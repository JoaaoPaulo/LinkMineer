"""
miner.py – Versão 5.0 (Hub ML Edition).
Suporte a raspagem interna do Hub de Afiliados do Mercado Livre.
"""

import json
import os
import time
import queue
import threading
from urllib.parse import urlparse, urlunparse

# Configurações de ambiente
_IS_SERVER = os.environ.get("RAILWAY_ENVIRONMENT") is not None or \
             os.environ.get("PORT") is not None
HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "true" if _IS_SERVER else "false").lower() == "true"

# -----------------------------------------------------------------------
# Helpers de Sistema e Log
# -----------------------------------------------------------------------

def _log(q: queue.Queue, message: str, progress: float = None):
    data = {"message": message}
    if progress is not None: data["progress"] = progress
    q.put(data)
    print(f"[LOG] {message}", flush=True)

def _clean_url(url: str) -> str:
    try:
        p = urlparse(url)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except: return url

def _append_param(url: str, key: str, value: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={value}"

def _scroll_page(page, q: queue.Queue, times=3):
    """Simula rolagem de mouse para carregar conteúdo dinâmico."""
    _log(q, f"Rolando a página {times} vezes para carregar itens...")
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
            _log(q, f"✅ {marketplace}: Cookies injetados.")
            return True
    except Exception as e:
        _log(q, f"❌ {marketplace}: Erro nos cookies: {str(e)[:50]}")
    return False

# -----------------------------------------------------------------------
# Demo Mode Logic
# -----------------------------------------------------------------------

def run_mining_demo(config: dict, q: queue.Queue):
    _log(q, "Iniciando MODO DEMO...", 0.1)
    qtd = config.get("qtd_produtos", 5)
    active = [m for m in ["Amazon", "Mercado Livre", "Shopee"] if config["marketplaces"][m]["active"]]
    for idx, m in enumerate(active):
        for i in range(qtd):
            q.put({"result": {"marketplace": m, "link_produto": "https://p.com", "link_afiliado": "https://a.com"}})
            time.sleep(0.1)
    q.put({"done": True})

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
            prog = ps + (pe - ps) * ((i+1)/len(valid))
            q.put({"result": {"marketplace": "Amazon", "link_produto": link, "link_afiliado": aff}})
            _log(q, f"Amazon: {i+1}/{len(valid)} pronto.", prog)
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
        # URL do Hub solicitada pelo usuário
        page.goto("https://www.mercadolivre.com.br/afiliados/hub#menu-user", timeout=60000)
        page.wait_for_timeout(5000)
        
        _scroll_page(page, q, 4)
        
        # Seletores para encontrar os cards de produtos no Hub
        # No hub, os links costumam estar em cards com classes de produto
        cards = page.query_selector_all(".andes-card")
        _log(q, f"ML Hub: {len(cards)} possíveis cards encontrados.")
        
        count = 0
        for card in cards:
            if count >= qtd: break
            
            try:
                # 1. Tenta pegar o link original do produto no card
                link_el = card.query_selector("a[href*='mercadolivre.com.br']")
                if not link_el: continue
                prod_link = _clean_url(link_el.get_attribute("href"))
                
                # 2. Busca e clica no botão de compartilhar (pode ser um ícone ou texto)
                # O botão geralmente tem 'Compartilhar' ou ícone de share
                share_btn = card.query_selector("button:has-text('Compartilhar'), .andes-button--share")
                if not share_btn: 
                    # Fallback: Se não achar botão, tenta ver se o link de afiliado está em algum input hidden
                    _log(q, "ML: Botão compartilhar não visível no card. Pulando...")
                    continue
                
                share_btn.click()
                page.wait_for_timeout(1500)
                
                # 3. No popover de compartilhamento, busca o link de afiliado
                # Geralmente é um input ou um campo com 'Copiado'
                aff_input = page.query_selector("input[value*='mercadolivre.com'], .andes-form-control__field")
                if aff_input:
                    aff_link = aff_input.get_attribute("value")
                    _log(q, f"✅ ML: Link coletado: {prod_link}")
                    q.put({"result": {"marketplace": "Mercado Livre", "link_produto": prod_link, "link_afiliado": aff_link}})
                    count += 1
                
                # Fecha o popover (Esc ou clique fora)
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                
            except Exception as inner:
                _log(q, f"ML: Erro ao processar card: {str(inner)[:50]}")
                continue

        if count == 0:
            _log(q, "⚠️ ML: Nenhum item processado com sucesso. Verifique se os cookies estão logados e se a página do Hub carregou os produtos.")
            
    except Exception as e:
        _log(q, f"❌ ML Erro no Hub: {str(e)[:100]}")

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
            prog = ps + (pe - ps) * ((i+1)/len(valid))
            q.put({"result": {"marketplace": "Shopee", "link_produto": link, "link_afiliado": aff}})
            _log(q, f"Shopee: {i+1}/{len(valid)} pronto.", prog)
    except Exception as e: _log(q, f"❌ Shopee: {str(e)[:50]}")

# -----------------------------------------------------------------------
# Motor Principal
# -----------------------------------------------------------------------

def run_mining(config: dict):
    q = queue.Queue()
    if config.get("demo_mode", False):
        threading.Thread(target=run_mining_demo, args=(config, q), daemon=True).start()
    else:
        def worker():
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    _log(q, "Iniciando Playwright...", 0.05)
                    browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-dev-shm-usage"])
                    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
                    page = context.new_page()
                    
                    active = [m for m in ["Amazon", "Mercado Livre", "Shopee"] if config["marketplaces"][m]["active"]]
                    seg = 1.0/len(active) if active else 1
                    
                    miners = {"Amazon": mine_amazon, "Mercado Livre": mine_ml, "Shopee": mine_shopee}
                    for i, m in enumerate(active):
                        try: miners[m](page, config, q, i*seg, (i+1)*seg)
                        except Exception as e: _log(q, f"❌ {m} Fatal: {e}")
                    
                    browser.close()
            except Exception as e: _log(q, f"❌ Erro Global: {e}")
            finally: q.put({"done": True})
        
        threading.Thread(target=worker, daemon=True).start()

    while True:
        item = q.get(timeout=300)
        if item.get("done"): break
        yield item
