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

2. 🧹 El sistema limpiará automáticamente la información.

3. 🔄 Se eliminarán las OT duplicadas conservando la más reciente.

4. 📋 Se extraerán únicamente las columnas necesarias para análisis y campañas.

5. 📊 Se generarán indicadores y gráficos automáticamente.

6. 📥 Descarga el archivo consolidado listo para usar.
""")

st.divider()

# =========================================
# CARGA DE ARCHIVO
# =========================================

archivo = st.file_uploader("📂 Arrastra aquí el archivo CSV de Taller", type=["csv"])

# =========================================
# PROCESAMIENTO
# =========================================

if archivo is not None:

    try:

        # =========================================
        # LEER ARCHIVO
        # =========================================

        df = pd.read_csv(archivo, sep=";", skiprows=1, dtype=str, engine="python")

        df.columns = df.columns.str.strip()

        # =========================================
        # VALIDAR COLUMNAS
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
            st.error(f"Faltan columnas en el archivo: {', '.join(faltantes)}")
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

else:

    st.info("👆 Carga un archivo CSV de Taller para comenzar.")
