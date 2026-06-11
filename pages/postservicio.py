import streamlit as st
import pandas as pd
import plotly.express as px

# =========================================
# CONFIGURACIÓN
# =========================================

st.set_page_config(page_title="📋 Consolidado Taller", page_icon="🔧", layout="wide")

st.title("🔧 Consolidado Taller")

with st.expander("ℹ️ ¿Cómo funciona este módulo?", expanded=False):

    st.markdown("""
1. 📂 Carga el archivo exportado desde Taller.

2. 📅 Carga el archivo de Citas (opcional) para cruzar teléfonos por VIN.

3. 🧹 El sistema limpiará automáticamente la información.

4. 🔄 Se eliminarán las OT duplicadas conservando la más reciente.

5. 📋 Se extraerán únicamente las columnas necesarias para análisis y campañas.

6. 📞 Si se cargó el archivo de Citas, se agregará la columna **Numero Telefono** cruzando por VIN.

7. 📊 Se generarán indicadores y gráficos automáticamente.

8. 📥 Descarga el archivo consolidado listo para usar.
""")

st.divider()

# =========================================
# CARGA DE ARCHIVOS
# =========================================

col_up1, col_up2 = st.columns(2)

with col_up1:
    archivo = st.file_uploader("📂 Archivo CSV de Taller", type=["csv"])

with col_up2:
    archivo_citas = st.file_uploader(
        "📅 Archivo CSV de Citas (opcional — para cruzar teléfonos)", type=["csv"]
    )

# =========================================
# ESTADO DE CARGA
# =========================================

archivos_cargados = sum([archivo is not None])

if archivos_cargados < 1:

    st.warning(
        f"⏳ Archivo cargado: {archivos_cargados}/1. "
        "Carga el archivo de Taller para iniciar el proceso."
    )

else:

    msg = "✅ Archivo de Taller cargado correctamente."
    if archivo_citas is not None:
        msg += " Archivo de Citas cargado — se cruzarán los teléfonos por VIN."
    st.success(msg)

# =========================================
# PROCESAMIENTO
# =========================================

if archivo is not None:

    try:

        # =========================================
        # LEER ARCHIVO TALLER
        # =========================================

        df = pd.read_csv(archivo, sep=";", skiprows=1, dtype=str, engine="python")

        df.columns = df.columns.str.strip()

        # =========================================
        # VALIDAR COLUMNAS TALLER
        # =========================================

        columnas_necesarias = [
            "Núm. OT",
            "Placa",
            "VIN",
            "Gama",
            "Motivo de Entrada",
            "F. Fra.",
            "Cliente Fra.",
        ]

        faltantes = [c for c in columnas_necesarias if c not in df.columns]

        if faltantes:
            st.error(f"Faltan columnas en el archivo de Taller: {', '.join(faltantes)}")
            st.stop()

        # =========================================
        # EXTRAER COLUMNAS
        # =========================================

        df = df[columnas_necesarias].copy()

        # =========================================
        # LIMPIAR FECHA
        # =========================================

        df["F. Fra."] = (
            df["F. Fra."]
            .astype(str)
            .str.replace(r"a\.\s*m\.", "AM", regex=True)
            .str.replace(r"p\.\s*m\.", "PM", regex=True)
        )

        df["F. Fra."] = pd.to_datetime(
            df["F. Fra."], errors="coerce", dayfirst=True, format="mixed"
        )

        # =========================================
        # OT BASE
        # =========================================

        df["OT_BASE"] = df["Núm. OT"].astype(str).str.replace(r"-\d+$", "", regex=True)

        # =========================================
        # CONSERVAR OT MÁS RECIENTE
        # =========================================

        df = df.sort_values(by="F. Fra.", ascending=False)

        antes = len(df)

        df = df.drop_duplicates(subset="OT_BASE", keep="first")

        eliminadas = antes - len(df)

        df = df.drop(columns=["OT_BASE"])

        # =========================================
        # FORMATO FECHA FINAL
        # =========================================

        df["F. Fra."] = df["F. Fra."].dt.strftime("%d/%m/%Y")

        # =========================================
        # CRUCE CON ARCHIVO CITAS (VIN → Celular)
        # =========================================

        cruce_info = None  # Para mostrar métricas del cruce más adelante

        if archivo_citas is not None:

            try:

                df_citas = pd.read_csv(
                    archivo_citas, sep=";", dtype=str, engine="python"
                )

                df_citas.columns = df_citas.columns.str.strip()

                # Validar que existan las columnas necesarias en Citas
                cols_citas_necesarias = ["VIN", "Celular"]
                faltantes_citas = [
                    c for c in cols_citas_necesarias if c not in df_citas.columns
                ]

                if faltantes_citas:
                    st.warning(
                        f"⚠️ El archivo de Citas no tiene las columnas requeridas: "
                        f"{', '.join(faltantes_citas)}. No se realizará el cruce."
                    )

                else:

                    # Limpiar VIN en ambos DataFrames para evitar espacios
                    df["VIN"] = df["VIN"].astype(str).str.strip()
                    df_citas["VIN"] = df_citas["VIN"].astype(str).str.strip()
                    df_citas["Celular"] = df_citas["Celular"].astype(str).str.strip()

                    # Conservar solo el primer registro por VIN en Citas
                    # (en caso de que un mismo VIN aparezca varias veces)
                    df_citas_unique = df_citas[["VIN", "Celular"]].drop_duplicates(
                        subset="VIN", keep="first"
                    )

                    # Cruce: left join por VIN
                    total_antes = len(df)
                    df = df.merge(df_citas_unique, on="VIN", how="left")

                    # Renombrar la columna Celular → Numero Telefono
                    df = df.rename(columns={"Celular": "Numero Telefono"})

                    # Reemplazar "nan" textual por vacío
                    df["Numero Telefono"] = df["Numero Telefono"].replace("nan", "")

                    # Calcular métricas del cruce
                    con_telefono = df["Numero Telefono"].notna() & (
                        df["Numero Telefono"] != ""
                    )
                    cruce_info = {
                        "con_telefono": con_telefono.sum(),
                        "sin_telefono": (~con_telefono).sum(),
                        "total": total_antes,
                    }

            except Exception as e_citas:
                st.warning(
                    f"⚠️ No se pudo procesar el archivo de Citas: {e_citas}. "
                    "El consolidado se generará sin número de teléfono."
                )

        # =========================================
        # KPIs
        # =========================================

        st.success(f"✅ Proceso completado. Se eliminaron {eliminadas} OT duplicadas.")

        st.divider()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("📄 OTs Únicas", len(df))

        with col2:
            st.metric("🚗 Vehículos Únicos", df["VIN"].nunique())

        with col3:
            st.metric("👤 Clientes Únicos", df["Cliente Fra."].nunique())

        # KPIs adicionales del cruce de teléfonos
        if cruce_info:
            st.divider()
            st.subheader("📞 Resultado del Cruce de Teléfonos")

            c1, c2, c3 = st.columns(3)

            with c1:
                st.metric("✅ Con Número Telefono", cruce_info["con_telefono"])
            with c2:
                st.metric("❌ Sin Número Telefono", cruce_info["sin_telefono"])
            with c3:
                pct = (
                    round(cruce_info["con_telefono"] / cruce_info["total"] * 100, 1)
                    if cruce_info["total"] > 0
                    else 0
                )
                st.metric("📊 Cobertura", f"{pct}%")

        st.divider()

        # =========================================
        # GRÁFICOS
        # =========================================

        col1, col2 = st.columns(2)

        with col1:

            st.subheader("🔧 Motivos de Entrada")

            motivos = (
                df["Motivo de Entrada"]
                .fillna("Sin dato")
                .value_counts()
                .head(10)
                .reset_index()
            )

            motivos.columns = ["Motivo", "Cantidad"]

            fig_motivos = px.bar(
                motivos, x="Motivo", y="Cantidad", color="Motivo", text_auto=True
            )

            fig_motivos.update_layout(
                showlegend=False, xaxis_title="", yaxis_title="Cantidad"
            )

            st.plotly_chart(fig_motivos, use_container_width=True)

        with col2:

            st.subheader("🚗 Gamas Atendidas")

            gamas = df["Gama"].fillna("Sin dato").value_counts().head(10).reset_index()

            gamas.columns = ["Gama", "Cantidad"]

            fig_gamas = px.pie(gamas, names="Gama", values="Cantidad", hole=0.45)

            st.plotly_chart(fig_gamas, use_container_width=True)

        st.divider()

        # =========================================
        # TABLA
        # =========================================

        st.subheader("📋 Resultado Consolidado")

        st.dataframe(df.reset_index(drop=True), use_container_width=True)

        # =========================================
        # DESCARGA
        # =========================================

        csv = df.to_csv(index=False, sep=";").encode("utf-8-sig")

        st.download_button(
            label="⬇️ Descargar CSV",
            data=csv,
            file_name="consolidado_taller.csv",
            mime="text/csv",
        )

    except Exception as e:

        st.error(f"Ocurrió un error al procesar el archivo:\n\n{e}")
