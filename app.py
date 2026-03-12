"""
app.py – LinkMineer: Minerador Automático de Links de Afiliados
Interface Streamlit compatível com Railway e execução local.

Variáveis de ambiente suportadas (defina no painel do Railway):
  ML_TRACKING_ID  → Tracking ID / Matt Tool do Mercado Livre
  AMAZON_TAG      → Tag de afiliado da Amazon (ex: seunome-20)
  SHOPEE_ID       → Affiliate ID da Shopee

Essas variáveis pré-preenchem os campos na interface, mas o usuário
pode sobrescrevê-las a qualquer momento pela sidebar.
"""

import io
import os
import streamlit as st
import pandas as pd
from miner import run_mining

# -----------------------------------------------------------------------
# Lê valores padrão das variáveis de ambiente do Railway (ou deixa vazio)
# -----------------------------------------------------------------------
DEFAULT_ML_TRACKING = os.environ.get("ML_TRACKING_ID", "")
DEFAULT_ML_MATT     = os.environ.get("ML_MATT_TOOL", "")
DEFAULT_AMAZON_TAG  = os.environ.get("AMAZON_TAG", "")
DEFAULT_SHOPEE_ID   = os.environ.get("SHOPEE_ID", "")

# -----------------------------------------------------------------------
# Configuração da página Streamlit
# -----------------------------------------------------------------------
st.set_page_config(
    page_title="LinkMineer – Minerador de Afiliados",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos visuais customizados
st.markdown("""
<style>
    /* Fundo escuro */
    [data-testid="stAppViewContainer"] { background: #0e1117; }
    h1 { font-size: 2rem !important; color: #f0f0f0; }
    h2, h3, h4 { color: #c9d1d9; }

    /* Botão principal com gradiente laranja → rosa */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(90deg, #fa8231, #e84393);
        border: none;
        color: white;
        font-size: 1.1rem;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        width: 100%;
        transition: opacity 0.2s;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover { opacity: 0.85; }

    /* Sidebar levemente diferenciada */
    [data-testid="stSidebar"] { background: #161b22; }

    /* Botões de download com borda arredondada */
    div[data-testid="stDownloadButton"] > button {
        border-radius: 6px; font-weight: 600; width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------
# Cabeçalho da página
# -----------------------------------------------------------------------
col_icon, col_title = st.columns([1, 10])
with col_icon:
    st.markdown("## ⛏️")
with col_title:
    st.markdown("# LinkMineer")
    st.caption("Mineração automática de links de afiliados • Mercado Livre · Amazon · Shopee")

st.divider()

# -----------------------------------------------------------------------
# Barra lateral – Configurações
# -----------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configurações")

    # Modo Demo: não abre navegador, usa dados fictícios
    demo_mode = st.toggle(
        "🧪 Modo Demo (sem navegador)",
        value=False,
        help=(
            "Usa produtos de exemplo sem abrir o Chrome. "
            "Ideal para testar a interface e o download antes de usar com conta real."
        )
    )

    # Quantidade de produtos para minerar por marketplace
    qtd_produtos = st.number_input(
        "🔢 Produtos por marketplace",
        min_value=1, max_value=200, value=5, step=1,
        help="Define quantos produtos serão coletados em cada marketplace ativo."
    )

    st.markdown("---")

    # ----------------------------------------------------------------
    # Mercado Livre
    # ----------------------------------------------------------------
    st.subheader("🛒 Mercado Livre")
    ml_active = st.checkbox("Minar Mercado Livre", value=True)
    ml_tracking = st.text_input(
        "Tracking ID (ML)",
        value=DEFAULT_ML_TRACKING,
        placeholder="ex: meu-tracking-123",
        help="ID de rastreio simples. Gerado no painel de afiliados."
    )
    ml_matt = st.text_input(
        "Matt Tool (ML)",
        value=DEFAULT_ML_MATT,
        placeholder="ex: matt_word=...&matt_tool=...",
        help="String completa de parâmetros do Matt Tool (opcional)."
    )
    ml_login_type = st.selectbox(
        "Autenticação ML",
        ["Cookies (JSON)", "Credenciais"],
        key="ml_lt"
    )
    if "Credenciais" in ml_login_type:
        ml_user = st.text_input("Usuário / E-mail ML", key="ml_user")
        ml_pass = st.text_input("Senha ML", type="password", key="ml_pass")
        ml_cookies = ""
    else:
        ml_cookies = st.text_area("Cookies ML (JSON array)", height=80, key="ml_cookies")
        ml_user, ml_pass = "", ""

    st.markdown("---")

    # ----------------------------------------------------------------
    # Amazon
    # DEFAULT_AMAZON_TAG vem da variável de ambiente AMAZON_TAG
    # ----------------------------------------------------------------
    st.subheader("📦 Amazon")
    amz_active = st.checkbox("Minar Amazon", value=True)
    amz_tag = st.text_input(
        "Tag de afiliado (AMZ)",
        value=DEFAULT_AMAZON_TAG,
        placeholder="ex: seunome-20",
        help="Sua Tag do Amazon Associates."
    )
    amz_login_type = st.selectbox("Autenticação AMZ", ["Cookies (JSON)", "Credenciais"], key="amz_lt")
    if "Credenciais" in amz_login_type:
        amz_user = st.text_input("Usuário / E-mail Amazon", key="amz_user")
        amz_pass = st.text_input("Senha Amazon", type="password", key="amz_pass")
        amz_cookies = ""
    else:
        amz_cookies = st.text_area("Cookies Amazon (JSON array)", height=80, key="amz_cookies")
        amz_user, amz_pass = "", ""

    st.markdown("---")

    # ----------------------------------------------------------------
    # Shopee
    # DEFAULT_SHOPEE_ID vem da variável de ambiente SHOPEE_ID
    # ----------------------------------------------------------------
    st.subheader("🛍️ Shopee")
    shp_active = st.checkbox("Minar Shopee", value=True)
    shp_aff_id = st.text_input(
        "Affiliate ID (SHP)",
        value=DEFAULT_SHOPEE_ID,
        placeholder="ex: 123456789",
        help="Seu ID do Shopee Affiliate Program."
    )
    shp_login_type = st.selectbox("Autenticação SHP", ["Cookies (JSON)", "Credenciais"], key="shp_lt")
    if "Credenciais" in shp_login_type:
        shp_user = st.text_input("Usuário / E-mail Shopee", key="shp_user")
        shp_pass = st.text_input("Senha Shopee", type="password", key="shp_pass")
        shp_cookies = ""
    else:
        shp_cookies = st.text_area("Cookies Shopee (JSON array)", height=80, key="shp_cookies")
        shp_user, shp_pass = "", ""

# -----------------------------------------------------------------------
# Área principal – Botão de ação
# -----------------------------------------------------------------------
active_count = sum([ml_active, amz_active, shp_active])

if active_count == 0:
    st.warning("⚠️ Selecione pelo menos um marketplace na barra lateral.")

# Centraliza o botão na tela
col_left, col_center, col_right = st.columns([3, 2, 3])
with col_center:
    start_btn = st.button(
        "🚀 Gerar Planilha",
        type="primary",
        disabled=(active_count == 0),
        use_container_width=True
    )

# -----------------------------------------------------------------------
# Execução da mineração ao clicar no botão
# -----------------------------------------------------------------------
if start_btn:
    # Monta o dicionário de configuração a partir dos campos da sidebar
    config = {
        "demo_mode": demo_mode,
        "qtd_produtos": int(qtd_produtos),
        "marketplaces": {
            "Amazon": {
                "active": amz_active,
                "tag": amz_tag,
                # Normaliza tipo de login para "Cookies" ou "Credentials"
                "login_type": "Cookies" if "Cookies" in amz_login_type else "Credentials",
                "user": amz_user,
                "password": amz_pass,
                "cookies": amz_cookies,
            },
            "Mercado Livre": {
                "active": ml_active,
                "tracking_id": ml_tracking,
                "matt_tool": ml_matt,
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

    # Aviso de modo demo
    if demo_mode:
        st.info(
            "🧪 **Modo Demo ativo** — Nenhum navegador será aberto. "
            "Os produtos abaixo são fictícios, usados apenas para testar a interface."
        )

    # Barra de progresso e status
    st.markdown("### ⏳ Progresso da Mineração")
    progress_bar = st.progress(0.0)
    status_text = st.empty()

    # Lista que acumula os resultados conforme chegam
    results: list = []

    try:
        status_text.markdown("**Iniciando mineração...**")

        # Consome o generator do miner.py, processando cada update em tempo real
        for update in run_mining(config):
            if "progress" in update:
                # Garante que o valor está entre 0.0 e 1.0
                val = min(float(update["progress"]), 1.0)
                progress_bar.progress(val)
                status_text.markdown(f"**{update.get('message', '')}**")

            if "result" in update:
                # Cada resultado é um dict com marketplace, link_produto, link_afiliado
                results.append(update["result"])

        progress_bar.progress(1.0)
        status_text.markdown("✅ **Mineração concluída!**")

    except Exception as e:
        status_text.markdown(f"❌ **Erro durante a mineração:** `{e}`")
        st.exception(e)

    # -----------------------------------------------------------------------
    # Exibição dos resultados e botões de download
    # -----------------------------------------------------------------------
    if results:
        # Cria o DataFrame com as colunas padrão do projeto
        df = pd.DataFrame(results, columns=["marketplace", "link_produto", "link_afiliado"])

        st.success(f"🎉 **{len(df)} links coletados** em {df['marketplace'].nunique()} marketplace(s).")

        # Resumo por marketplace
        summary = df.groupby("marketplace").size().reset_index(name="qtd_coletada")
        st.dataframe(summary, use_container_width=True, hide_index=True)

        # Tabela completa (expandida pelo usuário)
        with st.expander("📋 Ver todos os links coletados"):
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### ⬇️ Baixar Planilha")

        # Gera CSV em memória (não salva em disco)
        csv_data = df.to_csv(index=False).encode("utf-8")

        # Gera XLSX em memória usando openpyxl
        xlsx_buffer = io.BytesIO()
        with pd.ExcelWriter(xlsx_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Links Afiliados")
        xlsx_data = xlsx_buffer.getvalue()

        # Botões de download lado a lado
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="⬇️ Baixar CSV",
                data=csv_data,
                file_name="links_afiliados.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with dl_col2:
            st.download_button(
                label="⬇️ Baixar XLSX",
                data=xlsx_data,
                file_name="links_afiliados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    else:
        # Nenhum produto coletado — orienta o usuário
        st.warning(
            "⚠️ **Nenhum link foi coletado.** Possíveis causas:\n\n"
            "- Os marketplaces bloquearam o acesso (captcha / bot detection)\n"
            "- Credenciais ou cookies inválidos ou expirados\n"
            "- Seletores de página desatualizados (layout do site mudou)\n\n"
            "💡 Tente o **Modo Demo** para confirmar que a interface e o download funcionam corretamente."
        )
