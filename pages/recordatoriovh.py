import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Recordatorio VH", page_icon="🔔", layout="wide")

st.title("🔔 Recordatorio VH")
st.markdown("Carga los dos archivos y el cruce se genera automáticamente.")

with st.expander("ℹ️ ¿Cómo funciona este módulo?", expanded=False):
    st.markdown("""
1. 📁 Carga el archivo de **Vehículos** con datos de clientes y fechas de entrega.
2. 🔧 Carga el archivo de **Taller** con el historial de visitas y kilómetros.
3. 🔄 El sistema eliminará OT duplicadas conservando la más reciente.
4. 🚗 Se identificará la última visita registrada y el promedio de km/mes de cada vehículo.
5. 📅 Se estimará el mes en que cada vehículo alcanzará los 10.000 km.
6. 🏷️ Cada vehículo recibirá un estado: **Alcanzado**, **Activo** o **Pendiente**.
7. 📊 Se generarán indicadores y gráficos automáticamente.
8. 📥 Descarga la base lista para campañas de recordatorio.
""")

st.markdown("---")

# =========================================
# CONSTANTE
# =========================================

KM_META = 10000

# =========================================
# COLORES CONSISTENTES
# =========================================

COLORES_ESTADO = {
    "Alcanzado": "#22c55e",
    "Activo": "#3b82f6",
    "Pendiente": "#f59e0b",
}

# =========================================
# FUNCIONES DE PROCESAMIENTO
# =========================================


def procesar_vehiculos(archivo):
    df = pd.read_csv(archivo, sep=";")
    df.columns = df.columns.str.strip()

    if "Perfil Cliente" in df.columns:
        df = df[
            df["Perfil Cliente"].astype(str).str.strip().str.lower() == "particular"
        ]

    if "Fecha Paz y Salvo" in df.columns:
        df["Fecha Paz y Salvo"] = pd.to_datetime(
            df["Fecha Paz y Salvo"], errors="coerce", dayfirst=True, format="mixed"
        )
    if "F. Entrega Cliente" in df.columns:
        df["F. Entrega Cliente"] = pd.to_datetime(
            df["F. Entrega Cliente"], errors="coerce", dayfirst=True, format="mixed"
        )

    fecha_pys = df.get("Fecha Paz y Salvo", pd.Series(dtype="datetime64[ns]"))
    fecha_ent = df.get("F. Entrega Cliente", pd.Series(dtype="datetime64[ns]"))
    df["Fecha Entrega"] = fecha_pys.fillna(fecha_ent)

    if "Teléfonos" in df.columns:
        df["Teléfonos"] = df["Teléfonos"].astype(str)
        split = df["Teléfonos"].str.split(",", n=1, expand=True)
        df["Teléfonos"] = split[0].str.strip()
        df["Telefono 2"] = split[1].fillna("").str.strip() if 1 in split.columns else ""

        def agregar_prefijo(numero):
            numero = str(numero).strip()
            if numero in ("", "nan"):
                return ""
            return numero if numero.startswith("57") else "57" + numero

        df["Teléfonos"] = df["Teléfonos"].apply(agregar_prefijo)
        df["Telefono 2"] = df["Telefono 2"].apply(agregar_prefijo)

    df["Local"] = "co"
    df = df.drop_duplicates(subset=["Cliente", "Placa", "VIN"], keep="first")

    columnas_deseadas = [
        "VIN",
        "Placa",
        "Gama",
        "Cliente",
        "N° Doc. Cliente",
        "Teléfonos",
        "Telefono 2",
        "Email",
        "Fecha Entrega",
        "Local",
    ]
    columnas_presentes = [c for c in columnas_deseadas if c in df.columns]
    df["VIN"] = df["VIN"].astype(str).str.strip()
    return df[columnas_presentes]


def procesar_taller(archivo):
    df = pd.read_csv(archivo, sep=";")
    df.columns = df.columns.str.strip()

    if "VIN" not in df.columns:
        archivo.seek(0)
        df = pd.read_csv(archivo, sep=";", skiprows=1)
        df.columns = df.columns.str.strip()

    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    def parsear_fecha_fra(serie):
        return pd.to_datetime(
            serie.astype(str)
            .str.strip()
            .str.replace(r"a\.\s*m\.", "AM", regex=True)
            .str.replace(r"p\.\s*m\.", "PM", regex=True),
            errors="coerce",
            dayfirst=True,
            format="mixed",
        )

    if "Núm. OT" in df.columns and "F. Fra." in df.columns:
        df["F. Fra."] = parsear_fecha_fra(df["F. Fra."])
        df["OT_BASE"] = df["Núm. OT"].astype(str).str.replace(r"-\d+$", "", regex=True)
        df = df.sort_values("F. Fra.", ascending=False)
        df = df.drop_duplicates(subset="OT_BASE", keep="first")
        df = df.drop(columns=["OT_BASE"])
    else:
        df["F. Fra."] = parsear_fecha_fra(df["F. Fra."])

    if "Kilómetros" in df.columns:
        df["Kilómetros"] = (
            df["Kilómetros"]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        df["Kilómetros"] = pd.to_numeric(df["Kilómetros"], errors="coerce")

    df["VIN"] = df["VIN"].astype(str).str.strip()
    return df


def cruzar_tablas(df_vehiculos, df_taller):
    if "Fecha Entrega" in df_vehiculos.columns:
        df_vehiculos["Fecha Entrega"] = pd.to_datetime(
            df_vehiculos["Fecha Entrega"],
            errors="coerce",
            dayfirst=True,
            format="mixed",
        )

    visitas = df_taller.groupby("VIN").size().reset_index(name="Cantidad Visitas")
    ultima_visita = (
        df_taller.groupby("VIN")["F. Fra."]
        .max()
        .reset_index()
        .rename(columns={"F. Fra.": "Última Visita Taller"})
    )

    resumen = visitas.merge(ultima_visita, on="VIN", how="left")
    resultado = df_vehiculos.merge(resumen, on="VIN", how="left")
    resultado["Cantidad Visitas"] = resultado["Cantidad Visitas"].fillna(0).astype(int)

    def calcular_promedio_y_estimado(vin, fecha_entrega):
        visitas_vin = df_taller[df_taller["VIN"] == vin].copy()
        visitas_vin = visitas_vin.dropna(subset=["F. Fra.", "Kilómetros"])
        visitas_vin = visitas_vin.sort_values("F. Fra.", ascending=True)

        if len(visitas_vin) < 2 or pd.isna(fecha_entrega):
            return "", "", None

        km_ultima = visitas_vin.iloc[-1]["Kilómetros"]
        if km_ultima >= KM_META:
            return "", "", None

        fecha_ultima = visitas_vin.iloc[-1]["F. Fra."]
        delta = relativedelta(fecha_ultima, fecha_entrega)
        meses = delta.years * 12 + delta.months + delta.days / 30.0

        if meses <= 0:
            return "", "", None

        promedio = km_ultima / meses
        if promedio <= 0:
            return "", "", None

        meses_meta = KM_META / promedio
        fecha_estimada = fecha_entrega + relativedelta(
            months=int(meses_meta), days=int((meses_meta % 1) * 30)
        )

        return f"{promedio:.0f} km/mes", fecha_estimada.strftime("%m/%Y"), promedio

    def calcular_estado(vin, cantidad_visitas):
        visitas_vin = df_taller[df_taller["VIN"] == vin].copy()
        visitas_vin = visitas_vin.dropna(subset=["F. Fra.", "Kilómetros"])
        visitas_vin = visitas_vin.sort_values("F. Fra.", ascending=True)

        if len(visitas_vin) == 0:
            return "Pendiente"
        if visitas_vin.iloc[-1]["Kilómetros"] >= KM_META:
            return "Alcanzado"
        if cantidad_visitas >= 2:
            return "Activo"
        return "Pendiente"

    promedios, estimados, estados, promedios_num = [], [], [], []
    for _, fila in resultado.iterrows():
        vin = fila["VIN"]
        fecha_entrega = fila.get("Fecha Entrega", pd.NaT)
        p, e, p_num = calcular_promedio_y_estimado(vin, fecha_entrega)
        promedios.append(p)
        estimados.append(e)
        estados.append(calcular_estado(vin, fila["Cantidad Visitas"]))
        promedios_num.append(p_num)

    resultado["Promedio KM por Mes"] = promedios
    resultado["_promedio_num"] = promedios_num
    resultado["Mes Estimado 10.000 KM"] = estimados
    resultado["Estado"] = estados

    resultado["_UVT_raw"] = resultado["Última Visita Taller"]
    resultado["Última Visita Taller"] = (
        resultado["_UVT_raw"].dt.strftime("%d/%m/%Y").fillna("Sin fecha")
    )

    if "Fecha Entrega" in resultado.columns:
        resultado["Fecha Entrega"] = pd.to_datetime(
            resultado["Fecha Entrega"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")

    return resultado


# =========================================
# GRÁFICOS
# =========================================
def grafico_donut_estados(df):

    conteos = df["Estado"].value_counts().reset_index()

    conteos.columns = ["Estado", "Cantidad"]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=conteos["Estado"],
                values=conteos["Cantidad"],
                marker=dict(
                    colors=[
                        COLORES_ESTADO.get(estado, "#94a3b8")
                        for estado in conteos["Estado"]
                    ],
                    line=dict(color="white", width=3),
                ),
                pull=[0.03] * len(conteos),
                textinfo="percent+label",
                hovertemplate="<b>%{label}</b><br>"
                "%{value} vehículos<br>"
                "%{percent}<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        title=dict(text="✅ Distribución por Estado", x=0, font=dict(size=18)),
        height=380,
        margin=dict(t=60, b=10, l=10, r=10),
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5
        ),
        paper_bgcolor="rgba(0,0,0,0)",
    )

    return fig


def grafico_velocidad_gamas(df):
    """
    Barras horizontales: promedio km/mes por gama (solo Activos con promedio calculado).
    Muestra qué gamas acumulan km más rápido → llegarán antes a los 10.000.
    """
    if "Gama" not in df.columns:
        return None

    df_activos = df[(df["Estado"] == "Activo") & (df["_promedio_num"].notna())].copy()

    if df_activos.empty:
        return None

    resumen = (
        df_activos.groupby("Gama")["_promedio_num"]
        .mean()
        .reset_index()
        .rename(columns={"_promedio_num": "Promedio KM/mes"})
        .sort_values("Promedio KM/mes", ascending=True)
    )

    # Calcular meses estimados para llegar a meta
    resumen["Meses para 10.000 km"] = (KM_META / resumen["Promedio KM/mes"]).round(1)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            y=resumen["Gama"],
            x=resumen["Promedio KM/mes"],
            orientation="h",
            marker=dict(
                color=resumen["Promedio KM/mes"],
                colorscale=[[0, "#1e40af"], [0.5, "#3b82f6"], [1, "#22c55e"]],
                showscale=False,
                line=dict(color="rgba(0,0,0,0.1)", width=1),
            ),
            text=[f"{v:.0f} km/mes" for v in resumen["Promedio KM/mes"]],
            textposition="outside",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Promedio: %{x:.0f} km/mes<br>"
                "Meses est. para 10.000 km: %{customdata}<extra></extra>"
            ),
            customdata=resumen["Meses para 10.000 km"],
        )
    )

    fig.update_layout(
        title=dict(
            text="⚡ Velocidad por Gama — ¿Cuál llega antes a los 10.000 km?",
            font=dict(size=15),
            x=0,
        ),
        xaxis=dict(
            title="Promedio km/mes", showgrid=True, gridcolor="rgba(148,163,184,0.2)"
        ),
        yaxis=dict(title="", tickfont=dict(size=12)),
        margin=dict(t=55, b=40, l=10, r=80),
        height=max(280, len(resumen) * 48 + 80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def grafico_estado_por_gama(df):
    """
    Barras apiladas: por cada gama, cuántos vehículos están en cada estado.
    Permite ver de un vistazo qué gamas tienen más pendientes o alcanzados.
    """
    if "Gama" not in df.columns:
        return None

    tabla = df.groupby(["Gama", "Estado"]).size().reset_index(name="Cantidad")

    if tabla.empty:
        return None

    # Ordenar gamas por total de vehículos descendente
    orden_gamas = (
        tabla.groupby("Gama")["Cantidad"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )

    fig = go.Figure()

    for estado in ["Alcanzado", "Activo", "Pendiente"]:
        sub = tabla[tabla["Estado"] == estado]
        fig.add_trace(
            go.Bar(
                name=estado,
                x=sub["Gama"],
                y=sub["Cantidad"],
                marker_color=COLORES_ESTADO[estado],
                hovertemplate=f"<b>{estado}</b><br>Gama: %{{x}}<br>Cantidad: %{{y}}<extra></extra>",
            )
        )

    fig.update_layout(
        barmode="stack",
        title=dict(
            text="📊 Estado por Gama — Composición de la flota", font=dict(size=15), x=0
        ),
        xaxis=dict(
            title="Gama",
            categoryorder="array",
            categoryarray=orden_gamas,
            tickangle=-30,
        ),
        yaxis=dict(title="Vehículos", showgrid=True, gridcolor="rgba(148,163,184,0.2)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=70, b=60, l=10, r=10),
        height=370,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# =========================================
# UI — CARGA DE ARCHIVOS
# =========================================

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("📁 Archivo Vehículos")
    archivo_vehiculos = st.file_uploader(
        "Arrastra el CSV de vehículos aquí", type=["csv"], key="vh_vehiculos"
    )

with col_b:
    st.subheader("🔧 Archivo Taller")
    archivo_taller = st.file_uploader(
        "Arrastra el CSV del taller aquí", type=["csv"], key="vh_taller"
    )

# =========================================
# PROCESAMIENTO AUTOMÁTICO
# =========================================

if archivo_vehiculos is not None and archivo_taller is not None:

    with st.spinner("Procesando archivos y cruzando datos..."):
        try:
            df_v = procesar_vehiculos(archivo_vehiculos)
            df_t = procesar_taller(archivo_taller)

            errores = []
            if "VIN" not in df_v.columns:
                errores.append(
                    "❌ No se encontró la columna **VIN** en el archivo de vehículos."
                )
            if "VIN" not in df_t.columns:
                errores.append(
                    "❌ No se encontró la columna **VIN** en el archivo de taller."
                )
            if "F. Fra." not in df_t.columns:
                errores.append(
                    "❌ No se encontró la columna **F. Fra.** en el archivo de taller."
                )
            if "Kilómetros" not in df_t.columns:
                errores.append(
                    "❌ No se encontró la columna **Kilómetros** en el archivo de taller."
                )

            if errores:
                for e in errores:
                    st.error(e)
                st.stop()

            resultado = cruzar_tablas(df_v, df_t)

        except Exception as ex:
            st.error(f"Error al procesar los archivos: {ex}")
            st.stop()

    st.success(f"✅ Cruce completado — {len(resultado)} registros")
    st.markdown("---")

    # =========================================
    # GRÁFICOS
    # =========================================
    st.markdown("### 📊 Análisis Visual")

    st.plotly_chart(grafico_velocidad_gamas(resultado), use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.plotly_chart(grafico_donut_estados(resultado), use_container_width=True)

    with col2:
        st.plotly_chart(grafico_estado_por_gama(resultado), use_container_width=True)

    st.markdown("---")

    # =========================================
    # FILTROS
    # =========================================

    resultado_filtrado = resultado.copy()

    fechas_validas = resultado_filtrado["_UVT_raw"].dropna()

    if len(fechas_validas) > 0:
        st.markdown("### 📅 Filtrar por Última Visita Taller")
        fecha_min = fechas_validas.min().date()
        fecha_max = fechas_validas.max().date()
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input(
                "Desde", value=None, min_value=fecha_min, max_value=fecha_max, key="fi"
            )
        with col2:
            fecha_fin = st.date_input(
                "Hasta", value=None, min_value=fecha_min, max_value=fecha_max, key="ff"
            )

        if fecha_inicio and fecha_fin:
            resultado_filtrado = resultado_filtrado[
                (resultado_filtrado["_UVT_raw"] >= pd.to_datetime(fecha_inicio))
                & (resultado_filtrado["_UVT_raw"] <= pd.to_datetime(fecha_fin))
            ]

    st.markdown("---")

    st.markdown("### 🏷️ Filtrar por Estado")

    ESTADOS = ["Alcanzado", "Activo", "Pendiente"]
    ICONOS = {"Alcanzado": "🟢", "Activo": "🔵", "Pendiente": "🟡"}

    for estado in ESTADOS:
        if f"filtro_{estado}" not in st.session_state:
            st.session_state[f"filtro_{estado}"] = True

    cols = st.columns(3)
    for i, estado in enumerate(ESTADOS):
        with cols[i]:
            conteo = len(resultado_filtrado[resultado_filtrado["Estado"] == estado])
            nuevo = st.checkbox(
                f"{ICONOS[estado]} {estado} ({conteo})",
                value=st.session_state[f"filtro_{estado}"],
                key=f"chk_{estado}",
            )
            st.session_state[f"filtro_{estado}"] = nuevo

    estados_activos = [e for e in ESTADOS if st.session_state[f"filtro_{e}"]]

    if estados_activos:
        resultado_filtrado = resultado_filtrado[
            resultado_filtrado["Estado"].isin(estados_activos)
        ]
    else:
        st.warning("Selecciona al menos un estado para ver resultados.")
        resultado_filtrado = resultado_filtrado.iloc[0:0]

    st.markdown("---")

    # =========================================
    # TABLA RESULTADO
    # =========================================

    st.markdown("### 🗂️ Detalle de registros")

    columnas_ocultas = ["_UVT_raw", "_promedio_num"]
    columnas_mostrar = [
        c for c in resultado_filtrado.columns if c not in columnas_ocultas
    ]

    st.dataframe(
        resultado_filtrado[columnas_mostrar].reset_index(drop=True),
        use_container_width=True,
    )

    # =========================================
    # DESCARGA
    # =========================================

    csv_out = (
        resultado_filtrado[columnas_mostrar]
        .to_csv(index=False, sep=";")
        .encode("utf-8")
    )
    st.download_button(
        "⬇️ Descargar CSV Resultado", csv_out, "recordatorio_vh.csv", "text/csv"
    )

elif archivo_vehiculos is not None and archivo_taller is None:
    st.info("📂 Archivo de vehículos cargado. Ahora arrastra el archivo del taller.")

elif archivo_vehiculos is None and archivo_taller is not None:
    st.info("📂 Archivo de taller cargado. Ahora arrastra el archivo de vehículos.")

else:
    st.info("👆 Carga los dos archivos para generar el cruce automáticamente.")
