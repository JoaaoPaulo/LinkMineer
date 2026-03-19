import queue
import threading
import time
from typing import Dict, Any
from playwright.sync_api import sync_playwright

from src.backend.config.settings import settings
from src.backend.miners.amazon import AmazonMiner
from src.backend.miners.mercadolivre import MercadoLivreMiner
from src.backend.miners.shopee import ShopeeMiner
from src.backend.miners.stubs import PichauMiner, KabumMiner, MagaluMiner, GirafaMiner

class MiningEngine:
    """Orchestrates the execution of multiple miners in a controlled environment."""
    
    MINER_MAP = {
        "Amazon": AmazonMiner,
        "Mercado Livre": MercadoLivreMiner,
        "Shopee": ShopeeMiner,
        "Pichau": PichauMiner,
        "Kabum": KabumMiner,
        "Magalu": MagaluMiner,
        "Girafa": GirafaMiner
    }

    def __init__(self, config: Dict[str, Any], log_queue: queue.Queue):
        self.config = config
        self.log_queue = log_queue
        self.stop_event = config.get("stop_event", threading.Event())

    def _log(self, message: str, progress: float = None):
        data = {"type": "update", "message": message}
        if progress is not None:
            data["progress"] = progress
        self.log_queue.put(data)

    def run(self):
        """Starts the mining process in a separate thread."""
        thread = threading.Thread(target=self._execute, daemon=True)
        thread.start()
        return thread

    def _execute(self):
        """Internal execution logic using Playwright."""
        try:
            if self.config.get("demo_mode"):
                self._run_demo()
                return

            with sync_playwright() as p:
                self._log("Iniciando navegador Playwright...", 0.05)
                browser = p.chromium.launch(
                    headless=settings.PLAYWRIGHT_HEADLESS,
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    permissions=["clipboard-read", "clipboard-write"]
                )
                page = context.new_page()

                # Identify active marketplaces
                active_marketplaces = [
                    m for m in self.MINER_MAP.keys() 
                    if self.config["marketplaces"].get(m, {}).get("active")
                ]
                
                if not active_marketplaces:
                    self._log("⚠️ Nenhum marketplace ativo selecionado.", 1.0)
                    browser.close()
                    return

                segment_size = 0.9 / len(active_marketplaces)
                
                for i, name in enumerate(active_marketplaces):
                    if self.stop_event.is_set():
                        self._log(f"Interrompendo antes de iniciar {name}...")
                        break
                        
                    MinerClass = self.MINER_MAP[name]
                    miner = MinerClass(
                        page=page,
                        config=self.config,
                        log_queue=self.log_queue,
                        progress_start=0.1 + (i * segment_size),
                        progress_end=0.1 + ((i + 1) * segment_size),
                        stop_event=self.stop_event
                    )
                    
                    try:
                        miner.run()
                    except Exception as e:
                        self._log(f"❌ Erro fatal em {name}: {str(e)[:100]}")

                browser.close()
                self._log("Concluído!", 1.0)

        except Exception as e:
            self._log(f"❌ Erro Crítico no Motor: {str(e)[:100]}")
        finally:
            self.log_queue.put({"type": "done"})

    def _run_demo(self):
        """Simulates mining for testing UI components."""
        self._log("Iniciando modo de demonstração...", 0.1)
        active = [m for m in self.MINER_MAP.keys() if self.config["marketplaces"].get(m, {}).get("active")]
        
        for m in active:
            if self.stop_event.is_set(): break
            for i in range(self.config.get("qtd_produtos", 3)):
                if self.stop_event.is_set(): break
                time.sleep(0.5)
                self.log_queue.put({
                    "type": "result", 
                    "result": {
                        "marketplace": m, 
                        "link_produto": f"https://demo.com/prod-{i}", 
                        "link_afiliado": f"https://aff.com/link-{i}"
                    }
                })
                self._log(f"Demonstração {m}: Item {i+1} coletado")
        
        self._log("Demonstração concluída!", 1.0)
        self.log_queue.put({"type": "done"})
