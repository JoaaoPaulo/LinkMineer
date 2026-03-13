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
import pandas as pd
import threading
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
    /* Importando fonte moderna */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background: #0d1117;
    }

    /* Cabeçalho */
    h1 { 
        font-weight: 700 !important; 
        background: linear-gradient(90deg, #fa8231, #e84393);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0 !important;
    }
    
    .main-subtitle {
        color: #8b949e;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    /* Botão Principal - Primário */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(90deg, #fa8231, #e84393);
        border: none;
        color: white;
        font-size: 1.1rem;
        font-weight: 600;
        border-radius: 12px;
        padding: 0.75rem 2rem;
        width: 100%;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(232, 67, 147, 0.3);
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(232, 67, 147, 0.4);
        opacity: 0.9;
    }

    /* Botão Parar - Secundário */
    div[data-testid="stButton"] > button[kind="secondary"] {
        background: #21262d;
        border: 1px solid #f85149;
        color: #f85149;
        font-weight: 600;
        border-radius: 12px;
        width: 100%;
        transition: all 0.3s ease;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover {
        background: #f85149;
        color: white;
    }

    /* Sidebar */
    [data-testid="stSidebar"] { background: #161b22; border-right: 1px solid #30363d; }
    
    /* Expanders */
    .stExpander {
        border: 1px solid #30363d !important;
        border-radius: 12px !important;
        background: #0d1117 !important;
        margin-bottom: 10px !important;
    }

    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stNumberInput input {
        background-color: #0d1117 !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
    }

    /* Status alerts */
    .stAlert {
        border-radius: 12px !important;
        border: 1px solid #30363d !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------
# Cabeçalho da página
# -----------------------------------------------------------------------
col_icon, col_title = st.columns([1, 10])
with col_icon:
    st.markdown("<h2 style='text-align: right; margin-top: 5px;'>⛏️</h2>", unsafe_allow_html=True)
with col_title:
    st.markdown("<h1>LinkMineer</h1>", unsafe_allow_html=True)
    st.markdown("<p class='main-subtitle'>Mineração ultra-rápida de links de afiliados</p>", unsafe_allow_html=True)

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
        min_value=1, max_value=5000, value=5, step=1,
        help="Define quantos produtos serão coletados em cada marketplace ativo."
    )

    st.markdown("---")

    # Initialize marketplace active states
    ml_active = True
    amz_active = True
    shp_active = True
    pic_active = False
    kab_active = False
    mag_active = False
    gir_active = False

    # ----------------------------------------------------------------
    # Mercado Livre (Expandível)
    # ----------------------------------------------------------------
    with st.expander("🛒 Mercado Livre", expanded=ml_active):
        ml_active = st.checkbox("Ativar Mercado Livre", value=True, key="ml_active_check")
        st.info("⚠️ O ML exige **Cookies (JSON)** para acessar o Hub de Afiliados.")
        ml_cookies = st.text_area("Cookies (JSON array)", height=100, key="ml_cookies", placeholder='[{"name": "...", "value": "..."}, ...]')
        ml_login_type = "Cookies (JSON)"
        ml_user, ml_pass, ml_tracking = "", "", ""

    # ----------------------------------------------------------------
    # Amazon (Expandível)
    # ----------------------------------------------------------------
    with st.expander("📦 Amazon", expanded=amz_active):
        amz_active = st.checkbox("Ativar Amazon", value=True, key="amz_active_check")
        amz_tag = st.text_input(
            "Tag de afiliado (AMZ)",
            value=DEFAULT_AMAZON_TAG,
            placeholder="ex: seunome-20",
            key="amz_tag_input"
        )
        amz_login_type = st.selectbox("Autenticação AMZ", ["Cookies (JSON)", "Credenciais"], key="amz_lt")
        if "Credenciais" in amz_login_type:
            amz_user = st.text_input("Usuário / E-mail Amazon", key="amz_user")
            amz_pass = st.text_input("Senha Amazon", type="password", key="amz_pass")
            amz_cookies = ""
        else:
            amz_cookies = st.text_area("Cookies Amazon (JSON array)", height=80, key="amz_cookies")
            amz_user, amz_pass = "", ""

    # ----------------------------------------------------------------
    # Shopee (Expandível)
    # ----------------------------------------------------------------
    with st.expander("🛍️ Shopee", expanded=shp_active):
        shp_active = st.checkbox("Ativar Shopee", value=True, key="shp_active_check")
        shp_aff_id = st.text_input(
            "Affiliate ID (SHP)",
            value=DEFAULT_SHOPEE_ID,
            placeholder="ex: 123456789",
            key="shp_aff_id_input"
        )
        shp_login_type = st.selectbox("Autenticação SHP", ["Cookies (JSON)", "Credenciais"], key="shp_lt")
        if "Credenciais" in shp_login_type:
            shp_user = st.text_input("Usuário / E-mail Shopee", key="shp_user")
            shp_pass = st.text_input("Senha Shopee", type="password", key="shp_pass")
            shp_cookies = ""
        else:
            shp_cookies = st.text_area("Cookies Shopee (JSON array)", height=80, key="shp_cookies")
            shp_user, shp_pass = "", ""

    # ----------------------------------------------------------------
    # Outros Marketplaces (Stubs)
    # ----------------------------------------------------------------
    st.markdown("### ➕ Outros (Em breve)")
    
    with st.expander("🔵 Pichau", expanded=False):
        pic_active = st.checkbox("Ativar Pichau", value=False)
        st.caption("Configurações em breve...")
        
    with st.expander("🟠 Kabum", expanded=False):
        kab_active = st.checkbox("Ativar Kabum", value=False)
        st.caption("Configurações em breve...")

    with st.expander("🔴 Magalu", expanded=False):
        mag_active = st.checkbox("Ativar Magalu", value=False)
        st.caption("Configurações em breve...")

    with st.expander("🦒 Girafa", expanded=False):
        gir_active = st.checkbox("Ativar Girafa", value=False)
        st.caption("Configurações em breve...")

# -----------------------------------------------------------------------
# Gerenciamento de Estado
# -----------------------------------------------------------------------
if "results" not in st.session_state:
    st.session_state.results = []
if "mining_active" not in st.session_state:
    st.session_state.mining_active = False
if "stop_event" not in st.session_state:
    st.session_state.stop_event = threading.Event()

def stop_mining():
    if st.session_state.stop_event:
        st.session_state.stop_event.set()
    st.session_state.mining_active = False
    st.toast("🛑 Interrupção solicitada!")

# -----------------------------------------------------------------------
# Área principal – Botão de ação
# -----------------------------------------------------------------------
active_count = sum([ml_active, amz_active, shp_active, pic_active, kab_active, mag_active, gir_active])

if active_count == 0:
    st.warning("⚠️ Selecione pelo menos um marketplace na barra lateral.")

# Centraliza o botão na tela
col_left, col_center, col_right = st.columns([3, 2, 3])
with col_center:
    if not st.session_state.mining_active:
        start_btn = st.button(
            "🚀 Gerar Planilha",
            type="primary",
            disabled=(active_count == 0),
            use_container_width=True
        )
    else:
        st.button(
            "🛑 Parar Geração",
            type="secondary",
            on_click=stop_mining,
            use_container_width=True
        )
        start_btn = False

# -----------------------------------------------------------------------
# Execução da mineração ao clicar no botão
# -----------------------------------------------------------------------
if start_btn:
    # Reset de estado para nova mineração
    st.session_state.results = []
    st.session_state.mining_active = True
    st.session_state.stop_event.clear()

    # Monta o dicionário de configuração a partir dos campos da sidebar
    config = {
        "demo_mode": demo_mode,
        "qtd_produtos": int(qtd_produtos),
        "stop_event": st.session_state.stop_event, # Passa o evento
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
            "Pichau": {"active": pic_active},
            "Kabum": {"active": kab_active},
            "Magalu": {"active": mag_active},
            "Girafa": {"active": gir_active},
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

    # Painel de logs detalhados
    log_expander = st.expander("🔍 Ver Logs de Execução (Diagnóstico)", expanded=True)
    log_container = log_expander.empty()
    logs = []

    try:
        status_text.markdown("**Iniciando mineração...**")

        # Consome o generator do miner.py, processando cada update em tempo real
        for update in run_mining(config):
            # Verifica se foi parado (para sair do loop do generator)
            if st.session_state.stop_event.is_set():
                break

            msg = update.get('message', '')
            
            # 1. Trata Progresso
            if "progress" in update:
                val = min(float(update["progress"]), 1.0)
                progress_bar.progress(val)
                if msg:
                    status_text.markdown(f"**{msg}**")
            
            # 2. Trata Logs (Diagnóstico)
            if msg:
                import datetime
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                if not logs or msg != logs[-1].split("] ", 1)[-1]:
                    logs.append(f"[{timestamp}] {msg}")
                    log_content = "\n".join(logs[-25:])
                    log_container.code(log_content, language="text")

            # 3. Trata Resultados
            if "result" in update:
                st.session_state.results.append(update["result"])

        if st.session_state.stop_event.is_set():
            status_text.markdown("🛑 **Mineração parada pelo usuário!**")
            progress_bar.progress(1.0)
        else:
            progress_bar.progress(1.0)
            status_text.markdown("✅ **Mineração concluída!**")

    except Exception as e:
        status_text.markdown(f"❌ **Erro durante a mineração:** `{e}`")
        st.exception(e)
    finally:
        st.session_state.mining_active = False
        # st.rerun() # Opcional: força a remoção do botão Stop imediatamente

# -----------------------------------------------------------------------
# Exibição dos resultados e botões de download
# -----------------------------------------------------------------------
results = st.session_state.results

if results:
    # Cria o DataFrame com as colunas padrão do projeto
    df = pd.DataFrame(results, columns=["marketplace", "link_produto", "link_afiliado"])

    st.success(f"🎉 **{len(df)} links coletados** em {df['marketplace'].nunique()} marketplace(s).")

    # Resumo por marketplace
    summary = df.groupby("marketplace").size().reset_index(name="qtd_coletada")
    st.dataframe(summary, width="stretch", hide_index=True)

    # Tabela completa (expandida pelo usuário)
    with st.expander("📋 Ver todos os links coletados"):
        st.dataframe(df, width="stretch", hide_index=True)

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
            width="stretch",
        )
    with dl_col2:
        st.download_button(
            label="⬇️ Baixar XLSX",
            data=xlsx_data,
            file_name="links_afiliados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
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
