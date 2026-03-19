import streamlit as st

def get_theme_colors():
    is_dark_mode = st.session_state.get('is_dark_mode', False)
    return {
        "deep_blue": "#1e3799",
        "vibrant_blue": "#0056b3",
        "white": "#ffffff",
        "black": "#000000",
        "text_primary": "#000000" if not is_dark_mode else "#ffffff",
        "bg_main": "#ffffff" if not is_dark_mode else "#0e1117",
        "sidebar_bg": "#f0f2f6" if not is_dark_mode else "#161b22",
        "text_blue": "#1e3799" if not is_dark_mode else "#74b9ff"
    }
