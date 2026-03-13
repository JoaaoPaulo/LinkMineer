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

# Removemos os toggles da sidebar aqui, pois eles foram movidos para a área central (Controles Superiores)
# [PONTO 3 e 9]

if 'is_dark_mode' not in st.session_state:
    st.session_state['is_dark_mode'] = False
if 'is_demo_mode' not in st.session_state:
    st.session_state['is_demo_mode'] = False

# Paleta de Cores LinkMineer Premium
deep_blue = "#1e3799"
vibrant_blue = "#0056b3"
white = "#ffffff"
black = "#000000"
is_dark_mode = st.session_state['is_dark_mode']
text_primary = black if not is_dark_mode else white
bg_main = white if not is_dark_mode else "#0e1117"
sidebar_bg = "#f0f2f6" if not is_dark_mode else "#161b22"
text_blue = deep_blue if not is_dark_mode else "#74b9ff" # Azul claro para textos em modo escuro

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&family=Inter:wght@400;600;700&display=swap');
    
    /* Reset e Fundo Global */
    .stApp {{
        background-color: {bg_main} !important;
        color: {text_primary} !important;
        font-family: 'Inter', sans-serif !important;
    }}

    /* REFORÇO DE VISIBILIDADE (Sem usar * para preservar botões) */
    p, span, label, div.markdown-text-container, h1, h2, h3, h4, h5, h6, li {{
        color: {text_primary} !important;
    }}

    /* Sidebar - Manter Toggle visível */
    [data-testid="stSidebar"] {{
        background-color: {sidebar_bg} !important;
        border-right: 2px solid {deep_blue} !important;
    }}
    
    /* Expander (+/-) e Labels dos marketplaces */
    [data-testid="stExpanderHeader"] {{
        background-color: {deep_blue} !important;
        border-radius: 4px !important;
        padding: 5px 10px !important;
        margin-bottom: 2px !important;
    }}
    [data-testid="stExpanderHeader"] * {{
        color: {white} !important; /* Texto do título e icone +/- em branco */
        font-weight: 700 !important;
    }}

    /* [PONTO 8] Tira a barra preta de cima da tela */
    header[data-testid="stHeader"] {{
        background-color: transparent !important;
        border-bottom: none !important;
        box-shadow: none !important;
        color: transparent !important;
    }}
    .stApp > header {{ display: none !important; }}

    /* CAIXAS DE INFORMAÇÕES (TEXTO/NUMERO) */
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div, .stNumberInput input {{
        background-color: #f0f8ff !important; /* Azul claro (aliceblue) */
        color: {deep_blue} !important; /* Texto interno azul escuro */
        caret-color: {deep_blue} !important; /* Barrinha de escrita visível */
        border: 2px solid {deep_blue} !important; /* Borda azul escuro */
        border-radius: 6px !important;
        font-weight: 600 !important;
    }}
    
    /* BOTOES +/- DO NUMBER INPUT (Azul Escuro com Texto Branco) */
    [data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"],
    [data-testid="stNumberInput"] button {{
        background-color: {deep_blue} !important;
        color: {white} !important;
        border-radius: 4px !important;
    }}
    [data-testid="stNumberInputStepUp"]:hover, [data-testid="stNumberInputStepDown"]:hover,
    [data-testid="stNumberInput"] button:hover {{
        background-color: {vibrant_blue} !important;
        color: {white} !important;
        opacity: 0.9 !important;
    }}
    
    /* Garantindo que o ícone do botão +/- seja branco */
    [data-testid="stNumberInputStepUp"] svg, [data-testid="stNumberInputStepDown"] svg,
    [data-testid="stNumberInput"] button svg {{
        fill: {white} !important;
        color: {white} !important;
    }}

    .stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{
        border-color: {vibrant_blue} !important;
        box-shadow: 0 0 5px {vibrant_blue} !important;
    }}

    /* [PONTO 6] Título do LinkMineer (Dark Blue + Light Blue) */
    .header-container {{
        text-align: center;
        padding: 3rem 1rem 1rem 1rem;
    }}
    .logo-container {{
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 800 !important;
        font-size: 6rem !important;
        margin-bottom: 0px !important;
        line-height: 0.9 !important;
        letter-spacing: -2px !important;
    }}
    .logo-link {{ color: {text_blue} !important; }}
    .logo-mineer {{ color: #4facfe !important; /* Azul mais claro */ }}

    .header-subtitle {{
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 1.8rem !important;
        color: {text_blue} !important;
        margin-top: 5px !important;
    }}

    /* [PONTO 1 e 5] BOTOES BLUE SEM PRETO / Gerar Planilha Visível */
    div[data-testid="stButton"] > button[kind="primary"], 
    div[data-testid="stDownloadButton"] > button {{
        background-color: {white} !important;
        color: {deep_blue} !important;
        border: 2px solid {deep_blue} !important;
        font-size: 1.2rem !important;
        font-weight: 800 !important;
        border-radius: 6px !important;
        padding: 0.8rem 2rem !important;
        width: 100% !important;
        transition: all 0.2s ease !important;
    }}
    div[data-testid="stButton"] > button[kind="primary"]:hover,
    div[data-testid="stDownloadButton"] > button:hover {{
        background-color: {deep_blue} !important;
        color: {white} !important;
        opacity: 0.95 !important;
    }}

    /* Botão de Parar (Vermelho Leve) */
    div[data-testid="stButton"] > button[kind="secondary"] {{
        background-color: transparent !important;
        color: #d63031 !important;
        border: 2px solid #d63031 !important;
        font-weight: 700 !important;
        border-radius: 6px !important;
        width: 100% !important;
        transition: all 0.2s ease !important;
    }}
    div[data-testid="stButton"] > button[kind="secondary"]:hover {{
        background-color: #d63031 !important;
        color: {white} !important;
    }}

    /* Títulos de Expander - Aba Transparente, Borda Azul quando clicado/hover */
    [data-testid="stExpander"] {{
        background-color: transparent !important;
        border: 1px solid #d1d5db !important;
        border-radius: 6px !important;
        transition: all 0.2s ease;
    }}
    [data-testid="stExpander"]:hover, [data-testid="stExpander"]:focus-within {{
        border: 2px solid {deep_blue} !important;
        background-color: transparent !important;
    }}
    
    /* ZERA FUNDO DO HEADER DO EXPANDER EM TODAS CLASSES DO STREAMLIT */
    [data-testid="stExpanderHeader"],
    [data-testid="stExpanderHeader"]:hover,
    [data-testid="stExpanderHeader"]:active,
    [data-testid="stExpanderHeader"]:focus,
    [data-testid="stExpanderHeader"]:focus-within,
    .streamlit-expanderHeader,
    .streamlit-expanderHeader:hover,
    div[role="button"][aria-expanded],
    summary, summary:hover, summary:focus, summary:active {{
        background-color: transparent !important; /* Força transparência contra o preto do back */
    }}
    
    [data-testid="stExpanderHeader"] p, .streamlit-expanderHeader div, summary p, summary span {{
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        color: {text_blue} !important; /* Adapta ao dark mode */
    }}
    [data-testid="stExpanderHeader"] svg, .streamlit-expanderHeader svg, summary svg {{
        color: {text_blue} !important; 
    }}
    [data-testid="stExpanderDetails"], .streamlit-expanderContent, details {{
        background-color: transparent !important;
    }}

    /* Ocultar elementos sem quebrar o Sidebar Toggle */
    footer {{visibility: hidden;}}
    
    /* [PONTO 11] Progress e Resultados com tema Azul */
    .stProgress > div > div > div > div {{
        background-color: {vibrant_blue} !important;
    }}
    .stSuccess {{
        background-color: #e3f2fd !important;
        color: {deep_blue} !important;
        border-left-color: {deep_blue} !important;
    }}
    .stDataFrame {{
        border: 1px solid {deep_blue} !important;
        border-radius: 8px !important;
    }}
    
    /* Espaçamento Reduzido (Próximo) */

    .stVerticalBlock {{
        gap: 0.5rem !important;
    }}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------
# Cabeçalho da página (Centralizado)
# -----------------------------------------------------------------------
st.markdown("""
<div class="header-container">
    <div class="logo-container">
        <span class="logo-link">Link</span><span class="logo-mineer">Mineer</span>
    </div>
    <div class="header-subtitle">Minerador inteligente de links de afiliados • Multi-Marketplace</div>
</div>
""", unsafe_allow_html=True)

st.divider()

# -----------------------------------------------------------------------
# Continuação da Barra lateral – Marketplaces e Configurações
# -----------------------------------------------------------------------
with st.sidebar:
    # A seção "Configurações" e os interruptores foram removidos conforme solicitado.
    demo_mode = st.session_state['is_demo_mode'] # Oculto mas retido p/ back-end no app.py

    qtd_produtos = st.number_input(
        "🔢 Quantidade Mínima Desejada",
        min_value=1, max_value=5000, value=5, step=1
    )

    # Espaço entre config e marketplaces
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='color: {text_blue}; text-align: center;'>Marketplaces</h3>", unsafe_allow_html=True)

    # ----------------------------------------------------------------
    # Mercado Livre
    # ----------------------------------------------------------------
    with st.expander("MERCADO LIVRE", expanded=False):
        ml_active = st.checkbox("Ativar Mercado Livre", value=True, key="ml_active_check")
        ml_cookies = st.text_area("Cookies (JSON array)", height=100, key="ml_cookies")
        ml_login_type = "Cookies (JSON)"
        ml_user, ml_pass, ml_tracking = "", "", ""

    # ----------------------------------------------------------------
    # Amazon
    # ----------------------------------------------------------------
    with st.expander("AMAZON", expanded=False):
        amz_active = st.checkbox("Ativar Amazon", value=True, key="amz_active_check")
        amz_tag = st.text_input("Tag de afiliado (AMZ)", value=DEFAULT_AMAZON_TAG, key="amz_tag_input")
        amz_login_type = st.selectbox("Autenticação AMZ", ["Cookies (JSON)", "Credenciais"], key="amz_lt")
        if "Credenciais" in amz_login_type:
            amz_user = st.text_input("Usuário AMZ", key="amz_user")
            amz_pass = st.text_input("Senha AMZ", type="password", key="amz_pass")
            amz_cookies = ""
        else:
            amz_cookies = st.text_area("Cookies AMZ", height=80, key="amz_cookies")
            amz_user, amz_pass = "", ""

    # ----------------------------------------------------------------
    # Shopee
    # ----------------------------------------------------------------
    with st.expander("SHOPEE", expanded=False):
        shp_active = st.checkbox("Ativar Shopee", value=True, key="shp_active_check")
        shp_aff_id = st.text_input("Affiliate ID (SHP)", value=DEFAULT_SHOPEE_ID, key="shp_aff_id_input")
        shp_login_type = st.selectbox("Autenticação SHP", ["Cookies (JSON)", "Credenciais"], key="shp_lt")
        if "Credenciais" in shp_login_type:
            shp_user = st.text_input("Usuário SHP", key="shp_user")
            shp_pass = st.text_input("Senha SHP", type="password", key="shp_pass")
            shp_cookies = ""
        else:
            shp_cookies = st.text_area("Cookies SHP", height=80, key="shp_cookies")
            shp_user, shp_pass = "", ""

    # ----------------------------------------------------------------
    # Outros
    # ----------------------------------------------------------------
    with st.expander("PICHAU", expanded=False):
        pic_active = st.checkbox("Ativar Pichau", value=False)
        
    with st.expander("KABUM", expanded=False):
        kab_active = st.checkbox("Ativar Kabum", value=False)

    with st.expander("MAGALU", expanded=False):
        mag_active = st.checkbox("Ativar Magalu", value=False)

    with st.expander("GIRAFA", expanded=False):
        gir_active = st.checkbox("Ativar Girafa", value=False)

# -----------------------------------------------------------------------
# Gerenciamento de Estado
# -----------------------------------------------------------------------
if "results" not in st.session_state:
    st.session_state.results = []
if "mining_active" not in st.session_state:
    st.session_state.mining_active = False
if "mining_started" not in st.session_state:
    st.session_state.mining_started = False
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
    st.session_state.mining_started = True
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
    # Só mostra o alerta de erro se a mineração já tiver começado alguma vez
    if st.session_state.mining_started:
        st.warning(
            "⚠️ **Nenhum link foi coletado.** Possíveis causas:\n\n"
            "- Os marketplaces bloquearam o acesso (captcha / bot detection)\n"
            "- Credenciais ou cookies inválidos ou expirados\n"
            "- Seletores de página desatualizados (layout do site mudou)\n\n"
            "💡 Tente o **Modo Demo** para confirmar que a interface e o download funcionam corretamente."
        )
