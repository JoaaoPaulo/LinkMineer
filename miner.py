"""
miner.py – Versão 10.0 (High Speed & Infinite Scroll).
Otimizado para grandes volumes (40+ itens) e velocidade aprimorada.
Fluxo: Rolagem dinâmica + Interceptação de Clipboard + Cliques Ultra-precisos.
"""

import json
import os
import time
import queue
import threading
from urllib.parse import urlparse, urlunparse, urljoin

_IS_SERVER = os.environ.get("RAILWAY_ENVIRONMENT") is not None or \
             os.environ.get("PORT") is not None
HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "true" if _IS_SERVER else "false").lower() == "true"

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _log(q: queue.Queue, message: str, progress: float = None):
    data = {"message": message}
    if progress is not None: data["progress"] = progress
    q.put(data)
    print(f"[LOG] {message}", flush=True)

def _clean_url(url: str, base_url: str = "https://www.mercadolivre.com.br") -> str:
    try:
        if not url: return ""
        if url.startswith("/"): url = urljoin(base_url, url)
        p = urlparse(url)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except: return url

def _append_param(url: str, key: str, value: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={value}"

def _sanitize_cookies(cookies):
    valid_samesite = ["Strict", "Lax", "None"]
    sanitized = []
    for c in cookies:
        if not isinstance(c, dict): continue
        cookie = c.copy()
        raw_ss = str(cookie.get("sameSite", ""))
        ss = raw_ss.capitalize()
        if ss not in valid_samesite:
            if ss == "No_restriction" or raw_ss == "no_restriction":
                cookie["sameSite"] = "None"
                cookie["secure"] = True
            else: cookie.pop("sameSite", None)
        else: cookie["sameSite"] = ss
        if "name" in cookie and "value" in cookie and "domain" in cookie:
            sanitized.append(cookie)
    return sanitized

def _load_cookies(page, q: queue.Queue, cookies_json: str, marketplace: str):
    try:
        cookies = json.loads(cookies_json)
        if isinstance(cookies, list):
            sanitized = _sanitize_cookies(cookies)
            page.context.add_cookies(sanitized)
            return True
    except Exception as e:
        _log(q, f"❌ {marketplace}: Erro nos cookies: {str(e)[:50]}")
    return False

# -----------------------------------------------------------------------
# Scrapers
# -----------------------------------------------------------------------

def mine_amazon(page, config, q, ps, pe):
    cfg = config["marketplaces"]["Amazon"]
    qtd = config.get("qtd_produtos", 5)
    tag = cfg.get("tag", "").strip() or "tag-20"
    if cfg.get("cookies"): _load_cookies(page, q, cfg["cookies"], "Amazon")
    try:
        page.goto("https://www.amazon.com.br/gp/bestsellers/", timeout=45000, wait_until="commit")
        page.wait_for_timeout(2000)
        # Scroll dinâmico simples para Amazon
        for _ in range(2):
            page.keyboard.press("PageDown")
            page.wait_for_timeout(800)
        
        links = page.eval_on_selector_all('a[href*="/dp/"]', 'els => els.map(e => e.href)')
        valid = list(dict.fromkeys([_clean_url(l, "https://www.amazon.com.br") for l in links if "/dp/" in l]))[:qtd]
        for i, link in enumerate(valid):
            aff = _append_param(link, "tag", tag)
            q.put({"result": {"marketplace": "Amazon", "link_produto": link, "link_afiliado": aff}})
            _log(q, f"Amazon: {i+1}/{len(valid)} coletado", ps + (pe-ps)*((i+1)/len(valid)))
    except Exception as e: _log(q, f"❌ Amazon: {str(e)[:50]}")

def mine_ml(page, config, q, ps, pe):
    cfg = config["marketplaces"]["Mercado Livre"]
    qtd = config.get("qtd_produtos", 5)
    _log(q, "ML: Ativando motor de alta velocidade...", ps)
    
    if not cfg.get("cookies"):
        _log(q, "⚠️ ML: Cookies obrigatórios!")
        return
    _load_cookies(page, q, cfg["cookies"], "ML")

    # Injeta interceptador de clipboard ultra-rápido
    page.add_init_script("""
        window._lastCopiedLink = '';
        if (navigator.clipboard) {
            navigator.clipboard.writeText = async (text) => {
                window._lastCopiedLink = text;
                return Promise.resolve();
            };
        }
    """)

    try:
        page.goto("https://www.mercadolivre.com.br/afiliados/hub#menu-user", timeout=60000, wait_until="commit")
        page.wait_for_timeout(5000)
        
        count = 0
        processed_links = set()
        scroll_attempts = 0
        max_scroll_attempts = 15

        while count < qtd and scroll_attempts < max_scroll_attempts:
            # Captura cards visíveis no momento
            cards = page.query_selector_all(".andes-card")
            _log(q, f"ML: Analisando {len(cards)} cards na vista atual...")
            
            found_in_round = 0
            for card in cards:
                if count >= qtd: break
                
                try:
                    # 1. Identificar se já processamos este produto para ser rápido
                    link_el = card.query_selector("a[href*='mercadolivre.com.br']")
                    if not link_el: continue
                    prod_url = _clean_url(link_el.get_attribute("href"))
                    
                    if prod_url in processed_links: continue
                    processed_links.add(prod_url)

                    # 2. Interação
                    # Botão "Compartilhar"
                    share_btn = card.query_selector("button:has-text('Compartilhar'), .andes-button--share")
                    if not share_btn: continue
                    
                    card.scroll_into_view_if_needed()
                    share_btn.click()
                    
                    # Espera menor, mas com fallback
                    page.wait_for_timeout(1800)
                    
                    # Clicar em "Copiar link"
                    page.evaluate("window._lastCopiedLink = '';")
                    copy_btn = page.query_selector("button:has-text('Copiar link')")
                    if copy_btn:
                        copy_btn.click()
                        page.wait_for_timeout(800)
                    
                    aff_url = page.evaluate("window._lastCopiedLink")
                    
                    if not aff_url: # Fallback input
                        inp = page.query_selector("input.andes-form-control__field")
                        if inp: aff_url = inp.get_attribute("value")

                    if aff_url:
                        _log(q, f"✅ ML Item {count+1} pronto.")
                        q.put({"result": {"marketplace": "Mercado Livre", "link_produto": prod_url, "link_afiliado": aff_url}})
                        count += 1
                        found_in_round += 1
                        # Atualiza progresso proporcional
                        prog = ps + (pe - ps) * (count / qtd)
                        _log(q, f"Progresso ML: {count}/{qtd}", prog)
                    
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(400)
                    
                except:
                    page.keyboard.press("Escape")
                    continue

            # Se não achou nada novo nesta rodada ou se ainda precisa de mais, rola a página
            if found_in_round == 0 or count < qtd:
                scroll_attempts += 1
                _log(q, f"ML: Rulagem {scroll_attempts} para buscar mais itens...")
                page.keyboard.press("PageDown")
                page.wait_for_timeout(1500)
            else:
                # Se achou itens, tenta rolar só um pouco para trazer os próximos
                page.mouse.wheel(0, 800)
                page.wait_for_timeout(1000)

        if count < qtd:
            _log(q, f"ℹ️ ML: Coleta finalizada com {count} itens (alvo era {qtd}).")
            
    except Exception as e:
        _log(q, f"❌ ML Erro: {str(e)[:100]}")

def mine_shopee(page, config, q, ps, pe):
    cfg = config["marketplaces"]["Shopee"]
    qtd = config.get("qtd_produtos", 5)
    aid = cfg.get("affiliate_id", "").strip() or "0"
    if cfg.get("cookies"): _load_cookies(page, q, cfg["cookies"], "Shopee")
    try:
        page.goto("https://shopee.com.br/flash_sale", timeout=45000, wait_until="commit")
        page.wait_for_timeout(4000)
        page.keyboard.press("End")
        page.wait_for_timeout(1000)
        links = page.eval_on_selector_all('a[href*="-i."]', 'els => els.map(e => e.href)')
        valid = list(dict.fromkeys([_clean_url(l, "https://shopee.com.br") for l in links if "-i." in l]))[:qtd]
        for i, link in enumerate(valid):
            aff = _append_param(_append_param(link, "aff_id", aid), "aff_platform", "affiliate")
            q.put({"result": {"marketplace": "Shopee", "link_produto": link, "link_afiliado": aff}})
            _log(q, f"Shopee: {i+1}/{len(valid)} pronto", ps + (pe-ps)*((i+1)/len(valid)))
    except Exception as e: _log(q, f"❌ Shopee: {str(e)[:50]}")

# -----------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------

def run_mining(config: dict):
    q = queue.Queue()
    if config.get("demo_mode", False):
        def d():
            for m in [k for k,v in config["marketplaces"].items() if v["active"]]:
                for i in range(config.get("qtd_produtos", 5)):
                    q.put({"result": {"marketplace": m, "link_produto": "http://p", "link_afiliado": "http://a"}})
                    time.sleep(0.05)
            q.put({"done": True})
        threading.Thread(target=d, daemon=True).start()
    else:
        def worker():
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    b = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-dev-shm-usage"])
                    ctx = b.new_context(permissions=["clipboard-read", "clipboard-write"])
                    page = ctx.new_page()
                    active = [m for m in ["Amazon", "Mercado Livre", "Shopee"] if config["marketplaces"][m]["active"]]
                    seg = 1.0/len(active) if active else 1
                    map_m = {"Amazon": mine_amazon, "Mercado Livre": mine_ml, "Shopee": mine_shopee}
                    for i, m in enumerate(active):
                        map_m[m](page, config, q, i*seg, (i+1)*seg)
                    b.close()
            except Exception as e: _log(q, f"❌ Erro Global: {e}")
            finally: q.put({"done": True})
        threading.Thread(target=worker, daemon=True).start()

    while True:
        try:
            item = q.get(timeout=600) # 10 minutos para grandes batches
            if item.get("done"): break
            yield item
        except: break
