import streamlit as st
from frontend.theme import get_theme_colors

def apply_custom_css():
    colors = get_theme_colors()
    is_dark_mode = st.session_state.get('is_dark_mode', False)
    
    bg_main = colors["bg_main"]
    text_primary = colors["text_primary"]
    deep_blue = colors["deep_blue"]
    sidebar_bg = colors["sidebar_bg"]
    white = colors["white"]
    vibrant_blue = colors["vibrant_blue"]
    text_blue = colors["text_blue"]

    st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
    
    :root {{
        --glass-bg: {{ 'rgba(255, 255, 255, 0.7)' if not is_dark_mode else 'rgba(22, 27, 34, 0.7)' }};
        --glass-border: {{ 'rgba(255, 255, 255, 0.5)' if not is_dark_mode else 'rgba(255, 255, 255, 0.05)' }};
        --shadow-soft: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
        --gradient-primary: linear-gradient(135deg, {vibrant_blue} 0%, {deep_blue} 100%);
        --gradient-hover: linear-gradient(135deg, {deep_blue} 0%, #0a1f6a 100%);
    }}

    /* Reset e Fundo Global */
    .stApp {{
        background-color: {bg_main} !important;
        background-image: {{ 'radial-gradient(circle at 15% 50%, rgba(79, 172, 254, 0.08), transparent 25%), radial-gradient(circle at 85% 30%, rgba(30, 55, 153, 0.08), transparent 25%)' if not is_dark_mode else 'radial-gradient(circle at 15% 50%, rgba(79, 172, 254, 0.03), transparent 25%), radial-gradient(circle at 85% 30%, rgba(30, 55, 153, 0.03), transparent 25%)' }};
        color: {text_primary} !important;
        font-family: 'Inter', sans-serif !important;
    }}

    /* REFORÇO DE VISIBILIDADE */
    p, span, label, div.markdown-text-container, h1, h2, h3, h4, h5, h6, li {{
        color: {text_primary} !important;
        font-family: 'Inter', sans-serif;
    }}

    /* Sidebar - Manter Toggle visível */
    [data-testid="stSidebar"] {{
        background: var(--glass-bg) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border-right: 1px solid var(--glass-border) !important;
        box-shadow: 4px 0 24px rgba(0,0,0,0.02) !important;
    }}
    
    /* Expander (+/-) e Labels dos marketplaces */
    [data-testid="stExpander"] {{
        background: var(--glass-bg) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
        box-shadow: var(--shadow-soft) !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
        margin-bottom: 12px !important;
        overflow: hidden;
    }}
    
    [data-testid="stExpander"]:hover, [data-testid="stExpander"]:focus-within {{
        transform: translateY(-2px);
        box-shadow: 0 12px 40px 0 rgba(31, 38, 135, 0.12) !important;
        border: 1px solid rgba(79, 172, 254, 0.3) !important;
    }}

    [data-testid="stExpanderHeader"] {{
        background: transparent !important;
        padding: 12px 16px !important;
        border-bottom: 1px solid transparent;
        transition: all 0.3s ease;
    }}
    
    [data-testid="stExpanderHeader"]:hover {{
        background: rgba(79, 172, 254, 0.05) !important;
    }}

    [data-testid="stExpanderHeader"] p, summary p, summary span {{
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        color: {text_blue} !important;
        letter-spacing: 0.5px;
    }}
    
    [data-testid="stExpanderHeader"] svg {{
        color: {text_blue} !important; 
    }}

    /* Tira a barra preta de cima da tela */
    header[data-testid="stHeader"] {{
        background-color: transparent !important;
        border-bottom: none !important;
        box-shadow: none !important;
    }}
    .stApp > header {{ display: none !important; }}

    /* CAIXAS DE INFORMAÇÕES (TEXTO/NUMERO) */
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div, .stNumberInput input {{
        background-color: {{ 'rgba(255,255,255,0.7)' if not is_dark_mode else 'rgba(0,0,0,0.2)' }} !important;
        backdrop-filter: blur(8px) !important;
        color: {text_primary} !important;
        border: 1.5px solid {{ 'rgba(30, 55, 153, 0.2)' if not is_dark_mode else 'rgba(116, 185, 255, 0.2)' }} !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.01) !important;
    }}
    
    .stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus, .stSelectbox > div > div:focus {{
        border-color: {vibrant_blue} !important;
        box-shadow: 0 0 0 3px rgba(79, 172, 254, 0.25) !important;
        transform: translateY(-1px);
    }}

    /* BOTOES +/- DO NUMBER INPUT */
    [data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"] {{
        background: var(--glass-bg) !important;
        color: {text_primary} !important;
        border-radius: 6px !important;
        transition: all 0.2s ease !important;
    }}
    [data-testid="stNumberInputStepUp"]:hover, [data-testid="stNumberInputStepDown"]:hover {{
        background: var(--gradient-primary) !important;
    }}
    [data-testid="stNumberInputStepUp"]:hover svg, [data-testid="stNumberInputStepDown"]:hover svg {{
        fill: white !important;
        color: white !important;
    }}

    /* Título do LinkMineer (Modernizado) */
    .header-container {{
        text-align: center;
        padding: 4rem 1rem 2rem 1rem;
        animation: fadeInDown 0.8s cubic-bezier(0.2, 0.8, 0.2, 1);
    }}
    @keyframes fadeInDown {{
        from {{ opacity: 0; transform: translateY(-20px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    .logo-container {{
        font-family: 'Outfit', sans-serif !important;
        font-weight: 800 !important;
        font-size: 5rem !important;
        margin-bottom: 0px !important;
        line-height: 1 !important;
        letter-spacing: -1.5px !important;
        background: linear-gradient(135deg, {deep_blue} 0%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0px 4px 12px rgba(79, 172, 254, 0.2));
    }}

    .header-subtitle {{
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 1.2rem !important;
        color: {text_blue} !important;
        margin-top: 10px !important;
        opacity: 0.9;
        letter-spacing: 0.3px;
    }}

    /* BOTOES PRINCIPAIS */
    div[data-testid="stButton"] > button[kind="primary"], 
    div[data-testid="stDownloadButton"] > button {{
        background: var(--gradient-primary) !important;
        color: white !important;
        border: none !important;
        font-size: 1.15rem !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        padding: 0.8rem 2rem !important;
        width: 100% !important;
        transition: all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1) !important;
        box-shadow: 0 4px 15px rgba(0, 86, 179, 0.3) !important;
        position: relative;
        overflow: hidden;
    }}
    
    div[data-testid="stButton"] > button[kind="primary"]:hover,
    div[data-testid="stDownloadButton"] > button:hover {{
        background: var(--gradient-hover) !important;
        transform: translateY(-2px) scale(1.01) !important;
        box-shadow: 0 8px 25px rgba(0, 86, 179, 0.4) !important;
    }}
    
    div[data-testid="stButton"] > button[kind="primary"]:active,
    div[data-testid="stDownloadButton"] > button:active {{
        transform: translateY(1px) scale(0.98) !important;
    }}

    /* Botão de Parar (Vermelho Premium) */
    div[data-testid="stButton"] > button[kind="secondary"] {{
        background: transparent !important;
        color: #ff4757 !important;
        border: 2px solid rgba(255, 71, 87, 0.4) !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        border-radius: 12px !important;
        width: 100% !important;
        transition: all 0.3s ease !important;
    }}
    div[data-testid="stButton"] > button[kind="secondary"]:hover {{
        background: rgba(255, 71, 87, 0.1) !important;
        border-color: #ff4757 !important;
        box-shadow: 0 4px 15px rgba(255, 71, 87, 0.2) !important;
        transform: translateY(-1px);
    }}

    /* Progress e Resultados */
    .stProgress > div > div > div > div {{
        background: var(--gradient-primary) !important;
        border-radius: 10px !important;
    }}
    .stSuccess, .stInfo, .stWarning, .stError, .stException {{
        background: var(--glass-bg) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
        box-shadow: var(--shadow-soft) !important;
        color: {text_primary} !important;
    }}
    .stDataFrame {{
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
        overflow: hidden;
        box-shadow: var(--shadow-soft) !important;
    }}
    
    /* ZERA FUNDO DO HEADER DO EXPANDER EM TODAS CLASSES DO STREAMLIT */
    .streamlit-expanderHeader, div[role="button"][aria-expanded], summary {{
        background-color: transparent !important; 
    }}

    footer {{visibility: hidden;}}
    .stVerticalBlock {{ gap: 0.8rem !important; }}
</style>
""", unsafe_allow_html=True)
