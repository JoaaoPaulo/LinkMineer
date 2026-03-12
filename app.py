"""
app.py – LinkMineer: Minerador Automático de Links de Afiliados
Interface Streamlit com barra de progresso, modo demo e exportação CSV/XLSX.
"""

import io
import streamlit as st
import pandas as pd
from miner import run_mining

# ---------------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="LinkMineer – Minerador de Afiliados",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Fundo e tipografia geral */
    [data-testid="stAppViewContainer"] { background: #0e1117; }
    h1 { font-size: 2rem !important; color: #f0f0f0; }
    h2, h3, h4 { color: #c9d1d9; }

    /* Botão principal */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(90deg, #fa8231, #e84393);
        border: none;
        color: white;
        font-size: 1.1rem;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        width: 100%;
        cursor: pointer;
        transition: opacity 0.2s;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover { opacity: 0.85; }

    /* Sidebar cards */
    [data-testid="stSidebar"] { background: #161b22; }

    /* Download buttons */
    div[data-testid="stDownloadButton"] > button {
        border-radius: 6px; font-weight: 600; width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
col_logo, col_title = st.columns([1, 10])
with col_logo:
    st.markdown("## ⛏️")
with col_title:
    st.markdown("# LinkMineer")
    st.caption("Mineração automática de links de afiliados para Mercado Livre, Amazon e Shopee")

st.divider()

# ---------------------------------------------------------------------------
# Sidebar – Configurações
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configurações")

    demo_mode = st.toggle("🧪 Modo Demo (sem navegador)", value=False,
                          help="Usa dados de exemplo, sem abrir o Chrome. Ideal para testar a interface e o download.")

    qtd_produtos = st.number_input(
        "🔢 Produtos por marketplace",
        min_value=1, max_value=200, value=5, step=1,
        help="Quantos produtos minerar em cada marketplace ativo."
    )

    st.markdown("---")

    # ---- Mercado Livre ----
    st.subheader("🛒 Mercado Livre")
    ml_active = st.checkbox("Ativar Mercado Livre", value=True)
    ml_tracking = st.text_input("Tracking ID / Matt Tool", placeholder="ex: ml-afiliado-123",
                                help="Seu ID de afiliado do Programa de Afiliados ML")
    ml_login_type = st.selectbox("Tipo de autenticação", ["Cookies (JSON)", "Credenciais"], key="ml_lt")
    if "Credenciais" in ml_login_type:
        ml_user = st.text_input("Usuário / E-mail ML", key="ml_user")
        ml_pass = st.text_input("Senha ML", type="password", key="ml_pass")
        ml_cookies = ""
    else:
        ml_cookies = st.text_area("Cole seus cookies ML (JSON array)", height=80, key="ml_cookies",
                                  help="Exporte via DevTools → Application → Cookies → copiar como JSON")
        ml_user, ml_pass = "", ""

    st.markdown("---")

    # ---- Amazon ----
    st.subheader("📦 Amazon")
    amz_active = st.checkbox("Ativar Amazon", value=True)
    amz_tag = st.text_input("Tag de afiliado", placeholder="ex: seunome-20",
                            help="Sua Tag do Amazon Associates (aparece na URL como ?tag=...)")
    amz_login_type = st.selectbox("Tipo de autenticação", ["Cookies (JSON)", "Credenciais"], key="amz_lt")
    if "Credenciais" in amz_login_type:
        amz_user = st.text_input("Usuário / E-mail Amazon", key="amz_user")
        amz_pass = st.text_input("Senha Amazon", type="password", key="amz_pass")
        amz_cookies = ""
    else:
        amz_cookies = st.text_area("Cole seus cookies Amazon (JSON array)", height=80, key="amz_cookies")
        amz_user, amz_pass = "", ""

    st.markdown("---")

    # ---- Shopee ----
    st.subheader("🛍️ Shopee")
    shp_active = st.checkbox("Ativar Shopee", value=True)
    shp_aff_id = st.text_input("Affiliate ID", placeholder="ex: 123456789",
                                help="Seu ID do Shopee Affiliate Program")
    shp_login_type = st.selectbox("Tipo de autenticação", ["Cookies (JSON)", "Credenciais"], key="shp_lt")
    if "Credenciais" in shp_login_type:
        shp_user = st.text_input("Usuário / E-mail Shopee", key="shp_user")
        shp_pass = st.text_input("Senha Shopee", type="password", key="shp_pass")
        shp_cookies = ""
    else:
        shp_cookies = st.text_area("Cole seus cookies Shopee (JSON array)", height=80, key="shp_cookies")
        shp_user, shp_pass = "", ""

# ---------------------------------------------------------------------------
# Área principal – Iniciar mineração
# ---------------------------------------------------------------------------
active_count = sum([ml_active, amz_active, shp_active])

if active_count == 0:
    st.warning("⚠️ Selecione pelo menos um marketplace na barra lateral.")

c1, c2, c3 = st.columns([3, 1, 3])
with c2:
    start_btn = st.button("🚀 Gerar Planilha", type="primary", disabled=(active_count == 0))

if start_btn:
    # Montar config
    config = {
        "demo_mode": demo_mode,
        "qtd_produtos": qtd_produtos,
        "marketplaces": {
            "Amazon": {
                "active": amz_active,
                "tag": amz_tag,
                "login_type": "Cookies" if "Cookies" in amz_login_type else "Credentials",
                "user": amz_user,
                "password": amz_pass,
                "cookies": amz_cookies,
            },
            "Mercado Livre": {
                "active": ml_active,
                "tracking_id": ml_tracking,
                "login_type": "Cookies" if "Cookies" in ml_login_type else "Credentials",
                "user": ml_user,
                "password": ml_pass,
                "cookies": ml_cookies,
            },
            "Shopee": {
                "active": shp_active,
                "affiliate_id": shp_aff_id,
                "login_type": "Cookies" if "Cookies" in shp_login_type else "Credentials",
                "user": shp_user,
                "password": shp_pass,
                "cookies": shp_cookies,
            },
        },
    }

    if demo_mode:
        st.info("🧪 **Modo Demo ativo** – Nenhum navegador será aberto. Os resultados são fictícios para teste.")

    st.markdown("### ⏳ Progresso da Mineração")
    progress_bar = st.progress(0.0)
    status_text = st.empty()

    results: list[dict] = []

    try:
        status_text.markdown("**Iniciando mineração...**")

        for update in run_mining(config):
            if "progress" in update:
                val = float(update["progress"])
                progress_bar.progress(min(val, 1.0))
                status_text.markdown(f"**{update.get('message', '')}**")
            if "result" in update:
                results.append(update["result"])

        progress_bar.progress(1.0)
        status_text.markdown("✅ **Mineração concluída!**")

    except Exception as e:
        status_text.markdown(f"❌ **Erro durante a mineração:** `{e}`")
        st.exception(e)

    # -----------------------------------------------------------------------
    # Exibir resultados
    # -----------------------------------------------------------------------
    if results:
        df = pd.DataFrame(results, columns=["marketplace", "link_produto", "link_afiliado"])

        st.success(f"🎉 **{len(df)} links coletados** em {df['marketplace'].nunique()} marketplace(s).")

        # Resumo por marketplace
        summary = df.groupby("marketplace").size().reset_index(name="qtd_coletada")
        st.dataframe(summary, use_container_width=True, hide_index=True)

        with st.expander("📋 Ver todos os links coletados"):
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### ⬇️ Baixar Planilha")

        # Exportações em memória
        csv_data = df.to_csv(index=False).encode("utf-8")

        xlsx_buffer = io.BytesIO()
        with pd.ExcelWriter(xlsx_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Links Afiliados")
        xlsx_data = xlsx_buffer.getvalue()

        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                label="⬇️ Baixar CSV",
                data=csv_data,
                file_name="links_afiliados.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with dl2:
            st.download_button(
                label="⬇️ Baixar XLSX",
                data=xlsx_data,
                file_name="links_afiliados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    else:
        st.warning(
            "⚠️ Nenhum link foi coletado. Possíveis causas:\n"
            "- Marketplace(s) bloquearam o acesso (captcha/bot detection)\n"
            "- Credenciais ou cookies inválidos\n"
            "- Seletores de página desatualizados\n\n"
            "💡 Tente o **Modo Demo** para verificar se a interface e o download funcionam corretamente."
        )
