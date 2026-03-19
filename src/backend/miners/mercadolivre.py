from .base import BaseMiner
from src.backend.core.utils.url_cleaner import clean_url
from src.backend.core.utils.cookie_manager import load_cookies_to_page

class MercadoLivreMiner(BaseMiner):
    """Miner for Mercado Livre Affiliate Hub."""
    def run(self):
        cfg = self.config["marketplaces"].get("Mercado Livre", {})
        if not cfg.get("active"):
            return
            
        qtd = self.config.get("qtd_produtos", 5)
        hub_url = "https://www.mercadolivre.com.br/afiliados/hub#menu-user"
        
        if not cfg.get("cookies"):
            self.log("⚠️ Cookies ausentes! O Hub exige login.")
            return
            
        load_cookies_to_page(self.page, cfg["cookies"], "ML")

        # Clipboard interception
        self.page.add_init_script("""
            window._lastCopiedLink = '';
            if (navigator.clipboard) {
                navigator.clipboard.writeText = async (text) => {
                    window._lastCopiedLink = text;
                    return Promise.resolve();
                };
            }
        """)

        try:
            self.log(f"Navegando para o Hub de Afiliados...")
            self.page.goto(hub_url, timeout=60000, wait_until="domcontentloaded")
            self.page.wait_for_timeout(5000)
            
            if "login" in self.page.url.lower():
                self.log("❌ Redirecionado para login! Cookies expirados.")
                return

            self.log("Aguardando cards de produtos...")
            try:
                self.page.wait_for_selector(".andes-card", timeout=20000)
            except:
                self.log("⚠️ Tempo esgotado para '.andes-card'. Tentando reserva...")
            
            count = 0
            processed_links = set()
            scroll_attempts = 0
            max_scroll = max(30, (qtd // 2) + 10)

            while count < qtd and scroll_attempts < max_scroll:
                if self.check_stop():
                    break

                cards = self.page.query_selector_all(".andes-card, [class*='card']")
                if not cards:
                    self.page.keyboard.press("PageDown")
                    self.page.wait_for_timeout(2000)
                    scroll_attempts += 1
                    continue

                for card in cards:
                    if count >= qtd or self.check_stop():
                        break
                    
                    try:
                        link_el = card.query_selector("a[href*='mercadolivre.com.br']")
                        if not link_el:
                            continue
                            
                        p_url = clean_url(link_el.get_attribute("href"))
                        if p_url in processed_links:
                            continue
                        processed_links.add(p_url)

                        share_btn = card.query_selector("button:has-text('Compartilhar'), .andes-button--share")
                        if not share_btn:
                            continue
                            
                        card.scroll_into_view_if_needed()
                        share_btn.click()
                        self.page.wait_for_timeout(1000)
                        
                        self.page.evaluate("window._lastCopiedLink = '';")
                        copy_btn = self.page.query_selector("button:has-text('Copiar link')")
                        if copy_btn:
                            copy_btn.click()
                            self.page.wait_for_timeout(400)
                        
                        aff_url = self.page.evaluate("window._lastCopiedLink")
                        if not aff_url:
                            inp = self.page.query_selector("input.andes-form-control__field")
                            if inp: 
                                aff_url = inp.get_attribute("value")

                        if aff_url:
                            result = {
                                "marketplace": "Mercado Livre",
                                "link_produto": p_url,
                                "link_afiliado": aff_url
                            }
                            self.log_queue.put({"type": "result", "result": result})
                            count += 1
                            self.log(f"Item {count}/{qtd} coletado", progress=count/qtd)
                        
                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(150)
                    except:
                        self.page.keyboard.press("Escape")
                        continue

                self.page.keyboard.press("PageDown")
                self.page.wait_for_timeout(2000)
                scroll_attempts += 1

        except Exception as e:
            self.log(f"❌ Erro fatal no ML: {str(e)[:150]}")
