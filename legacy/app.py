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
    
    /* Global Reset and Colors */
    :root {{
        --deep-blue: {deep_blue};
        --vibrant-blue: {vibrant_blue};
        --white: {white};
        --black: {black};
        --bg-main: {bg_main};
        --sidebar-bg: {sidebar_bg};
        --text-primary: {text_primary};
        --text-blue: {text_blue};
    }}

    .stApp {{
        background-color: var(--bg-main) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
    }}

    /* Global Typography Visibility */
    p, span, label, div.markdown-text-container, h1, h2, h3, h4, h5, h6, li {{
        color: var(--text-primary) !important;
    }}

    /* Header Hidden (Clean Look) */
    header[data-testid="stHeader"] {{
        visibility: hidden;
        height: 0;
    }}

    /* Sidebar Styling */
    [data-testid="stSidebar"] {{
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--deep-blue) !important;
    }}

    /* Header & Logo Section */
    .header-container {{
        text-align: center;
        padding: 2rem 1rem;
        user-select: none;
    }}
    .logo-container {{
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 800 !important;
        font-size: clamp(3rem, 8vw, 5rem) !important; /* Responsive font size */
        line-height: 1.2 !important; /* Fixed overlapping */
        letter-spacing: -1px !important;
        margin-bottom: 0.5rem !important;
    }}
    .logo-link {{ color: var(--text-blue) !important; }}
    .logo-mineer {{ 
        color: #4facfe !important; 
        background: linear-gradient(135deg, var(--text-blue), #4facfe);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .header-subtitle {{
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: clamp(1rem, 2.5vw, 1.4rem) !important;
        color: var(--text-blue) !important;
        opacity: 0.9;
    }}

    /* Expanders (Marketplaces) - Fix Visibility & Contrast */
    [data-testid="stExpander"] {{
        background-color: rgba(30, 55, 153, 0.05) !important;
        border: 1px solid var(--deep-blue) !important;
        border-radius: 8px !important;
        margin-bottom: 0.5rem !important;
        overflow: hidden;
    }}
    [data-testid="stExpanderHeader"] {{
        background-color: var(--deep-blue) !important;
        padding: 0.5rem 1rem !important;
        transition: background-color 0.3s ease;
    }}
    [data-testid="stExpanderHeader"]:hover {{
        background-color: var(--vibrant-blue) !important;
    }}
    /* Force text white inside header */
    [data-testid="stExpanderHeader"] p, 
    [data-testid="stExpanderHeader"] span, 
    [data-testid="stExpanderHeader"] svg {{
        color: var(--white) !important;
        fill: var(--white) !important;
        font-weight: 700 !important;
    }}
    .streamlit-expanderContent {{
        padding: 1rem !important;
        background-color: transparent !important;
    }}

    /* Form Inputs Styling */
    .stTextInput input, .stTextArea textarea, .stNumberInput input {{
        background-color: var(--white) !important;
        color: var(--black) !important;
        border: 1px solid #ced4da !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        padding: 0.5rem !important;
    }}
    .stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{
        border-color: var(--vibrant-blue) !important;
        box-shadow: 0 0 0 2px rgba(0, 86, 179, 0.25) !important;
    }}

    /* Action Buttons (Generate/Stop) */
    div[data-testid="stButton"] > button {{
        width: 100% !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        padding: 0.75rem 1.5rem !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }}
    /* Primary (Generate) */
    div[data-testid="stButton"] > button[kind="primary"] {{
        background: linear-gradient(135deg, var(--deep-blue), var(--vibrant-blue)) !important;
        color: var(--white) !important;
        border: none !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
    }}
    div[data-testid="stButton"] > button[kind="primary"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15) !important;
        opacity: 0.9;
    }}
    /* Secondary (Stop/Stop) */
    div[data-testid="stButton"] > button[kind="secondary"] {{
        background-color: transparent !important;
        color: #e63946 !important;
        border: 2px solid #e63946 !important;
    }}
    div[data-testid="stButton"] > button[kind="secondary"]:hover {{
        background-color: #e63946 !important;
        color: var(--white) !important;
    }}

    /* Progress and Success Message */
    .stProgress > div > div > div > div {{
        background-color: var(--vibrant-blue) !important;
    }}
    .stSuccess {{
        border-left: 5px solid #28a745 !important;
        background-color: rgba(40, 167, 69, 0.1) !important;
    }}

    /* Dataframe Styling */
    .stDataFrame {{
        border: 1px solid #dee2e6 !important;
        border-radius: 8px !important;
    }}

    /* Footer and Branding removal */
    footer {{ display: none !important; }}
    #MainMenu {{ visibility: hidden; }}

    /* Responsive Spacing */
    .stVerticalBlock {{
        gap: 1rem !important;
    }}

    /* Dark Mode Adjustments */
    @media (prefers-color-scheme: dark) {{
        .stTextInput input, .stTextArea textarea, .stNumberInput input {{
            background-color: #262730 !important;
            color: var(--white) !important;
            border-color: #464855 !important;
        }}
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
    st.markdown(f"<h2 style='color: {text_blue}; text-align: center; font-family: Montserrat;'>⚙️ Configurações</h2>", unsafe_allow_html=True)
    
    qtd_produtos = st.number_input(
        "📦 Quantidade de Produtos",
        min_value=1, max_value=5000, value=5, step=1,
        help="Quantidade mínima de links a serem coletados por marketplace ativo."
    )

    st.markdown("<hr style='border: 0.5px solid rgba(116, 185, 255, 0.2);'>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='color: {text_blue}; text-align: center; font-family: Montserrat;'>🏪 Marketplaces</h3>", unsafe_allow_html=True)

    # A seção "Configurações" e os interruptores foram removidos conforme solicitado.
    demo_mode = st.session_state['is_demo_mode'] # Oculto mas retido p/ back-end no app.py

    # ----------------------------------------------------------------
    # Mercado Livre
    # ----------------------------------------------------------------
    with st.expander("🔵 MERCADO LIVRE", expanded=False):
        ml_active = st.checkbox("Ativar", value=True, key="ml_active_check")
        ml_cookies = st.text_area("Cookies (JSON)", height=100, key="ml_cookies", placeholder='[{"name": "...", "value": "..."}, ...]')
        ml_login_type = "Cookies (JSON)"
        ml_user, ml_pass, ml_tracking = "", "", ""

    # ----------------------------------------------------------------
    # Amazon
    # ----------------------------------------------------------------
    with st.expander("🟠 AMAZON", expanded=False):
        amz_active = st.checkbox("Ativar", value=True, key="amz_active_check")
        amz_tag = st.text_input("Tag Afiliado", value=DEFAULT_AMAZON_TAG, key="amz_tag_input", placeholder="ex: tag-20")
        amz_login_type = st.selectbox("Login", ["Cookies (JSON)", "Credenciais"], key="amz_lt")
        if "Credenciais" in amz_login_type:
            amz_user = st.text_input("E-mail", key="amz_user")
            amz_pass = st.text_input("Senha", type="password", key="amz_pass")
            amz_cookies = ""
        else:
            amz_cookies = st.text_area("Cookies", height=80, key="amz_cookies")
            amz_user, amz_pass = "", ""

    # ----------------------------------------------------------------
    # Shopee
    # ----------------------------------------------------------------
    with st.expander("🔴 SHOPEE", expanded=False):
        shp_active = st.checkbox("Ativar", value=True, key="shp_active_check")
        shp_aff_id = st.text_input("Affiliate ID", value=DEFAULT_SHOPEE_ID, key="shp_aff_id_input")
        shp_login_type = st.selectbox("Login", ["Cookies (JSON)", "Credenciais"], key="shp_lt")
        if "Credenciais" in shp_login_type:
            shp_user = st.text_input("Usuário", key="shp_user")
            shp_pass = st.text_input("Senha", type="password", key="shp_pass")
            shp_cookies = ""
        else:
            shp_cookies = st.text_area("Cookies", height=80, key="shp_cookies")
            shp_user, shp_pass = "", ""

    # ----------------------------------------------------------------
    # Outros
    # ----------------------------------------------------------------
    with st.expander("➕ OUTROS", expanded=False):
        st.info("Marketplaces em desenvolvimento")
        pic_active = st.checkbox("Pichau", value=False)
        kab_active = st.checkbox("Kabum", value=False)
        mag_active = st.checkbox("Magalu", value=False)
        gir_active = st.checkbox("Girafa", value=False)

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

# Sidebar warning moved above buttons
if active_count == 0:
    st.sidebar.warning("⚠️ Selecione um marketplace.")

# Centraliza o botão na tela com largura controlada
st.markdown("<br>", unsafe_allow_html=True)
col_l, col_btn, col_r = st.columns([2, 2, 2])
with col_btn:
    if not st.session_state.mining_active:
        start_btn = st.button(
            "🚀 INICIAR MINERAÇÃO",
            type="primary",
            disabled=(active_count == 0),
            use_container_width=True
        )
    else:
        st.button(
            "🛑 INTERROMPER AGORA",
            type="secondary",
            on_click=stop_mining,
            use_container_width=True
        )
        start_btn = False

# -----------------------------------------------------------------------
# Execução da mineração
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
                "login_type": "Cookies", # ML only works with cookies currently
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
        st.info("🧪 **Modo de Demonstração** — Simulando coleta de dados...")

    # Layout de progresso mais compacto
    prog_col1, prog_col2 = st.columns([3, 1])
    with prog_col1:
        progress_bar = st.progress(0.0)
    with prog_col2:
        status_text = st.empty()

    # Painel de logs detalhados
    log_expander = st.expander("🔍 Detalhes da Execução", expanded=False)
    log_container = log_expander.empty()
    logs = []

    try:
        status_text.markdown("0%")

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
                status_text.markdown(f"**{int(val*100)}%**")
            
            # 2. Trata Logs (Diagnóstico)
            if msg:
                import datetime
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                if not logs or msg != logs[-1].split("] ", 1)[-1]:
                    logs.append(f"[{timestamp}] {msg}")
                    log_content = "\n".join(logs[-15:])
                    log_container.code(log_content, language="text")

            # 3. Trata Resultados
            if "result" in update:
                st.session_state.results.append(update["result"])

        if st.session_state.stop_event.is_set():
            st.warning("🛑 Coleta interrompida pelo usuário.")
        else:
            st.success("✅ Processo concluído com sucesso!")

    except Exception as e:
        st.error(f"❌ Erro crítico: {e}")
    finally:
        st.session_state.mining_active = False
        # st.rerun() # Opcional: força a remoção do botão Stop imediatamente

# -----------------------------------------------------------------------
# Resultados e Downloads
# -----------------------------------------------------------------------
results = st.session_state.results

if results:
    # Cria o DataFrame com as colunas padrão do projeto
    df = pd.DataFrame(results, columns=["marketplace", "link_produto", "link_afiliado"])
    
    st.markdown("---")
    res_col1, res_col2 = st.columns([1, 2])
    
    with res_col1:
        st.markdown("### 📊 Resumo")
        summary = df.groupby("marketplace").size().reset_index(name="Qtd")
        st.dataframe(summary, use_container_width=True, hide_index=True)

    with res_col2:
        st.markdown("### ⬇️ Exportar Dados")
        csv_data = df.to_csv(index=False).encode("utf-8")
        xlsx_buffer = io.BytesIO()
        with pd.ExcelWriter(xlsx_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Links")
        xlsx_data = xlsx_buffer.getvalue()

        dl_col1, dl_col2 = st.columns(2)
        dl_col1.download_button("📂 Baixar CSV", csv_data, "links.csv", "text/csv", use_container_width=True)
        dl_col2.download_button("📊 Baixar XLSX", xlsx_data, "links.xlsx", "application/vnd.ms-excel", use_container_width=True)

    with st.expander("📋 Visualizar Links Coletados", expanded=True):
        st.dataframe(df, use_container_width=True, hide_index=True)

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
