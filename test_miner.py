import threading
import queue
import time
from miner import run_mining

# Usar os mesmos cookies/dados do app global (Configuração Simples para Teste)
# Vamos rodar em mock mode p pular abrir a UI
config = {
    "marketplaces": {
        "Mercado Livre": {
            "active": True,
            "cookies": "[]" # Inserir cookies válidos se for validar login real. Usaremos dummy aqui ou só testar a compilação
        },
        "Amazon": {"active": False},
        "Shopee": {"active": False},
        "Pichau": {"active": False},
        "Kabum": {"active": False},
        "Magalu": {"active": False},
        "Girafa": {"active": False}
    },
    "qtd_produtos": 2,
    "demo_mode": False,
    "stop_event": threading.Event()
}

print("Iniciando rotina de teste do motor veloz...")
miner_gen = run_mining(config)
try:
    for item in miner_gen:
        print(f"Recebido: {item}")
except Exception as e:
    print(f"Erro no teste: {e}")
print("Teste concluído.")
