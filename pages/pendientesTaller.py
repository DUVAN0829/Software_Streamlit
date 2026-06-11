import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Pendientes Taller", page_icon="🔧", layout="wide")

# =========================================
# ENCABEZADO
# =========================================

st.title("🔧 Pendientes Taller")

st.markdown("""
Cruza automáticamente las órdenes pendientes del taller con la información de clientes y vehículos.
""")

with st.expander("ℹ️ ¿Cómo funciona este módulo?"):

    st.markdown("""
    1. 📋 Carga el archivo **Service Scam Reporte**.
    2. 🔧 Carga el archivo **Mantenimientos Pendientes**.
    3. 🚗 Carga el archivo **Citas / VIN**.
    4. 🔄 El sistema realizará los cruces automáticamente.
    5. 📥 Descarga el resultado final.
    """)

st.divider()

# =========================================
# CARGA DE ARCHIVOS
# =========================================

st.subheader("📂 Archivos requeridos")

col1, col2, col3 = st.columns(3)

with col1:
    archivo_1 = st.file_uploader(
        "📋 Service Scam Reporte", type=["csv"], key="archivo1"
    )

with col2:
    archivo_2 = st.file_uploader(
        "🔧 Mantenimientos Pendientes", type=["csv"], key="archivo2"
    )

with col3:
    archivo_3 = st.file_uploader("🚗 Clientes / VIN", type=["csv"], key="archivo3")

# =========================================
# ESTADO DE CARGA
# =========================================

archivos_cargados = sum(
    [archivo_1 is not None, archivo_2 is not None, archivo_3 is not None]
)

if archivos_cargados < 3:

    st.warning(
        f"⏳ Archivos cargados: {archivos_cargados}/3. "
        "Carga todos los archivos para iniciar el proceso."
    )

# =========================================
# PROCESAR
# =========================================

if archivo_1 is not None and archivo_2 is not None and archivo_3 is not None:

    st.success("✅ Archivos cargados correctamente.")

    try:

        # =========================================
        # LEER ARCHIVOS
        # =========================================

        df1 = pd.read_csv(archivo_1, sep=";", dtype=str, engine="python")

        df2 = pd.read_csv(archivo_2, sep=";", skiprows=1, dtype=str, engine="python")

        df3 = pd.read_csv(archivo_3, sep=";", dtype=str, engine="python")

        # =========================================
        # LIMPIAR COLUMNAS
        # =========================================

        df1.columns = df1.columns.str.strip()
        df2.columns = df2.columns.str.strip()
        df3.columns = df3.columns.str.strip()

        # =========================================
        # LIMPIAR ORDER NUMBER
        # =========================================

        df1["order_number"] = df1["order_number"].astype(str).str.strip()

        # =========================================
        # EXTRAER OT
        # =========================================

        df2["OT_LIMPIO"] = df2["Núm. OT"].astype(str).str.extract(r"OT\/(\d+)\/")

        # =========================================
        # LIMPIAR VIN
        # =========================================

        df2["VIN"] = df2["VIN"].astype(str).str.strip()

        df3["VIN"] = df3["VIN"].astype(str).str.strip()

        # =========================================
        # ELIMINAR DUPLICADOS
        # =========================================

        df1 = df1.drop_duplicates(subset=["order_number"])

        df2 = df2.drop_duplicates(subset=["OT_LIMPIO"])

        df3 = df3.drop_duplicates(subset=["VIN"])

        # =========================================
        # CRUCE 1
        # =========================================

        resultado = pd.merge(
            df1[["order_number", "title"]],
            df2[["OT_LIMPIO", "Núm. OT", "Placa", "VIN", "Marca", "Gama", "F. Fra."]],
            left_on="order_number",
            right_on="OT_LIMPIO",
            how="inner",
        )

        # =========================================
        # CRUCE 2
        # =========================================

        resultado = pd.merge(
            resultado,
            df3[["VIN", "Nombre Cliente", "Telf. Móvil", "Resto Telfs"]],
            on="VIN",
            how="left",
        )

        # RELLENAR TELÉFONO
        resultado["Telf. Móvil"] = resultado["Telf. Móvil"].fillna("").str.strip()
        resultado["Resto Telfs"] = resultado["Resto Telfs"].fillna("").str.strip()

        resultado["Telf. Móvil"] = resultado.apply(
            lambda row: (
                row["Resto Telfs"] if row["Telf. Móvil"] == "" else row["Telf. Móvil"]
            ),
            axis=1,
        )

        resultado = resultado.drop(
            columns=["Resto Telfs"]
        )  # opcional: ocultar del resultado final

        # =========================================
        # FECHA
        # =========================================

        resultado["F. Fra."] = pd.to_datetime(
            resultado["F. Fra."], dayfirst=True, errors="coerce"
        ).dt.strftime("%d/%m/%Y")

        # =========================================
        # ELIMINAR AUXILIAR
        # =========================================

        resultado = resultado.drop(columns=["OT_LIMPIO"])

        st.divider()

        # =========================================
        # DASHBOARD
        # =========================================

        st.subheader("📊 Resumen de Pendientes")

        # =========================================
        # DASHBOARD VISUAL
        # =========================================

        st.divider()

        col1, col2 = st.columns(2)

        # =========================================
        # GRAFICO POR GAMA
        # =========================================

        with col1:

            st.subheader("🚗 Pendientes por Gama")

            gamas = (
                resultado["Gama"]
                .fillna("Sin Gama")
                .value_counts()
                .head(10)
                .reset_index()
            )

            gamas.columns = ["Gama", "Cantidad"]

            fig_gamas = px.bar(
                gamas,
                x="Gama",
                y="Cantidad",
                color="Gama",
                text_auto=True,
                title="Top 10 Gamas con Pendientes",
            )

            fig_gamas.update_layout(
                showlegend=False, xaxis_title="", yaxis_title="Cantidad"
            )

            st.plotly_chart(fig_gamas, use_container_width=True)

        # =========================================
        # GRAFICO SERVICIOS
        # =========================================

        with col2:

            st.subheader("🔧 Servicios Pendientes")

            servicios = (
                resultado["title"]
                .fillna("Sin Servicio")
                .value_counts()
                .head(10)
                .reset_index()
            )

            servicios.columns = ["Servicio", "Cantidad"]

            fig_servicios = px.pie(
                servicios,
                names="Servicio",
                values="Cantidad",
                hole=0.4,
                title="Distribución de Servicios",
            )

            st.plotly_chart(fig_servicios, use_container_width=True)

        st.divider()

        # =========================================
        # TABLA
        # =========================================

        st.subheader("📄 Resultado del Cruce")

        st.dataframe(resultado, use_container_width=True)

        # =========================================
        # DESCARGA
        # =========================================

        csv = resultado.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            label="📥 Descargar Resultado",
            data=csv,
            file_name="resultado_cruce.csv",
            mime="text/csv",
            use_container_width=True,
        )

    except Exception as e:

        st.error(f"❌ Ocurrió un error: {e}")
