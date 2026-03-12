#!/bin/bash
# ============================================================
# start.sh – Script de inicialização para Railway
# Executado automaticamente pelo Procfile no deploy
# ============================================================

set -e  # Para o script se qualquer comando falhar

echo ">>> [1/3] Instalando dependências de sistema do Playwright..."
# playwright install-deps instala as libs nativas do Linux
# necessárias para o Chromium funcionar em ambiente headless
playwright install-deps chromium

echo ">>> [2/3] Instalando o Chromium..."
playwright install chromium

echo ">>> [3/3] Iniciando Streamlit na porta $PORT..."
# $PORT é injetado automaticamente pelo Railway
# --server.address 0.0.0.0 garante que o Railway consiga rotear o tráfego
streamlit run app.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false