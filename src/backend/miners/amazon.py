from .base import BaseMiner
from src.backend.core.utils.url_cleaner import clean_url
from src.backend.core.utils.param_helper import append_param
from src.backend.core.utils.cookie_manager import load_cookies_to_page

class AmazonMiner(BaseMiner):
    """Miner for Amazon Brazil bestsellers and product details."""
    def run(self):
        cfg = self.config["marketplaces"].get("Amazon", {})
        if not cfg.get("active"):
            return
            
        qtd = self.config.get("qtd_produtos", 5)
        tag = cfg.get("tag", "").strip() or "tag-20"
        
        # Load cookies if available
        if cfg.get("cookies"):
            load_cookies_to_page(self.page, cfg["cookies"], "Amazon")
            
        try:
            self.log("Navegando para mais vendidos da Amazon...")
            self.page.goto("https://www.amazon.com.br/gp/bestsellers/", timeout=45000)
            self.page.wait_for_timeout(3000)
            
            self.log("Extraindo links de produtos...")
            links = self.page.eval_on_selector_all('a[href*="/dp/"]', 'els => els.map(e => e.href)')
            valid = list(dict.fromkeys([clean_url(l, "https://www.amazon.com.br") for l in links if "/dp/" in l]))[:qtd]
            
            for i, link in enumerate(valid):
                if self.check_stop():
                    break
                    
                aff_url = append_param(link, "tag", tag)
                result = {
                    "marketplace": "Amazon",
                    "link_produto": link,
                    "link_afiliado": aff_url
                }
                
                # Report result and progress
                self.log_queue.put({"type": "result", "result": result})
                self.log(f"Item {i+1}/{len(valid)} coletado", progress=(i + 1) / len(valid))
                
        except Exception as e:
            self.log(f"❌ Erro na Amazon: {str(e)[:50]}")
