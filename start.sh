#!/bin/bash
# Instala Chromium para Playwright
playwright install chromium

# Roda o Streamlit na porta que o Railway fornece
streamlit run app.py --server.port $PORT --server.address 0.0.0.0