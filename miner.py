"""
miner.py – Versão 6.0 (ML Hub Precision).
Ajustado para capturar link de afiliado dentro do popover do Mercado Livre.
"""

import json
import os
import time
import queue
import threading
from urllib.parse import urlparse, urlunparse

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

def _clean_url(url: str) -> str:
    try:
        if not url: return ""
        p = urlparse(url)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except: return url

def _append_param(url: str, key: str, value: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={value}"

def _scroll_page(page, q: queue.Queue, times=3):
    _log(q, f"Rolando a página para carregar itens dinâmicos...")
    for i in range(times):
        page.mouse.wheel(0, 1500)
        page.wait_for_timeout(1500)

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
        _log(q, f"{marketplace}: Injetando cookies...")
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
    _log(q, "Amazon: Iniciando...", ps)
    if cfg.get("cookies"): _load_cookies(page, q, cfg["cookies"], "Amazon")
    try:
        page.goto("https://www.amazon.com.br/gp/bestsellers/", timeout=45000)
        _scroll_page(page, q, 2)
        links = page.eval_on_selector_all('a[href*="/dp/"]', 'els => els.map(e => e.href)')
        valid = list(dict.fromkeys([_clean_url(l) for l in links if "/dp/" in l]))[:qtd]
        for i, link in enumerate(valid):
            aff = _append_param(link, "tag", tag)
            q.put({"result": {"marketplace": "Amazon", "link_produto": link, "link_afiliado": aff}})
            _log(q, f"Amazon: {i+1}/{len(valid)} processado", ps + (pe-ps)*((i+1)/len(valid)))
    except Exception as e: _log(q, f"❌ Amazon: {str(e)[:50]}")

def mine_ml(page, config, q, ps, pe):
    cfg = config["marketplaces"]["Mercado Livre"]
    qtd = config.get("qtd_produtos", 5)
    _log(q, "ML: Acessando Hub de Afiliados...", ps)
    if not cfg.get("cookies"):
        _log(q, "⚠️ ML: Erro! Cookies são OBRIGATÓRIOS para o Hub.")
        return
    _load_cookies(page, q, cfg["cookies"], "ML")
    try:
        page.goto("https://www.mercadolivre.com.br/afiliados/hub#menu-user", timeout=60000)
        page.wait_for_timeout(5000)
        _scroll_page(page, q, 4)
        
        # Seletores de cards e conteúdo
        cards = page.query_selector_all(".andes-card")
        _log(q, f"ML Hub: {len(cards)} possíveis cards encontrados.")
        
        count = 0
        for card in cards:
            if count >= qtd: break
            try:
                # 1. Pega link do produto
                link_el = card.query_selector("a[href*='mercadolivre.com.br']")
                if not link_el: continue
                prod_link = _clean_url(link_el.get_attribute("href"))
                
                # 2. Clicar em "Compartilhar"
                # Tentando múltiplos seletores para o botão de compartilhamento
                share_btn = card.query_selector("button:has-text('Compartilhar'), .andes-button--share, .andes-button--quiet")
                if not share_btn: continue
                
                # Scroll para o card ser visível antes de clicar
                card.scroll_into_view_if_needed()
                share_btn.click()
                page.wait_for_timeout(2000) # Espera popover
                
                # 3. Pegar link de afiliado no popover/modal
                # No modal de compartilhamento, o link costuma estar em um input ou texto destacado
                aff_link = ""
                # Tenta input de valor
                input_el = page.query_selector("input.andes-form-control__field, .andes-form-control__field input")
                if input_el:
                    aff_link = input_el.get_attribute("value")
                
                # Se não achou no input, tenta por texto que comece com o domínio do ML
                if not aff_link:
                    text_els = page.query_selector_all(".andes-form-control__field")
                    for te in text_els:
                        val = te.inner_text().strip()
                        if "mercadolivre.com" in val:
                            aff_link = val
                            break
                
                if aff_link:
                    _log(q, f"✅ ML: Link afiliado coletado para {prod_link[:30]}...")
                    q.put({"result": {"marketplace": "Mercado Livre", "link_produto": prod_link, "link_afiliado": aff_link}})
                    count += 1
                else:
                    _log(q, f"⚠️ ML: Falha ao capturar link de afiliado no popover para {prod_link[:30]}...")
                
                # Fecha popover (Esc ou clique no X se houver)
                page.keyboard.press("Escape")
                page.wait_for_timeout(800)
                
            except Exception as e:
                _log(q, f"ML: Erro no card: {str(e)[:50]}")
                page.keyboard.press("Escape") # Tenta limpar estado
                continue

        if count == 0:
            _log(q, "⚠️ ML: Nenhum item processado. Verifique os seletores no Hub ou os cookies.")
            
    except Exception as e: _log(q, f"❌ ML Erro: {str(e)[:100]}")

def mine_shopee(page, config, q, ps, pe):
    cfg = config["marketplaces"]["Shopee"]
    qtd = config.get("qtd_produtos", 5)
    aff_id = cfg.get("affiliate_id", "").strip() or "0"
    _log(q, "Shopee: Iniciando...", ps)
    if cfg.get("cookies"): _load_cookies(page, q, cfg["cookies"], "Shopee")
    try:
        page.goto("https://shopee.com.br/flash_sale", timeout=45000)
        page.wait_for_timeout(4000)
        _scroll_page(page, q, 3)
        links = page.eval_on_selector_all('a[href*="-i."]', 'els => els.map(e => e.href)')
        valid = list(dict.fromkeys([_clean_url(l) for l in links if "-i." in l]))[:qtd]
        for i, link in enumerate(valid):
            aff = _append_param(_append_param(link, "aff_id", aff_id), "aff_platform", "affiliate")
            q.put({"result": {"marketplace": "Shopee", "link_produto": link, "link_afiliado": aff}})
            _log(q, f"Shopee: {i+1}/{len(valid)} processado", ps + (pe-ps)*((i+1)/len(valid)))
    except Exception as e: _log(q, f"❌ Shopee: {str(e)[:50]}")

# -----------------------------------------------------------------------
# Motor Principal
# -----------------------------------------------------------------------

def run_mining(config: dict):
    q = queue.Queue()
    if config.get("demo_mode", False):
        def demo():
            active = [m for m in ["Amazon", "Mercado Livre", "Shopee"] if config["marketplaces"][m]["active"]]
            for m in active:
                for i in range(config.get("qtd_produtos", 5)):
                    q.put({"result": {"marketplace": m, "link_produto": "https://exemplo.com/p", "link_afiliado": "https://mercadolivre.com/afiliado/demo"}})
                    time.sleep(0.1)
            q.put({"done": True})
        threading.Thread(target=demo, daemon=True).start()
    else:
        def worker():
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-dev-shm-usage"])
                    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
                    page = context.new_page()
                    active = [m for m in ["Amazon", "Mercado Livre", "Shopee"] if config["marketplaces"][m]["active"]]
                    seg = 1.0/len(active) if active else 1
                    miners = {"Amazon": mine_amazon, "Mercado Livre": mine_ml, "Shopee": mine_shopee}
                    for i, m in enumerate(active): miners[m](page, config, q, i*seg, (i+1)*seg)
                    browser.close()
            except Exception as e: _log(q, f"❌ Erro Global: {e}")
            finally: q.put({"done": True})
        threading.Thread(target=worker, daemon=True).start()

    while True:
        item = q.get(timeout=300)
        if item.get("done"): break
        yield item
