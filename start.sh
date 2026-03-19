#!/bin/bash
# ============================================================
# start.sh – Script de inicialização para Railway
# Executado automaticamente pelo Procfile no deploy
# ============================================================

set -e  # Para o script se qualquer comando falhar

echo ">>> [1/3] Instalando dependências de sistema do Playwright..."
# playwright install-deps pode falhar se não houver permissão de root (comum no Railway).
# Usamos '|| true' para que o deploy continue caso as libs já existam.
playwright install-deps chromium || true

echo ">>> [2/3] Instalando o Chromium..."
playwright install chromium

echo ">>> [3/3] Iniciando LinkMineer na porta $PORT..."
# $PORT é injetada automaticamente pelo Railway
# Executa o novo ponto de entrada modular
python run.py