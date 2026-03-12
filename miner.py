"""
miner.py – Versão 7.0 (ML Hub Ultra-Diagnostic).
Re-implementado para máxima visibilidade e captura de links de afiliado.
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
        if url.startswith("/"):
            url = urljoin(base_url, url)
        p = urlparse(url)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except: return url

def _append_param(url: str, key: str, value: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={value}"

def _scroll_page_smooth(page, q: queue.Queue, marketplace: str):
    _log(q, f"{marketplace}: Rolando página para carregar conteúdo dinâmico...")
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
        _log(q, "Amazon: Acessando Bestsellers...")
        page.goto("https://www.amazon.com.br/gp/bestsellers/", timeout=45000, wait_until="domcontentloaded")
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
    hub_url = "https://www.mercadolivre.com.br/afiliados/hub#menu-user"
    
    _log(q, "ML: Iniciando scraping via Hub...", ps)
    if not cfg.get("cookies"):
        _log(q, "⚠️ ML: Cookies ausentes. O Hub exige login.")
        return
    _load_cookies(page, q, cfg["cookies"], "ML")
    
    try:
        _log(q, f"ML: Navegando para {hub_url}...")
        # Usamos wait_until="commit" para não travar em analytics/trackers do ML no Railway
        page.goto(hub_url, timeout=60000, wait_until="commit")
        
        _log(q, "ML: Aguardando carregamento da estrutura do Hub...")
        page.wait_for_timeout(7000) # Tempo maior para o Hub carregar os cards internos
        
        _scroll_page_smooth(page, q, "ML")
        
        # O Hub do ML usa cards da biblioteca 'andes'. Tentamos capturá-los.
        cards = page.query_selector_all(".andes-card")
        _log(q, f"ML Hub: {len(cards)} possíveis produtos (cards) detectados.")
        
        if not cards:
            _log(q, "⚠️ ML Hub: Nenhum card encontrado. Verifique se os cookies estão válidos.")
            # Diagnóstico extra: Título da página
            _log(q, f"Página atual: {page.title()} | URL: {page.url}")
            return

        count = 0
        for i, card in enumerate(cards):
            if count >= qtd: break
            
            try:
                # 1. Capturar Link do Produto (Geralmente no título ou imagem)
                link_el = card.query_selector("a[href*='mercadolivre.com.br']")
                if not link_el: continue
                prod_url = _clean_url(link_el.get_attribute("href"))
                
                # 2. Clicar em Compartilhar
                # Buscamos o botão que costuma disparar o modal de link
                share_btn = card.query_selector("button:has-text('Compartilhar'), .andes-button--share, .andes-button--quiet")
                if not share_btn:
                    _log(q, f"ML Card {i+1}: Botão de compartilhamento não encontrado. Ignorando...")
                    continue
                
                _log(q, f"ML Card {i+1}: Abrindo menu de compartilhamento...")
                card.scroll_into_view_if_needed()
                share_btn.click()
                page.wait_for_timeout(3000) # Espera o popover/modal de link
                
                # 3. Capturar o Link de Afiliado no popover
                # Geralmente é um input de texto ou um componente de "Link copiado"
                aff_url = ""
                
                # Tenta input direto
                input_el = page.query_selector("input[value*='mercadolivre.com'], .andes-form-control__field input, input.andes-form-control__field")
                if input_el:
                    aff_url = input_el.get_attribute("value")
                
                # Fallback: Tenta ler o texto de algum campo que tenha o formato de link
                if not aff_url:
                    text_els = page.query_selector_all(".andes-form-control__field, .andes-list__item-primary")
                    for te in text_els:
                        val = te.inner_text().strip()
                        if "mercadolivre.com.br" in val or "mercado-livre.com" in val:
                            aff_url = val
                            break
                
                if aff_url:
                    _log(q, f"✅ ML: Link afiliado capturado: {aff_url[:50]}...")
                    q.put({"result": {"marketplace": "Mercado Livre", "link_produto": prod_url, "link_afiliado": aff_url}})
                    count += 1
                else:
                    _log(q, f"⚠️ ML Card {i+1}: Não consegui ler o link de afiliado no popover.")
                
                # Fecha popover para não atrapalhar o próximo
                page.keyboard.press("Escape")
                page.wait_for_timeout(1000)
                
            except Exception as e:
                _log(q, f"ML Erro no Card {i+1}: {str(e)[:50]}")
                page.keyboard.press("Escape")
                continue

        _log(q, f"ML: Finalizado. Total coletado: {count}/{qtd}", pe)
            
    except Exception as e:
        _log(q, f"❌ ML Erro Fatal: {str(e)[:100]}")

def mine_shopee(page, config, q, ps, pe):
    cfg = config["marketplaces"]["Shopee"]
    qtd = config.get("qtd_produtos", 5)
    aid = cfg.get("affiliate_id", "").strip() or "0"
    if cfg.get("cookies"): _load_cookies(page, q, cfg["cookies"], "Shopee")
    try:
        _log(q, "Shopee: Acessando Flash Sale...")
        page.goto("https://shopee.com.br/flash_sale", timeout=45000, wait_until="commit")
        page.wait_for_timeout(5000)
        _scroll_page_smooth(page, q, "Shopee")
        links = page.eval_on_selector_all('a[href*="-i."]', 'els => els.map(e => e.href)')
        valid = list(dict.fromkeys([_clean_url(l, "https://shopee.com.br") for l in links if "-i." in l]))[:qtd]
        for i, link in enumerate(valid):
            aff = _append_param(_append_param(link, "aff_id", aid), "aff_platform", "affiliate")
            q.put({"result": {"marketplace": "Shopee", "link_produto": link, "link_afiliado": aff}})
            _log(q, f"Shopee: {i+1}/{len(valid)} processado", ps + (pe-ps)*((i+1)/len(valid)))
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
                    q.put({"result": {"marketplace": m, "link_produto": f"https://{m.lower()}.com.br/prod-{i}", "link_afiliado": f"https://{m.lower()}.com.br/aff-{i}"}})
                    _log(q, f"[DEMO] {m} {i+1} coletado", (idx + (i+1)/config.get("qtd_produtos", 5))/len(active))
            q.put({"done": True})
        threading.Thread(target=demo, daemon=True).start()
    else:
        def worker():
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    _log(q, "Iniciando motor Playwright (Chrome Headless)...")
                    browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
                    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
                    page = context.new_page()
                    active = [m for m in ["Amazon", "Mercado Livre", "Shopee"] if config["marketplaces"][m]["active"]]
                    seg = 1.0/len(active) if active else 1
                    miners = {"Amazon": mine_amazon, "Mercado Livre": mine_ml, "Shopee": mine_shopee}
                    for i, m in enumerate(active):
                        try: miners[m](page, config, q, i*seg, (i+1)*seg)
                        except Exception as e: _log(q, f"❌ {m} Erro Fatal no Loop: {e}")
                    browser.close()
            except Exception as e: _log(q, f"❌ Erro Crítico no Navegador: {e}")
            finally: q.put({"done": True})
        threading.Thread(target=worker, daemon=True).start()

    while True:
        item = q.get(timeout=300)
        if item.get("done"): break
        yield item
