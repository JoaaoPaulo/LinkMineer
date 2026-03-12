"""
miner.py – Núcleo de automação do LinkMineer (Versão com Diagnóstico Avançado).

Estratégia:
  - Detecção de Captcha e bloqueios em tempo real.
  - Telemetria detalhada enviada ao frontend para depuração.
  - Suporte a Railway (headless=True) e Local (headless=False).
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

def _check_blocks(page, marketplace: str):
    """
    Verifica se a página atual mostra sinais de captcha ou bloqueio.
    Retorna uma string descritiva se bloqueado, senão None.
    """
    title = page.title().lower()
    content = page.content().lower()
    
    blocks = [
        "captcha", "robot", "human verification", "bot detection", 
        "desafio", "não somos robôs", "access denied", "403 forbidden",
        "press and hold", "verification required"
    ]
    
    for b in blocks:
        if b in title or b in content:
            return f"Bloqueio detectado ({b})"
    
    # Verificação específica de Amazon
    if "amazon.com.br/errors/validatecaptcha" in page.url:
        return "Amazon Captcha (validatecaptcha)"
    
    return None

# -----------------------------------------------------------------------
# Amazon
# -----------------------------------------------------------------------

def mine_amazon(page, config: dict, q: queue.Queue, p_start: float, p_end: float):
    cfg = config["marketplaces"]["Amazon"]
    qtd = config.get("qtd_produtos", 5)
    tag = cfg.get("tag", "").strip() or "tag-20"

    q.put({"progress": p_start, "message": "Amazon: Iniciando sessão..."})
    
    if cfg.get("login_type") == "Cookies" and cfg.get("cookies"):
        q.put({"progress": p_start + 0.01, "message": "Amazon: Injetando cookies..."})
        page.context.add_cookies(json.loads(cfg["cookies"]))

    source_urls = [
        "https://www.amazon.com.br/gp/bestsellers/",
        "https://www.amazon.com.br/s?k=ofertas",
    ]

    product_links = []
    for url in source_urls:
        try:
            q.put({"progress": p_start + 0.05, "message": f"Amazon: Acessando {url}..."})
            page.goto(url, timeout=30000)
            
            block = _check_blocks(page, "Amazon")
            if block:
                q.put({"progress": p_start + 0.06, "message": f"⚠️ Amazon: {block}"})
                continue

            page.wait_for_timeout(3000)
            
            selectors = [
                'a[href*="/dp/"]',
                '.s-result-item a[href*="/dp/"]',
                '.a-carousel-card a[href*="/dp/"]'
            ]
            
            for sel in selectors:
                try:
                    q.put({"progress": p_start + 0.07, "message": f"Amazon: Tentando seletor '{sel}'..."})
                    links = page.eval_on_selector_all(sel, 'els => els.map(e => e.href)')
                    valid = [l for l in links if "/dp/" in l]
                    if valid:
                        product_links.extend([_clean_url(l) for l in valid])
                        q.put({"progress": p_start + 0.08, "message": f"Amazon: {len(valid)} links encontrados com '{sel}'"})
                        break
                except:
                    continue
            
            if len(product_links) >= qtd:
                break
        except Exception as e:
            q.put({"progress": p_start + 0.09, "message": f"❌ Amazon Erro: {str(e)[:50]}..."})

    product_links = list(dict.fromkeys(product_links))[:qtd]
    
    if not product_links:
        q.put({"progress": p_end, "message": "❌ Amazon: Nenhum produto encontrado após tentar todas as URLs."})
        return

    for i, link in enumerate(product_links):
        affiliate_link = _append_param(link, "tag", tag)
        progress = p_start + (p_end - p_start) * ((i + 1) / len(product_links))
        q.put({"progress": progress, "message": f"Amazon: Processado {i+1}/{len(product_links)}"})
        q.put({"result": {"marketplace": "Amazon", "link_produto": link, "link_afiliado": affiliate_link}})

# -----------------------------------------------------------------------
# Mercado Livre
# -----------------------------------------------------------------------

def mine_ml(page, config: dict, q: queue.Queue, p_start: float, p_end: float):
    cfg = config["marketplaces"]["Mercado Livre"]
    qtd = config.get("qtd_produtos", 5)
    tracking_id = cfg.get("tracking_id", "").strip()
    matt_tool = cfg.get("matt_tool", "").strip()

    q.put({"progress": p_start, "message": "Mercado Livre: Iniciando sessão..."})

    if cfg.get("login_type") == "Cookies" and cfg.get("cookies"):
        q.put({"progress": p_start + 0.01, "message": "ML: Injetando cookies..."})
        page.context.add_cookies(json.loads(cfg["cookies"]))

    source_urls = [
        "https://www.mercadolivre.com.br/ofertas",
        "https://www.mercadolivre.com.br/mais-vendidos",
    ]

    product_links = []
    for url in source_urls:
        try:
            q.put({"progress": p_start + 0.05, "message": f"ML: Acessando {url}..."})
            page.goto(url, timeout=30000)
            
            block = _check_blocks(page, "ML")
            if block:
                q.put({"progress": p_start + 0.06, "message": f"⚠️ ML: {block}"})
                continue

            page.wait_for_timeout(3000)
            
            selectors = [
                ".promotion-item__link",
                ".poly-component__title a",
                'a[href*="/MLB-"]'
            ]
            
            for sel in selectors:
                try:
                    q.put({"progress": p_start + 0.07, "message": f"ML: Tentando seletor '{sel}'..."})
                    links = page.eval_on_selector_all(sel, 'els => els.map(e => e.href)')
                    valid = [l for l in links if "mercadolivre.com.br" in l]
                    if valid:
                        product_links.extend([_clean_url(l) for l in valid])
                        q.put({"progress": p_start + 0.08, "message": f"ML: {len(valid)} links encontrados"})
                        break
                except:
                    continue
            
            if len(product_links) >= qtd:
                break
        except Exception as e:
            q.put({"progress": p_start + 0.09, "message": f"❌ ML Erro: {str(e)[:50]}..."})

    product_links = list(dict.fromkeys(product_links))[:qtd]

    if not product_links:
        q.put({"progress": p_end, "message": "❌ ML: Nenhum produto encontrado."})
        return

    for i, link in enumerate(product_links):
        affiliate_link = link
        if tracking_id:
            affiliate_link = _append_param(affiliate_link, "tracking_id", tracking_id)
        if matt_tool:
            sep = "&" if "?" in affiliate_link else "?"
            if "=" in matt_tool: affiliate_link = f"{affiliate_link}{sep}{matt_tool}"
            else: affiliate_link = _append_param(affiliate_link, "matt_tool", matt_tool)

        progress = p_start + (p_end - p_start) * ((i + 1) / len(product_links))
        q.put({"progress": progress, "message": f"ML: Processado {i+1}/{len(product_links)}"})
        q.put({"result": {"marketplace": "Mercado Livre", "link_produto": link, "link_afiliado": affiliate_link}})

# -----------------------------------------------------------------------
# Shopee
# -----------------------------------------------------------------------

def mine_shopee(page, config: dict, q: queue.Queue, p_start: float, p_end: float):
    cfg = config["marketplaces"]["Shopee"]
    qtd = config.get("qtd_produtos", 5)
    aff_id = cfg.get("affiliate_id", "").strip() or "0"

    q.put({"progress": p_start, "message": "Shopee: Iniciando sessão..."})
    
    if cfg.get("login_type") == "Cookies" and cfg.get("cookies"):
        q.put({"progress": p_start + 0.01, "message": "Shopee: Injetando cookies..."})
        page.context.add_cookies(json.loads(cfg["cookies"]))

    source_urls = [
        "https://shopee.com.br/flash_sale",
        "https://shopee.com.br/",
    ]

    product_links = []
    for url in source_urls:
        try:
            q.put({"progress": p_start + 0.05, "message": f"Shopee: Acessando {url}..."})
            page.goto(url, timeout=30000)
            
            block = _check_blocks(page, "Shopee")
            if block:
                q.put({"progress": p_start + 0.06, "message": f"⚠️ Shopee: {block}"})
                continue

            page.wait_for_timeout(4000)
            
            selectors = ['a[href*="-i."]', 'a[data-sqe="link"]']
            for sel in selectors:
                try:
                    q.put({"progress": p_start + 0.07, "message": f"Shopee: Tentando seletor '{sel}'..."})
                    links = page.eval_on_selector_all(sel, 'els => els.map(e => e.href)')
                    valid = [l for l in links if "-i." in l]
                    if valid:
                        product_links.extend([_clean_url(l) for l in valid])
                        q.put({"progress": p_start + 0.08, "message": f"Shopee: {len(valid)} links encontrados"})
                        break
                except:
                    continue
            
            if len(product_links) >= qtd:
                break
        except Exception as e:
            q.put({"progress": p_start + 0.09, "message": f"❌ Shopee Erro: {str(e)[:50]}..."})

    product_links = list(dict.fromkeys(product_links))[:qtd]

    if not product_links:
        q.put({"progress": p_end, "message": "❌ Shopee: Nenhum produto encontrado."})
        return

    for i, link in enumerate(product_links):
        affiliate_link = _append_param(link, "aff_id", aff_id)
        affiliate_link = _append_param(affiliate_link, "aff_platform", "affiliate")
        progress = p_start + (p_end - p_start) * ((i + 1) / len(product_links))
        q.put({"progress": progress, "message": f"Shopee: Processado {i+1}/{len(product_links)}"})
        q.put({"result": {"marketplace": "Shopee", "link_produto": link, "link_afiliado": affiliate_link}})

# -----------------------------------------------------------------------
# Main Engine
# -----------------------------------------------------------------------

def run_mining(config: dict):
    q = queue.Queue()
    
    if config.get("demo_mode", False):
        from miner_demo import run_mining_demo # Movi a demo para outro arquivo interno para limpar aqui
        t = threading.Thread(target=run_mining_demo, args=(config, q), daemon=True)
        t.start()
        while True:
            item = q.get()
            if item.get("done"): break
            yield item
        return

    active_markets = [m for m in ["Amazon", "Mercado Livre", "Shopee"] if config["marketplaces"][m]["active"]]
    if not active_markets:
        yield {"progress": 1.0, "message": "⚠️ Nenhum marketplace selecionado."}
        return

    segment = 1.0 / len(active_markets)

    def worker():
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=HEADLESS, 
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
                context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
                page = context.new_page()

                miners = {"Amazon": mine_amazon, "Mercado Livre": mine_ml, "Shopee": mine_shopee}
                
                for i, m in enumerate(active_markets):
                    try:
                        miners[m](page, config, q, i*segment, (i+1)*segment)
                    except Exception as fatal:
                        q.put({"progress": (i+1)*segment, "message": f"❌ {m}: Erro Fatal: {str(fatal)}"})
                
                browser.close()
        except Exception as e:
            q.put({"progress": 1.0, "message": f"❌ Erro Crítico do Navegador: {str(e)}"})
        finally:
            q.put({"done": True})

    threading.Thread(target=worker, daemon=True).start()
    
    while True:
        try:
            item = q.get(timeout=180)
            if item.get("done"): break
            yield item
        except queue.Empty:
            yield {"progress": 1.0, "message": "❌ Timeout da operação."}
            break
