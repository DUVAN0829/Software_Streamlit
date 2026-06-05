import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Reactivación Clientes", page_icon="♻️", layout="wide")

st.title("♻️ Reactivación Clientes")

with st.expander("ℹ️ ¿Cómo funciona este módulo?", expanded=False):
    st.markdown("""
1. 📂 Carga el archivo histórico de Taller.
2. 🔄 El sistema eliminará OT duplicadas conservando la más reciente.
3. 🚗 Se identificará la última visita registrada de cada vehículo.
4. 📅 Se calcularán los meses transcurridos desde esa visita hasta hoy.
5. ♻️ Se conservarán únicamente vehículos con 6 meses o más sin regresar al taller.
6. 📊 Se generarán indicadores y gráficos automáticamente.
7. 📥 Descarga la base lista para campañas de reactivación.
""")

st.markdown("---")

# =========================================
# CARGA ARCHIVO
# =========================================

archivo = st.file_uploader("📂 Carga el archivo de Taller", type=["csv"])

# =========================================
# FUNCIONES
# =========================================


def parsear_fecha_taller(serie):
    serie = (
        serie.astype(str)
        .str.strip()
        .str.replace(r"a\.\s*m\.", "AM", regex=True)
        .str.replace(r"p\.\s*m\.", "PM", regex=True)
    )
    return pd.to_datetime(serie, errors="coerce", dayfirst=True, format="mixed")


def calcular_meses(fecha):
    if pd.isna(fecha):
        return None
    hoy = pd.Timestamp.today()
    return (hoy.year - fecha.year) * 12 + (hoy.month - fecha.month)


def segmentar(meses):
    if meses < 12:
        return "6 - 12 meses"
    elif meses < 18:
        return "12 - 18 meses"
    elif meses < 24:
        return "18 - 24 meses"
    return "24+ meses"


# =========================================
# PROCESAMIENTO
# =========================================

if archivo is not None:

    try:
        df = pd.read_csv(archivo, sep=";", skiprows=1, dtype=str, engine="python")
        df.columns = df.columns.str.strip()
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

        columnas_requeridas = [
            "Núm. OT",
            "VIN",
            "Placa",
            "Gama",
            "Motivo de Entrada",
            "F. Fra.",
            "Cliente Fra.",
        ]
        faltantes = [c for c in columnas_requeridas if c not in df.columns]
        if faltantes:
            st.error(f"Faltan columnas: {', '.join(faltantes)}")
            st.stop()

        df["F. Fra."] = parsear_fecha_taller(df["F. Fra."])
        df["OT_BASE"] = df["Núm. OT"].astype(str).str.replace(r"-\d+$", "", regex=True)
        df = df.sort_values("F. Fra.", ascending=False)
        df = df.drop_duplicates(subset="OT_BASE", keep="first")
        df = df.drop_duplicates(subset="VIN", keep="first")
        df["Meses sin asistencia"] = df["F. Fra."].apply(calcular_meses)
        df = df[df["Meses sin asistencia"] >= 6]
        df["Segmento Reactivación"] = df["Meses sin asistencia"].apply(segmentar)
        df["F. Fra."] = df["F. Fra."].dt.strftime("%d/%m/%Y")

        resultado = df[
            [
                "Núm. OT",
                "Placa",
                "VIN",
                "Gama",
                "Motivo de Entrada",
                "F. Fra.",
                "Cliente Fra.",
                "Meses sin asistencia",
                "Segmento Reactivación",
            ]
        ].copy()

        st.success(f"✅ Vehículos candidatos a reactivación: {len(resultado)}")
        st.markdown("---")

        # =========================================
        # GRÁFICO 1 — MOTIVOS DE ENTRADA
        # =========================================

        motivos = (
            resultado["Motivo de Entrada"]
            .fillna("Sin dato")
            .astype(str)
            .str.strip()
            .value_counts()
            .head(10)
            .reset_index()
        )

        motivos.columns = ["Motivo", "Cantidad"]

        fig1 = go.Figure()

        fig1.add_trace(
            go.Pie(
                labels=motivos["Motivo"],
                values=motivos["Cantidad"],
                hole=0.45,
                pull=[0.03] * len(motivos),
                marker=dict(
                    colors=[
                        "#3b82f6",
                        "#22c55e",
                        "#f59e0b",
                        "#ef4444",
                        "#8b5cf6",
                        "#06b6d4",
                        "#ec4899",
                        "#84cc16",
                        "#f97316",
                        "#14b8a6",
                    ]
                ),
            )
        )

        fig1.update_layout(
            title=dict(
                text="📋 Motivos de Entrada Más Frecuentes",
                x=0,
                font=dict(size=16),
            ),
            height=380,
        )

        gamas = (
            resultado["Gama"]
            .fillna("Sin dato")
            .astype(str)
            .str.strip()
            .value_counts()
            .head(10)
            .reset_index()
        )

        gamas.columns = ["Gama", "Cantidad"]

        gamas = gamas.sort_values("Cantidad", ascending=True)

        # =========================================
        # GRÁFICO 2 — GAMAS CON MAYOR INACTIVIDAD
        # =========================================

        fig2 = go.Figure()

        fig2.add_trace(
            go.Bar(
                y=gamas["Gama"],
                x=gamas["Cantidad"],
                orientation="h",
                text=gamas["Cantidad"],
                textposition="outside",
                marker=dict(
                    color=[
                        "#22c55e",
                        "#06b6d4",
                        "#f59e0b",
                        "#ef4444",
                        "#8b5cf6",
                        "#14b8a6",
                        "#ec4899",
                        "#84cc16",
                        "#f97316",
                        "#3b82f6",
                    ][: len(gamas)],
                ),
            )
        )

        fig2.update_layout(
            title="🚗 Top Gamas con Mayor Inactividad",
            yaxis=dict(categoryorder="total ascending"),
            height=420,
            showlegend=False,
        )

        # =========================================
        # MOSTRAR GRÁFICOS
        # =========================================

        st.markdown("### 📊 Análisis Visual")

        gc1, gc2 = st.columns(2)

        with gc1:
            st.plotly_chart(fig1, use_container_width=True)

        with gc2:
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")

        # =========================================
        # TABLA
        # =========================================

        st.markdown("### 📋 Vehículos para Reactivación")
        st.dataframe(resultado, use_container_width=True)

        # =========================================
        # DESCARGA
        # =========================================

        csv = resultado.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button(
            "⬇️ Descargar CSV", csv, "reactivacion_clientes.csv", "text/csv"
        )

    except Exception as e:
        st.exception(e)

else:
    st.info("👆 Carga el archivo histórico de Taller para comenzar.")
