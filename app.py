import streamlit as st

st.set_page_config(
    page_title="Mini CRM - Carrazos Duván", page_icon="🚗", layout="wide"
)

# ==========================
# PÁGINAS
# ==========================

pg = st.navigation(
    [
        st.Page(
            "pages/postservicio.py",
            title="Postservicio",
            icon="📋",
            default=True,
        ),
        st.Page(
            "pages/recordatoriovh.py",
            title="Recordatorio VH",
            icon="🔔",
        ),
        st.Page(
            "pages/pendientesTaller.py",
            title="Pendientes Taller",
            icon="🔧",
        ),
        st.Page(
            "pages/reactivacionCliente.py",
            title="Reactivación Clientes",
            icon="♻️",
        ),
    ]
)

pg.run()
