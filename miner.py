"""
miner.py – Versão 4.0 (Ultra Robust Debug).
Focado em visibilidade total do processo e correção de erros de ambiente (Railway/Local).
"""

import json
import os
import time
import queue
import threading
import sys
from urllib.parse import urlparse, urlunparse

# Configurações de ambiente
_IS_SERVER = os.environ.get("RAILWAY_ENVIRONMENT") is not None or \
             os.environ.get("PORT") is not None
HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "true" if _IS_SERVER else "false").lower() == "true"

# -----------------------------------------------------------------------
# Helpers de Sistema e Log
# -----------------------------------------------------------------------

def _log(q: queue.Queue, message: str, progress: float = None):
    """Envia log para o UI do Streamlit e para o console (Railway Logs)."""
    data = {"message": message}
    if progress is not None:
        data["progress"] = progress
    q.put(data)
    # Print para o log do Railway (Terminal)
    print(f"[LOG] {message}", flush=True)

def _clean_url(url: str) -> str:
    try:
        p = urlparse(url)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except:
        return url

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
            else:
                cookie.pop("sameSite", None)
        else:
            cookie["sameSite"] = ss
        if "name" in cookie and "value" in cookie and "domain" in cookie:
            sanitized.append(cookie)
    return sanitized

def _load_cookies(page, q: queue.Queue, cookies_json: str, marketplace: str):
    try:
        _log(q, f"{marketplace}: Analisando JSON de cookies...")
        cookies = json.loads(cookies_json)
        if isinstance(cookies, list):
            sanitized = _sanitize_cookies(cookies)
            page.context.add_cookies(sanitized)
            _log(q, f"✅ {marketplace}: {len(sanitized)} cookies injetados com sucesso.")
            return True
        _log(q, f"⚠️ {marketplace}: Cookies devem ser uma lista JSON [{{...}}].")
    except Exception as e:
        _log(q, f"❌ {marketplace}: Erro ao processar cookies: {str(e)[:100]}")
    return False

def _check_blocks(page):
    title = page.title().lower()
    content = page.content().lower()
    blocks = ["captcha", "robot", "human verification", "bot detection", "denied", "403 forbidden", "press and hold"]
    for b in blocks:
        if b in title or b in content:
            return f"Bloqueio detectado: {b}"
    if "/errors/validatecaptcha" in page.url:
        return "Amazon Captcha detectado"
    return None

# -----------------------------------------------------------------------
# Demo Mode Logic
# -----------------------------------------------------------------------

def run_mining_demo(config: dict, q: queue.Queue):
    _log(q, "Iniciando MODO DEMO (Simulação)...", 0.05)
    time.sleep(1)
    qtd = config.get("qtd_produtos", 5)
    active = [m for m in ["Amazon", "Mercado Livre", "Shopee"] if config["marketplaces"][m]["active"]]
    
    demo_links = {
        "Amazon": ["https://www.amazon.com.br/dp/B0C4J5L9QP"],
        "Mercado Livre": ["https://www.mercadolivre.com.br/p/MLB27580088"],
        "Shopee": ["https://shopee.com.br/produto-i.123.456"]
    }

    for idx, m in enumerate(active):
        _log(q, f"[DEMO] Minerando {m}...", (idx+1)/len(active))
        for i in range(qtd):
            links = demo_links.get(m, ["https://exemplo.com/p"])
            base = links[0]
            aff = base + "?aff_id=demo"
            q.put({"result": {"marketplace": m, "link_produto": base, "link_afiliado": aff}})
            time.sleep(0.2)
    
    _log(q, "✅ MODO DEMO concluído.", 1.0)
    q.put({"done": True})

# -----------------------------------------------------------------------
# Scraper Genérico
# -----------------------------------------------------------------------

def mine_generic(page, marketplace: str, source_urls: list, selectors: list, config: dict, q: queue.Queue, ps: float, pe):
    cfg = config["marketplaces"][marketplace]
    qtd = config.get("qtd_produtos", 5)
    
    _log(q, f"{marketplace}: Preparando motor...", ps)
    
    if cfg.get("cookies"):
        _load_cookies(page, q, cfg["cookies"], marketplace)

    all_links = []
    for url in source_urls:
        if len(all_links) >= qtd: break
        
        try:
            _log(q, f"{marketplace}: Navegando → {url}")
            # Timeout maior e wait_until relaxado para evitar travar no Railway
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            
            block = _check_blocks(page)
            if block:
                _log(q, f"⚠️ {marketplace}: {block}")
                continue
            
            _log(q, f"{marketplace}: Página carregada. Buscando produtos...")
            
            found_this_url = []
            for sel in selectors:
                _log(q, f"{marketplace}: Testando seletor '{sel}'...")
                links = page.eval_on_selector_all(sel, 'els => els.map(e => e.href)')
                
                # Filtros por marketplace
                valid = []
                if marketplace == "Amazon": valid = [l for l in links if "/dp/" in l]
                elif marketplace == "Mercado Livre": valid = [l for l in links if "mercadolivre.com.br" in l and "/p/" in l or "/MLB-" in l]
                else: valid = [l for l in links if "-i." in l]
                
                if valid:
                    _log(q, f"✅ {marketplace}: {len(valid)} links encontrados com '{sel}'.")
                    found_this_url.extend([_clean_url(l) for l in valid])
                    break # Se achou links com um seletor, não precisa dos outros nesta URL
            
            all_links.extend(found_this_url)
            
        except Exception as e:
            _log(q, f"❌ {marketplace}: Erro na URL {url}: {str(e)[:100]}")

    all_links = list(dict.fromkeys(all_links))[:qtd]
    
    if not all_links:
        _log(q, f"⚠️ {marketplace}: Nenhum produto encontrado.", pe)
        return

    # Gera links de afiliado
    for i, link in enumerate(all_links):
        aff = link
        if marketplace == "Amazon":
            tag = cfg.get("tag", "").strip() or "tag-20"
            aff = _append_param(link, "tag", tag)
        elif marketplace == "Mercado Livre":
            track = cfg.get("tracking_id", "").strip()
            if "=" in track: aff = f"{link}{'&' if '?' in link else '?'}{track}"
            elif track: aff = _append_param(link, "tracking_id", track)
        else: # Shopee
            aid = cfg.get("affiliate_id", "").strip() or "0"
            aff = _append_param(_append_param(link, "aff_id", aid), "aff_platform", "affiliate")
            
        p = ps + (pe - ps) * ((i+1)/len(all_links))
        q.put({"result": {"marketplace": marketplace, "link_produto": link, "link_afiliado": aff}})
        _log(q, f"{marketplace}: Link {i+1} pronto.", p)

# -----------------------------------------------------------------------
# Marketplace Wrappers
# -----------------------------------------------------------------------

def mine_amazon_wrap(page, config, q, ps, pe):
    urls = ["https://www.amazon.com.br/gp/bestsellers/", "https://www.amazon.com.br/s?k=ofertas"]
    selectors = ['a[href*="/dp/"]', '.s-result-item a', '.a-carousel-card a']
    mine_generic(page, "Amazon", urls, selectors, config, q, ps, pe)

def mine_ml_wrap(page, config, q, ps, pe):
    urls = ["https://www.mercadolivre.com.br/ofertas", "https://www.mercadolivre.com.br/mais-vendidos"]
    selectors = [".promotion-item__link", ".poly-component__title a", "a[href*='/p/MLB']", "a[href*='/MLB-']"]
    mine_generic(page, "Mercado Livre", urls, selectors, config, q, ps, pe)

def mine_shopee_wrap(page, config, q, ps, pe):
    urls = ["https://shopee.com.br/flash_sale", "https://shopee.com.br/daily_discover"]
    selectors = ['a[href*="-i."]', 'a[data-sqe="link"]']
    mine_generic(page, "Shopee", urls, selectors, config, q, ps, pe)

# -----------------------------------------------------------------------
# Main Runner
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
        yield {"progress": 1.0, "message": "⚠️ Nenhum marketplace selecionado."}
        return

    segment = 1.0 / len(active)

    def worker():
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                _log(q, "Iniciando motor Playwright (Headless)...", 0.05)
                # Argumentos extras para Railway (Alpine/Debian containers)
                browser = p.chromium.launch(
                    headless=HEADLESS, 
                    args=[
                        "--no-sandbox", 
                        "--disable-setuid-sandbox", 
                        "--disable-dev-shm-usage", 
                        "--disable-gpu",
                        "--no-first-run",
                        "--no-zygote"
                    ]
                )
                _log(q, "✅ Navegador lançado. Criando contexto...", 0.1)
                
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 800}
                )
                page = context.new_page()

                miners = {
                    "Amazon": mine_amazon_wrap, 
                    "Mercado Livre": mine_ml_wrap, 
                    "Shopee": mine_shopee_wrap
                }
                
                for i, m in enumerate(active):
                    try:
                        miners[m](page, config, q, i*segment, (i+1)*segment)
                    except Exception as err:
                        _log(q, f"❌ Erro Crítico em {m}: {str(err)[:150]}")
                
                browser.close()
                _log(q, "Concluído. Navegador encerrado.", 1.0)
        except Exception as e:
            _log(q, f"❌ Erro Global Playwright: {str(e)[:150]}")
        finally:
            q.put({"done": True})

    threading.Thread(target=worker, daemon=True).start()
    
    while True:
        try:
            item = q.get(timeout=300) # Timeout de 5 minutos por segurança
            if item.get("done"): break
            yield item
        except queue.Empty:
            yield {"progress": 1.0, "message": "❌ Timeout: A operação demorou mais que o esperado."}
            break
