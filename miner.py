"""
miner.py – Núcleo de automação do LinkMineer (Versão Ultra Diagnóstica).

Estratégia:
  - Logs granulares para cada ação (navegação, injeção, raspagem).
  - Captura e exibição de erros reais (sem silent fail).
  - Sanitização de cookies para evitar erros de SameSite.
"""

import json
import os
import time
import queue
import threading
import datetime
from urllib.parse import urlparse, urlunparse

_IS_SERVER = os.environ.get("RAILWAY_ENVIRONMENT") is not None or \
             os.environ.get("PORT") is not None
HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "true" if _IS_SERVER else "false").lower() == "true"

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _log(q: queue.Queue, message: str, progress: float = None):
    data = {"message": message}
    if progress is not None:
        data["progress"] = progress
    q.put(data)

def _clean_url(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

def _append_param(url: str, key: str, value: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={value}"

def _sanitize_cookies(cookies):
    valid_samesite = ["Strict", "Lax", "None"]
    sanitized = []
    for c in cookies:
        if not isinstance(c, dict): continue
        cookie = c.copy()
        ss = str(cookie.get("sameSite", "")).capitalize()
        if ss not in valid_samesite:
            if ss == "No_restriction":
                cookie["sameSite"] = "None"
                cookie["secure"] = True
            else:
                cookie.pop("sameSite", None)
        else:
            cookie["sameSite"] = ss
        
        if "name" in cookie and "value" in cookie and "domain" in cookie:
            sanitized.append(cookie)
    return sanitized

def _load_cookies(page, q: queue.Queue, cookies_json: str, marketplace: str):
    try:
        _log(q, f"{marketplace}: Analisando cookies...")
        cookies = json.loads(cookies_json)
        if isinstance(cookies, list):
            sanitized = _sanitize_cookies(cookies)
            page.context.add_cookies(sanitized)
            _log(q, f"✅ {marketplace}: {len(sanitized)} cookies injetados.")
            return True
        else:
            _log(q, f"⚠️ {marketplace}: Formato de cookies inválido (não é uma lista).")
    except Exception as e:
        _log(q, f"❌ {marketplace}: Erro ao carregar cookies: {str(e)[:100]}")
    return False

def _check_blocks(page):
    title = page.title().lower()
    content = page.content().lower()
    blocks = ["captcha", "robot", "human verification", "bot detection", "access denied", "403 forbidden", "press and hold"]
    for b in blocks:
        if b in title or b in content:
            return f"Bloqueio detectado: {b}"
    if "amazon.com.br/errors/validatecaptcha" in page.url:
        return "Amazon Captcha"
    return None

# -----------------------------------------------------------------------
# Demo Mode
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
            time.sleep(0.3)
            aff_link = link
            if m == "Amazon": 
                tag = cfg.get("tag", "").strip() or "demo-20"
                aff_link = _append_param(link, "tag", tag)
            elif m == "Mercado Livre":
                track = cfg.get("tracking_id", "").strip() or "demo-ml"
                if "=" in track: aff_link = f"{link}{'&' if '?' in link else '?'}{track}"
                else: aff_link = _append_param(link, "tracking_id", track)
            else: # Shopee
                aff_id = cfg.get("affiliate_id", "").strip() or "0"
                aff_link = _append_param(link, "aff_id", aff_id)
                aff_link = _append_param(aff_link, "aff_platform", "affiliate")
            
            done += 1
            _log(q, f"[DEMO] {m}: Item {i+1} pronto", done/total)
            q.put({"result": {"marketplace": m, "link_produto": link, "link_afiliado": aff_link}})
    q.put({"done": True})

# -----------------------------------------------------------------------
# Core Mining Logic
# -----------------------------------------------------------------------

def mine_generic(page, marketplace: str, source_urls: list, selector: str, config: dict, q: queue.Queue, p_start: float, p_end: float):
    cfg = config["marketplaces"][marketplace]
    qtd = config.get("qtd_produtos", 5)
    
    _log(q, f"{marketplace}: Iniciando mineração...", p_start)
    
    if cfg.get("cookies"):
        _load_cookies(page, q, cfg["cookies"], marketplace)

    product_links = []
    for url in source_urls:
        if len(product_links) >= qtd: break
        
        try:
            _log(q, f"{marketplace}: Acessando {url}...")
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            
            # Aguarda um pouco mais em caso de CSR (Shopee)
            page.wait_for_timeout(3000)
            
            block = _check_blocks(page)
            if block:
                _log(q, f"⚠️ {marketplace}: {block}")
                continue
            
            _log(q, f"{marketplace}: Buscando produtos...")
            links = page.eval_on_selector_all(selector, 'els => els.map(e => e.href)')
            
            # Filtros específicos
            if marketplace == "Amazon":
                found = [_clean_url(l) for l in links if "/dp/" in l]
            elif marketplace == "Mercado Livre":
                found = [_clean_url(l) for l in links if "mercadolivre.com.br" in l]
            else: # Shopee
                found = [_clean_url(l) for l in links if "-i." in l]
                
            if found:
                _log(q, f"✅ {marketplace}: {len(found)} links encontrados.")
                product_links.extend(found)
            else:
                _log(q, f"ℹ️ {marketplace}: Nenhum link encontrado com o seletor atual.")
                
        except Exception as e:
            _log(q, f"❌ {marketplace}: Erro ao acessar URL: {str(e)[:100]}")

    product_links = list(dict.fromkeys(product_links))[:qtd]
    
    if not product_links:
        _log(q, f"⚠️ {marketplace}: Não foi possível coletar nenhum link.")
        return

    # Geração dos links de afiliado
    for i, link in enumerate(product_links):
        aff_link = link
        if marketplace == "Amazon":
            tag = cfg.get("tag", "").strip() or "tag-20"
            aff_link = _append_param(link, "tag", tag)
        elif marketplace == "Mercado Livre":
            track = cfg.get("tracking_id", "").strip()
            if "=" in track: aff_link = f"{link}{'&' if '?' in link else '?'}{track}"
            elif track: aff_link = _append_param(link, "tracking_id", track)
        else: # Shopee
            aff_id = cfg.get("affiliate_id", "").strip() or "0"
            aff_link = _append_param(link, "aff_id", aff_id)
            aff_link = _append_param(aff_link, "aff_platform", "affiliate")
            
        prog = p_start + (p_end - p_start) * ((i+1)/len(product_links))
        _log(q, f"{marketplace}: {i+1}/{len(product_links)} processado", prog)
        q.put({"result": {"marketplace": marketplace, "link_produto": link, "link_afiliado": aff_link}})

# -----------------------------------------------------------------------
# Entradas específicas
# -----------------------------------------------------------------------

def mine_amazon(page, config, q, ps, pe):
    urls = ["https://www.amazon.com.br/gp/bestsellers/", "https://www.amazon.com.br/s?k=ofertas"]
    mine_generic(page, "Amazon", urls, 'a[href*="/dp/"]', config, q, ps, pe)

def mine_ml(page, config, q, ps, pe):
    urls = ["https://www.mercadolivre.com.br/ofertas"]
    # Tenta seletores diferentes em cascata se necessário, mas aqui usaremos o mais genérico
    mine_generic(page, "Mercado Livre", urls, "a.promotion-item__link, a[href*='/MLB-']", config, q, ps, pe)

def mine_shopee(page, config, q, ps, pe):
    urls = ["https://shopee.com.br/flash_sale"]
    mine_generic(page, "Shopee", urls, 'a[href*="-i."]', config, q, ps, pe)

# -----------------------------------------------------------------------
# Motor Principal
# -----------------------------------------------------------------------

def run_mining(config: dict):
    q = queue.Queue()
    
    if config.get("demo_mode", False):
        t = threading.Thread(target=run_mining_demo, args=(config, q), daemon=True)
        t.start()
        while True:
            item = q.get()
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
                _log(q, "Iniciando navegador Playwright...")
                browser = p.chromium.launch(
                    headless=HEADLESS, 
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 720}
                )
                page = context.new_page()

                miners = {"Amazon": mine_amazon, "Mercado Livre": mine_ml, "Shopee": mine_shopee}
                
                for i, m in enumerate(active):
                    try:
                        miners[m](page, config, q, i*segment, (i+1)*segment)
                    except Exception as fatal:
                        _log(q, f"❌ {m}: Erro crítico: {str(fatal)[:100]}")
                
                browser.close()
                _log(q, "Navegador fechado.")
        except Exception as e:
            _log(q, f"❌ Erro Global: {str(e)[:100]}")
        finally:
            q.put({"done": True})

    threading.Thread(target=worker, daemon=True).start()
    
    while True:
        try:
            item = q.get(timeout=200)
            if item.get("done"): break
            yield item
        except queue.Empty:
            yield {"progress": 1.0, "message": "❌ Operação interrompida por timeout."}
            break
