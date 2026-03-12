"""
miner.py – Versão 8.0 (ML Hub Final Polish).
Totalmente alinhado às instruções do usuário: Compartilhar -> Copiar Link -> Esc.
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

def _scroll_page_smooth(page, q: queue.Queue, marketplace: str):
    _log(q, f"{marketplace}: Rolando página...")
    for i in range(3):
        page.keyboard.press("PageDown")
        page.wait_for_timeout(1000)

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
            _log(q, f"✅ {marketplace}: Cookies injetados.")
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
        page.wait_for_timeout(3000)
        _scroll_page_smooth(page, q, "Amazon")
        links = page.eval_on_selector_all('a[href*="/dp/"]', 'els => els.map(e => e.href)')
        valid = list(dict.fromkeys([_clean_url(l, "https://www.amazon.com.br") for l in links if "/dp/" in l]))[:qtd]
        for i, link in enumerate(valid):
            aff = _append_param(link, "tag", tag)
            q.put({"result": {"marketplace": "Amazon", "link_produto": link, "link_afiliado": aff}})
            _log(q, f"Amazon: {i+1}/{len(valid)} processado", ps + (pe-ps)*((i+1)/len(valid)))
    except Exception as e: _log(q, f"❌ Amazon Erro: {str(e)[:80]}")

def mine_ml(page, config, q, ps, pe):
    cfg = config["marketplaces"]["Mercado Livre"]
    qtd = config.get("qtd_produtos", 5)
    _log(q, "ML: Iniciando...", ps)
    if cfg.get("cookies"): _load_cookies(page, q, cfg["cookies"], "ML")
    else:
        _log(q, "⚠️ ML: Erro! Cookies são obrigatórios.")
        return

    try:
        _log(q, "ML: Acessando Hub de Afiliados...")
        page.goto("https://www.mercadolivre.com.br/afiliados/hub#menu-user", timeout=60000, wait_until="commit")
        page.wait_for_timeout(8000)
        _scroll_page_smooth(page, q, "ML")
        
        # Seletores de cards do ML (Hub)
        # O Hub pode usar '.andes-card' ou '.hub-product-card' ou similar
        cards = page.query_selector_all(".andes-card, .hub-card, [class*='card']")
        _log(q, f"ML Hub: {len(cards)} cards detectados.")
        
        count = 0
        for i, card in enumerate(cards):
            if count >= qtd: break
            try:
                # 1. Link do Produto
                link_el = card.query_selector("a[href*='mercadolivre.com.br']")
                if not link_el: continue
                prod_url = _clean_url(link_el.get_attribute("href"))
                
                # 2. Clicar em Compartilhar
                # Seletores mais amplos para o botão
                share_btn = card.query_selector("button:has-text('Compartilhar'), .andes-button--share, [aria-label*='Compartilhar']")
                if not share_btn:
                    # Tenta clicar em qualquer botão silencioso (comum no ML)
                    share_btn = card.query_selector(".andes-button--quiet, button")
                    if not share_btn or "Compartilhar" not in (share_btn.inner_text() or ""):
                        continue

                _log(q, f"ML Item {count+1}: Clicando em Compartilhar...")
                card.scroll_into_view_if_needed()
                share_btn.click()
                page.wait_for_timeout(3500) # Espera popover abrir e renderizar

                # 3. Clicar em "Copiar link" e Capturar o valor
                # No popover do ML, geralmente há um botão com o texto "Copiar link"
                # E o link de afiliado costuma estar em um input ou num atributo do botão.
                aff_url = ""
                
                # A) Tenta encontrar o botão "Copiar link"
                copy_btn = page.query_selector("button:has-text('Copiar link'), .andes-button:has-text('Copiar link')")
                if copy_btn:
                    # Alguns botões têm o link num atributo data-link ou similar
                    aff_url = copy_btn.get_attribute("data-link") or copy_btn.get_attribute("href")
                
                # B) Se não achou, tenta o input que fica no popover
                if not aff_url:
                    input_el = page.query_selector("input[value*='mercadolivre.com'], .andes-form-control__field input")
                    if input_el:
                        aff_url = input_el.get_attribute("value")
                
                # C) Fallback: varrer o popover por qualquer texto que pareça um link do ML
                if not aff_url:
                    elements = page.query_selector_all(".andes-form-control__field, .andes-modal__content p")
                    for el in elements:
                        txt = el.inner_text().strip()
                        if "mercadolivre.com.br" in txt or "p.mercadolivre" in txt:
                            aff_url = txt
                            break

                if aff_url:
                    _log(q, f"✅ ML Item {count+1} coletado!")
                    q.put({"result": {"marketplace": "Mercado Livre", "link_produto": prod_url, "link_afiliado": aff_url}})
                    count += 1
                else:
                    _log(q, f"⚠️ ML Item {count+1}: Link de afiliado não encontrado no popover.")
                
                # 4. Esc para fechar popover
                page.keyboard.press("Escape")
                page.wait_for_timeout(1000)
                
            except Exception as e:
                _log(q, f"ML Erro no item {i+1}: {str(e)[:50]}")
                page.keyboard.press("Escape")
                continue

        if count == 0:
            _log(q, "⚠️ ML: Nenhum item completo coletado. Tente atualizar os cookies.")
            
    except Exception as e:
        _log(q, f"❌ ML Erro Fatal: {str(e)[:100]}")

def mine_shopee(page, config, q, ps, pe):
    cfg = config["marketplaces"]["Shopee"]
    qtd = config.get("qtd_produtos", 5)
    aid = cfg.get("affiliate_id", "").strip() or "0"
    if cfg.get("cookies"): _load_cookies(page, q, cfg["cookies"], "Shopee")
    try:
        page.goto("https://shopee.com.br/flash_sale", timeout=45000, wait_until="commit")
        page.wait_for_timeout(5000)
        _scroll_page_smooth(page, q, "Shopee")
        links = page.eval_on_selector_all('a[href*="-i."]', 'els => els.map(e => e.href)')
        valid = list(dict.fromkeys([_clean_url(l, "https://shopee.com.br") for l in links if "-i." in l]))[:qtd]
        for i, link in enumerate(valid):
            aff = _append_param(_append_param(link, "aff_id", aid), "aff_platform", "affiliate")
            q.put({"result": {"marketplace": "Shopee", "link_produto": link, "link_afiliado": aff}})
            _log(q, f"Shopee: {i+1}/{len(valid)} pronto.", ps + (pe-ps)*((i+1)/len(valid)))
    except Exception as e: _log(q, f"❌ Shopee Erro: {str(e)[:80]}")

# -----------------------------------------------------------------------
# Motor Principal
# -----------------------------------------------------------------------

def run_mining(config: dict):
    q = queue.Queue()
    if config.get("demo_mode", False):
        def demo():
            active = [m for m in ["Amazon", "Mercado Livre", "Shopee"] if config["marketplaces"][m]["active"]]
            for idx, m in enumerate(active):
                for i in range(config.get("qtd_produtos", 5)):
                    time.sleep(0.1)
                    q.put({"result": {"marketplace": m, "link_produto": f"https://{m.lower()}.com/p-{i}", "link_afiliado": f"https://{m.lower()}.com/a-{i}"}})
                    _log(q, f"[DEMO] {m} {i+1} pronto", (idx + (i+1)/config.get("qtd_produtos", 5))/len(active))
            q.put({"done": True})
        threading.Thread(target=demo, daemon=True).start()
    else:
        def worker():
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    _log(q, "Iniciando motor Playwright...")
                    browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
                    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
                    page = context.new_page()
                    active = [m for m in ["Amazon", "Mercado Livre", "Shopee"] if config["marketplaces"][m]["active"]]
                    seg = 1.0/len(active) if active else 1
                    miners = {"Amazon": mine_amazon, "Mercado Livre": mine_ml, "Shopee": mine_shopee}
                    for i, m in enumerate(active):
                        try: miners[m](page, config, q, i*seg, (i+1)*seg)
                        except Exception as e: _log(q, f"❌ {m} Fatal: {e}")
                    browser.close()
            except Exception as e: _log(q, f"❌ Erro Crítico: {e}")
            finally: q.put({"done": True})
        threading.Thread(target=worker, daemon=True).start()

    while True:
        item = q.get(timeout=300)
        if item.get("done"): break
        yield item
