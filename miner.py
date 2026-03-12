"""
miner.py – Núcleo de automação do LinkMineer (Versão com Diagnóstico e Correção de Cookies).

Melhorias:
  - Sanitização de cookies (fix sameSite error).
  - Restauração do modo demo interno.
  - Simplificação da lógica de links ML.
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

def _clean_url(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

def _append_param(url: str, key: str, value: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={value}"

def _sanitize_cookies(cookies):
    """
    Corrige erros comuns em cookies exportados:
    - Valor de 'sameSite' deve ser Strict, Lax ou None.
    - Remove atributos que o Playwright não aceita.
    """
    valid_samesite = ["Strict", "Lax", "None"]
    sanitized = []
    for c in cookies:
        cookie = c.copy()
        # Corrige SameSite
        ss = str(cookie.get("sameSite", "")).capitalize()
        if ss not in valid_samesite:
            # Se for 'no_restriction', Playwright pede 'None' + 'secure=True'
            if ss == "No_restriction":
                cookie["sameSite"] = "None"
                cookie["secure"] = True
            else:
                # Fallback seguro para o Playwright
                cookie.pop("sameSite", None)
        else:
            cookie["sameSite"] = ss
        
        # Garante que campos obrigatórios existam e remove lixo
        if "name" in cookie and "value" in cookie and "domain" in cookie:
            sanitized.append(cookie)
    return sanitized

def _load_cookies(page, cookies_json: str):
    try:
        cookies = json.loads(cookies_json)
        if isinstance(cookies, list):
            sanitized = _sanitize_cookies(cookies)
            page.context.add_cookies(sanitized)
            return True
    except Exception as e:
        print(f"Erro ao carregar cookies: {e}")
    return False

def _check_blocks(page, marketplace: str):
    title = page.title().lower()
    content = page.content().lower()
    blocks = ["captcha", "robot", "human verification", "bot detection", "access denied", "403 forbidden", "press and hold"]
    for b in blocks:
        if b in title or b in content:
            return f"Bloqueio detectado ({b})"
    if "amazon.com.br/errors/validatecaptcha" in page.url:
        return "Amazon Captcha"
    return None

# -----------------------------------------------------------------------
# Demo Mode (Restaurado)
# -----------------------------------------------------------------------

DEMO_PRODUCTS = {
    "Amazon": ["https://www.amazon.com.br/dp/B0C4J5L9QP", "https://www.amazon.com.br/dp/B09G3GNY2N"],
    "Mercado Livre": ["https://www.mercadolivre.com.br/iphone-15/p/MLB27580088", "https://www.mercadolivre.com.br/air-fryer/p/MLB21765432"],
    "Shopee": ["https://shopee.com.br/produto-ex-i.123456.789012", "https://shopee.com.br/produto-ex-i.234567.890123"],
}

def run_mining_demo(config: dict, q: queue.Queue):
    qtd = config.get("qtd_produtos", 5)
    active = [m for m in ["Amazon", "Mercado Livre", "Shopee"] if config["marketplaces"][m]["active"]]
    total = qtd * len(active) if active else 1
    done = 0

    for m in active:
        cfg = config["marketplaces"][m]
        items = DEMO_PRODUCTS.get(m, [])
        for i, link in enumerate(items[:qtd]):
            time.sleep(0.5)
            aff_link = link
            if m == "Amazon": aff_link = _append_param(link, "tag", cfg.get("tag", "demo-20"))
            elif m == "Mercado Livre":
                track = cfg.get("tracking_id", "").strip()
                if "=" in track: aff_link = f"{link}{'&' if '?' in link else '?'}{track}"
                elif track: aff_link = _append_param(link, "tracking_id", track)
            else: # Shopee
                aff_link = _append_param(link, "aff_id", cfg.get("affiliate_id", "0"))
                aff_link = _append_param(aff_link, "aff_platform", "affiliate")
            
            done += 1
            q.put({"progress": done/total, "message": f"[DEMO] {m}: {i+1} coletado"})
            q.put({"result": {"marketplace": m, "link_produto": link, "link_afiliado": aff_link}})
    q.put({"done": True})

# -----------------------------------------------------------------------
# Amazon
# -----------------------------------------------------------------------

def mine_amazon(page, config: dict, q: queue.Queue, p_start: float, p_end: float):
    cfg = config["marketplaces"]["Amazon"]
    qtd = config.get("qtd_produtos", 5)
    tag = cfg.get("tag", "").strip() or "tag-20"

    q.put({"progress": p_start, "message": "Amazon: Iniciando..."})
    if cfg.get("cookies"): _load_cookies(page, cfg["cookies"])

    source_urls = ["https://www.amazon.com.br/gp/bestsellers/", "https://www.amazon.com.br/s?k=ofertas"]
    product_links = []
    
    for url in source_urls:
        try:
            page.goto(url, timeout=30000)
            block = _check_blocks(page, "Amazon")
            if block:
                q.put({"progress": p_start, "message": f"⚠️ Amazon: {block}"})
                continue
            page.wait_for_timeout(2000)
            links = page.eval_on_selector_all('a[href*="/dp/"]', 'els => els.map(e => e.href)')
            product_links.extend([_clean_url(l) for l in links if "/dp/" in l])
            if len(product_links) >= qtd: break
        except: continue

    product_links = list(dict.fromkeys(product_links))[:qtd]
    for i, link in enumerate(product_links):
        aff_link = _append_param(link, "tag", tag)
        prog = p_start + (p_end - p_start) * ((i+1)/len(product_links))
        q.put({"progress": prog, "message": f"Amazon: {i+1}/{len(product_links)}"})
        q.put({"result": {"marketplace": "Amazon", "link_produto": link, "link_afiliado": aff_link}})

# -----------------------------------------------------------------------
# Mercado Livre
# -----------------------------------------------------------------------

def mine_ml(page, config: dict, q: queue.Queue, p_start: float, p_end: float):
    cfg = config["marketplaces"]["Mercado Livre"]
    qtd = config.get("qtd_produtos", 5)
    track = cfg.get("tracking_id", "").strip()

    q.put({"progress": p_start, "message": "ML: Iniciando..."})
    if cfg.get("cookies"): _load_cookies(page, cfg["cookies"])

    source_urls = ["https://www.mercadolivre.com.br/ofertas"]
    product_links = []
    
    for url in source_urls:
        try:
            page.goto(url, timeout=30000)
            if _check_blocks(page, "ML"): continue
            page.wait_for_timeout(2000)
            links = page.eval_on_selector_all(".promotion-item__link", 'els => els.map(e => e.href)')
            product_links.extend([_clean_url(l) for l in links])
            if len(product_links) >= qtd: break
        except: continue

    product_links = list(dict.fromkeys(product_links))[:qtd]
    for i, link in enumerate(product_links):
        aff_link = link
        if "=" in track: aff_link = f"{link}{'&' if '?' in link else '?'}{track}"
        elif track: aff_link = _append_param(link, "tracking_id", track)
        
        prog = p_start + (p_end - p_start) * ((i+1)/len(product_links))
        q.put({"progress": prog, "message": f"ML: {i+1}/{len(product_links)}"})
        q.put({"result": {"marketplace": "Mercado Livre", "link_produto": link, "link_afiliado": aff_link}})

# -----------------------------------------------------------------------
# Shopee
# -----------------------------------------------------------------------

def mine_shopee(page, config: dict, q: queue.Queue, p_start: float, p_end: float):
    cfg = config["marketplaces"]["Shopee"]
    qtd = config.get("qtd_produtos", 5)
    aff_id = cfg.get("affiliate_id", "").strip() or "0"

    q.put({"progress": p_start, "message": "Shopee: Iniciando..."})
    if cfg.get("cookies"): _load_cookies(page, cfg["cookies"])

    try:
        page.goto("https://shopee.com.br/flash_sale", timeout=30000)
        page.wait_for_timeout(4000)
        links = page.eval_on_selector_all('a[href*="-i."]', 'els => els.map(e => e.href)')
        product_links = list(dict.fromkeys([_clean_url(l) for l in links]))[:qtd]
        
        for i, link in enumerate(product_links):
            aff_link = _append_param(link, "aff_id", aff_id)
            aff_link = _append_param(aff_link, "aff_platform", "affiliate")
            prog = p_start + (p_end - p_start) * ((i+1)/len(product_links))
            q.put({"progress": prog, "message": f"Shopee: {i+1}/{len(product_links)}"})
            q.put({"result": {"marketplace": "Shopee", "link_produto": link, "link_afiliado": aff_link}})
    except Exception as e:
        q.put({"progress": p_end, "message": f"Shopee erro: {str(e)[:50]}"})

# -----------------------------------------------------------------------
# Main Engine
# -----------------------------------------------------------------------

def run_mining(config: dict):
    q = queue.Queue()
    if config.get("demo_mode", False):
        t = threading.Thread(target=run_mining_demo, args=(config, q), daemon=True)
        t.start()
        while True:
            item = q.get(); 
            if item.get("done"): break
            yield item
        return

    active = [m for m in ["Amazon", "Mercado Livre", "Shopee"] if config["marketplaces"][m]["active"]]
    if not active:
        yield {"progress": 1.0, "message": "⚠️ Nada selecionado."}
        return

    segment = 1.0 / len(active)

    def worker():
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-dev-shm-usage"])
                context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
                page = context.new_page()
                miners = {"Amazon": mine_amazon, "Mercado Livre": mine_ml, "Shopee": mine_shopee}
                for i, m in enumerate(active):
                    try: miners[m](page, config, q, i*segment, (i+1)*segment)
                    except Exception as fatal: q.put({"progress": (i+1)*segment, "message": f"❌ {m} Erro: {fatal}"})
                browser.close()
        except Exception as e: q.put({"progress": 1.0, "message": f"❌ Erro Navegador: {e}"})
        finally: q.put({"done": True})

    threading.Thread(target=worker, daemon=True).start()
    while True:
        try:
            item = q.get(timeout=180)
            if item.get("done"): break
            yield item
        except queue.Empty:
            yield {"progress": 1.0, "message": "❌ Timeout."}
            break
