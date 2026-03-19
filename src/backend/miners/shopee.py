from .base import BaseMiner
from src.backend.core.utils.url_cleaner import clean_url
from src.backend.core.utils.param_helper import append_param
from src.backend.core.utils.cookie_manager import load_cookies_to_page

class ShopeeMiner(BaseMiner):
    """Miner for Shopee Flash Sales."""
    def run(self):
        cfg = self.config["marketplaces"].get("Shopee", {})
        if not cfg.get("active"):
            return
            
        qtd = self.config.get("qtd_produtos", 5)
        aid = cfg.get("affiliate_id", "").strip() or "0"
        
        if cfg.get("cookies"):
            load_cookies_to_page(self.page, cfg["cookies"], "Shopee")
            
        try:
            self.log("Navegando para Ofertas Relâmpago Shopee...")
            self.page.goto("https://shopee.com.br/flash_sale", timeout=45000)
            self.page.wait_for_timeout(5000)
            self.page.keyboard.press("End")
            self.page.wait_for_timeout(1000)
            
            self.log("Extraindo links de produtos da Shopee...")
            links = self.page.eval_on_selector_all('a[href*="-i."]', 'els => els.map(e => e.href)')
            valid = list(dict.fromkeys([clean_url(l, "https://shopee.com.br") for l in links if "-i." in l]))[:qtd]
            
            for i, link in enumerate(valid):
                if self.check_stop():
                    break
                    
                aff_url = append_param(append_param(link, "aff_id", aid), "aff_platform", "affiliate")
                result = {
                    "marketplace": "Shopee",
                    "link_produto": link,
                    "link_afiliado": aff_url
                }
                
                self.log_queue.put({"type": "result", "result": result})
                self.log(f"Item {i+1}/{len(valid)} coletado", progress=(i + 1) / len(valid))
                
        except Exception as e:
            self.log(f"❌ Erro na Shopee: {str(e)[:50]}")
