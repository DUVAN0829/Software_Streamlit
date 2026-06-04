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
        # GRÁFICO 1 — BARRAS POR SEGMENTO
        # =========================================

        ORDEN_SEGMENTOS = [
            "6 - 12 meses",
            "12 - 18 meses",
            "18 - 24 meses",
            "24+ meses",
        ]
        COLORES_SEGMENTOS = {
            "6 - 12 meses": "#22c55e",
            "12 - 18 meses": "#f59e0b",
            "18 - 24 meses": "#ef4444",
            "24+ meses": "#8b5cf6",
        }

        seg_counts = resultado["Segmento Reactivación"].value_counts()
        total = seg_counts.sum()

        seg_df = pd.DataFrame(
            {
                "Segmento": ORDEN_SEGMENTOS,
                "Cantidad": [seg_counts.get(s, 0) for s in ORDEN_SEGMENTOS],
            }
        )
        seg_df["Porcentaje"] = (seg_df["Cantidad"] / total * 100).round(1)
        seg_df["Color"] = seg_df["Segmento"].map(COLORES_SEGMENTOS)

        fig1 = go.Figure()

        fig1.add_trace(
            go.Bar(
                x=seg_df["Segmento"],
                y=seg_df["Cantidad"],
                marker=dict(
                    color=seg_df["Color"].tolist(),
                    line=dict(color="rgba(0,0,0,0.15)", width=1),
                ),
                text=[
                    f"{p}%<br>({c})"
                    for p, c in zip(seg_df["Porcentaje"], seg_df["Cantidad"])
                ],
                textposition="outside",
                textfont=dict(size=13),
                hovertemplate="<b>%{x}</b><br>%{y} vehículos<br>%{text}<extra></extra>",
            )
        )

        fig1.update_layout(
            title=dict(text="Segmentos de Reactivación", font=dict(size=16), x=0),
            xaxis=dict(title="", tickfont=dict(size=13)),
            yaxis=dict(
                title="Vehículos",
                showgrid=True,
                gridcolor="rgba(148,163,184,0.2)",
            ),
            margin=dict(t=55, b=30, l=10, r=10),
            height=370,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )

        # =========================================
        # GRÁFICO 2 — GAMAS CON MAYOR INACTIVIDAD
        # =========================================

        gamas = resultado["Gama"].value_counts().head(10).reset_index()
        gamas.columns = ["Gama", "Cantidad"]
        gamas = gamas.sort_values("Cantidad", ascending=True)
        gamas["Porcentaje"] = (gamas["Cantidad"] / total * 100).round(1)

        fig2 = go.Figure()

        fig2.add_trace(
            go.Bar(
                y=gamas["Gama"],
                x=gamas["Cantidad"],
                orientation="h",
                marker=dict(
                    color="#3b82f6",
                    opacity=0.85,
                    line=dict(color="rgba(0,0,0,0.1)", width=1),
                ),
                text=[
                    f"{c}  ({p}%)"
                    for c, p in zip(gamas["Cantidad"], gamas["Porcentaje"])
                ],
                textposition="outside",
                textfont=dict(size=12),
                hovertemplate="<b>%{y}</b><br>%{x} vehículos<br>%{text}<extra></extra>",
            )
        )

        fig2.update_layout(
            title=dict(
                text="Gamas con Mayor Inactividad (Top 10)", font=dict(size=16), x=0
            ),
            xaxis=dict(
                title="Vehículos",
                showgrid=True,
                gridcolor="rgba(148,163,184,0.2)",
            ),
            yaxis=dict(title="", tickfont=dict(size=12)),
            margin=dict(t=55, b=30, l=10, r=80),
            height=max(300, len(gamas) * 42 + 80),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )

        # =========================================
        # MOSTRAR GRÁFICOS
        # =========================================

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
