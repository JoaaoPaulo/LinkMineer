"""
miner.py – Versão 11.0 (Deep Diagnostic Mode).
Focado em descobrir por que a lista de cards aparece vazia (0 cards).
Inclui validação de sessão e carregamento resiliente.
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
            _log(q, f"✅ {marketplace}: Cookies injetados.")
            return True
    except Exception as e:
        _log(q, f"❌ {marketplace}: Erro nos cookies: {str(e)[:50]}")
    return False

# -----------------------------------------------------------------------
# Scrapers
# -----------------------------------------------------------------------

def mine_amazon(page, config, q, ps, pe, stop_event=None):
    cfg = config["marketplaces"]["Amazon"]
    qtd = config.get("qtd_produtos", 5)
    tag = cfg.get("tag", "").strip() or "tag-20"
    if cfg.get("cookies"): _load_cookies(page, q, cfg["cookies"], "Amazon")
    try:
        page.goto("https://www.amazon.com.br/gp/bestsellers/", timeout=45000)
        page.wait_for_timeout(3000)
        links = page.eval_on_selector_all('a[href*="/dp/"]', 'els => els.map(e => e.href)')
        valid = list(dict.fromkeys([_clean_url(l, "https://www.amazon.com.br") for l in links if "/dp/" in l]))[:qtd]
        for i, link in enumerate(valid):
            if stop_event and stop_event.is_set():
                _log(q, "Amazon: Interrupção solicitada pelo usuário.")
                break
            aff = _append_param(link, "tag", tag)
            q.put({"result": {"marketplace": "Amazon", "link_produto": link, "link_afiliado": aff}})
            _log(q, f"Amazon: {i+1}/{len(valid)} coletado", ps + (pe-ps)*((i+1)/len(valid)))
    except Exception as e: _log(q, f"❌ Amazon: {str(e)[:50]}")

def mine_ml(page, config, q, ps, pe, stop_event=None):
    cfg = config["marketplaces"]["Mercado Livre"]
    qtd = config.get("qtd_produtos", 5)
    hub_url = "https://www.mercadolivre.com.br/afiliados/hub#menu-user"
    
    _log(q, "ML: Iniciando motor diagnóstico (v11)...", ps)
    
    if not cfg.get("cookies"):
        _log(q, "⚠️ ML: Cookies ausentes! O Hub exige login.")
        return
    _load_cookies(page, q, cfg["cookies"], "ML")

    # Bloquear recursos pesados (Imagens, css, fontes, mídias) para velocidade máxima
    def block_resources(route):
        if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
            route.abort()
        else:
            route.continue_()
    page.route("**/*", block_resources)

    # Injeta interceptador de clipboard
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
        _log(q, f"ML: Navegando para {hub_url}...")
        # Usamos domcontentloaded para garantir que a estrutura base está lá
        page.goto(hub_url, timeout=60000, wait_until="domcontentloaded")
        
        _log(q, "ML: Verificando carregamento da página...")
        page.wait_for_timeout(5000)
        
        # Diagnóstico de Redirecionamento
        current_url = page.url
        current_title = page.title()
        _log(q, f"ML Info: URL={current_url} | Title={current_title}")
        
        if "login" in current_url.lower() or "auth" in current_url.lower():
            _log(q, "❌ ML: Redirecionado para Login! Seus cookies podem estar expirados.")
            return

        # Busca cards com espera explícita
        _log(q, "ML: Aguardando cards (.andes-card) aparecerem de fato...")
        try:
            page.wait_for_selector(".andes-card", timeout=20000)
        except:
            _log(q, "⚠️ ML: Timeout aguardando '.andes-card'. Tentando seletor reserva...")
        
        count = 0
        processed_links = set()
        scroll_attempts = 0
        # Aumentamos o limite de scroll para suportar batches grandes (ex: 500 itens)
        max_scroll_attempts = max(30, (qtd // 2) + 10)

        while count < qtd and scroll_attempts < max_scroll_attempts:
            if stop_event and stop_event.is_set():
                _log(q, "ML: Interrupção solicitada pelo usuário.")
                break

            # Lista cards visíveis
            cards = page.query_selector_all(".andes-card, [class*='card']")
            _log(q, f"ML: {len(cards)} cards detectados na vista atual.")
            
            if not cards:
                # Se não tem nada e é a primeira vez, pode ser renderização lenta
                _log(q, "ML: Tentando rolar um pouco para forçar renderização...")
                page.keyboard.press("PageDown")
                page.wait_for_timeout(2000)
                scroll_attempts += 1
                continue

            found_in_round = 0
            for card in cards:
                if count >= qtd: break
                if stop_event and stop_event.is_set(): break
                
                try:
                    # Produto Link
                    link_el = card.query_selector("a[href*='mercadolivre.com.br']")
                    if not link_el: continue
                    p_url = _clean_url(link_el.get_attribute("href"))
                    
                    if p_url in processed_links: continue
                    processed_links.add(p_url)

                    card.scroll_into_view_if_needed()
                    
                    # Botão Compartilhar
                    share_btn = card.query_selector("button:has-text('Compartilhar'), .andes-button--share")
                    if not share_btn: continue
                    share_btn.click()
                    
                    # Clicou, não espera estático 2.5s. Esperamos ativamente o pop-up aparecer pelas classes:
                    try:
                        page.wait_for_selector("button:has-text('Copiar link')", timeout=3000)
                    except:
                        pass # Continua se não aparecer logo, para não travar
                    
                    # Copiar Link
                    page.evaluate("window._lastCopiedLink = '';")
                    copy_btn = page.query_selector("button:has-text('Copiar link')")
                    if copy_btn:
                        copy_btn.click()
                        # Reduzido de 1s para o tempo estrito que o clipboard processa via JS
                        page.wait_for_timeout(150)
                    
                    aff_url = page.evaluate("window._lastCopiedLink")
                    if not aff_url:
                        inp = page.query_selector("input.andes-form-control__field")
                        if inp: aff_url = inp.get_attribute("value")

                    if aff_url:
                        _log(q, f"✅ ML Item {count+1} disparado na velocidade da luz.")
                        q.put({"result": {"marketplace": "Mercado Livre", "link_produto": p_url, "link_afiliado": aff_url}})
                        count += 1
                        found_in_round += 1
                        _log(q, f"ML Progresso: {count}/{qtd}", ps + (pe-ps)*(count/qtd))
                    
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(100) # De 500ms para 100ms
                except:
                    page.keyboard.press("Escape")
                    continue

            # Controle de Rolagem
            if (found_in_round == 0 or count < qtd) and not (stop_event and stop_event.is_set()):
                scroll_attempts += 1
                _log(q, f"ML: Rolagem {scroll_attempts} / {max_scroll_attempts}...")
                page.keyboard.press("PageDown")
                page.wait_for_timeout(2000)

        if count == 0 and not (stop_event and stop_event.is_set()):
            _log(q, "❌ ML: Falha total na coleta. Verifique se os cookies permitem acesso ao Hub.")
            
    except Exception as e:
        _log(q, f"❌ ML Erro Fatal: {str(e)[:150]}")

def mine_shopee(page, config, q, ps, pe, stop_event=None):
    cfg = config["marketplaces"]["Shopee"]
    qtd = config.get("qtd_produtos", 5)
    aid = cfg.get("affiliate_id", "").strip() or "0"
    if cfg.get("cookies"): _load_cookies(page, q, cfg["cookies"], "Shopee")
    try:
        page.goto("https://shopee.com.br/flash_sale", timeout=45000)
        page.wait_for_timeout(5000)
        page.keyboard.press("End")
        page.wait_for_timeout(1000)
        links = page.eval_on_selector_all('a[href*="-i."]', 'els => els.map(e => e.href)')
        valid = list(dict.fromkeys([_clean_url(l, "https://shopee.com.br") for l in links if "-i." in l]))[:qtd]
        for i, link in enumerate(valid):
            if stop_event and stop_event.is_set():
                _log(q, "Shopee: Interrupção solicitada pelo usuário.")
                break
            aff = _append_param(_append_param(link, "aff_id", aid), "aff_platform", "affiliate")
            q.put({"result": {"marketplace": "Shopee", "link_produto": link, "link_afiliado": aff}})
            _log(q, f"Shopee: {i+1}/{len(valid)} pronto", ps + (pe-ps)*((i+1)/len(valid)))
    except Exception as e: _log(q, f"❌ Shopee: {str(e)[:50]}")

def mine_generic_stub(page, config, q, ps, pe, marketplace, stop_event=None):
    """Stub genérico para marketplaces ainda não configurados."""
    _log(q, f"ℹ️ {marketplace}: Configuração pendente... Pulando.", pe)
    time.sleep(0.5)

def mine_pichau(page, config, q, ps, pe, stop_event=None):
    mine_generic_stub(page, config, q, ps, pe, "Pichau", stop_event)

def mine_kabum(page, config, q, ps, pe, stop_event=None):
    mine_generic_stub(page, config, q, ps, pe, "Kabum", stop_event)

def mine_magalu(page, config, q, ps, pe, stop_event=None):
    mine_generic_stub(page, config, q, ps, pe, "Magalu", stop_event)

def mine_girafa(page, config, q, ps, pe, stop_event=None):
    mine_generic_stub(page, config, q, ps, pe, "Girafa", stop_event)

# -----------------------------------------------------------------------
# Motor Principal
# -----------------------------------------------------------------------

def run_mining(config):
    q = queue.Queue()
    stop_event = config.get("stop_event")
    
    if config.get("demo_mode", False):
        def d():
            for m in [k for k,v in config["marketplaces"].items() if v["active"]]:
                if stop_event and stop_event.is_set(): break
                for i in range(config.get("qtd_produtos", 5)):
                    if stop_event and stop_event.is_set(): break
                    q.put({"result": {"marketplace": m, "link_produto": "http://p", "link_afiliado": "http://a"}})
                    time.sleep(0.05)
            q.put({"done": True})
        threading.Thread(target=d, daemon=True).start()
    else:
        def worker():
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    _log(q, "Abrindo Navegador...")
                    browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-dev-shm-usage"])
                    context = browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                        permissions=["clipboard-read", "clipboard-write"]
                    )
                    page = context.new_page()
                    active = [m for m in ["Amazon", "Mercado Livre", "Shopee", "Pichau", "Kabum", "Magalu", "Girafa"] if config["marketplaces"].get(m, {}).get("active")]
                    seg = 1.0/len(active) if active else 1
                    miners = {
                        "Amazon": mine_amazon, 
                        "Mercado Livre": mine_ml, 
                        "Shopee": mine_shopee,
                        "Pichau": mine_pichau,
                        "Kabum": mine_kabum,
                        "Magalu": mine_magalu,
                        "Girafa": mine_girafa
                    }
                    for i, m in enumerate(active):
                        if stop_event and stop_event.is_set():
                            _log(q, f"Interrompendo antes de iniciar {m}...")
                            break
                        try: miners[m](page, config, q, i*seg, (i+1)*seg, stop_event=stop_event)
                        except Exception as e: _log(q, f"❌ {m} Fatal: {e}")
                    browser.close()
            except Exception as e: _log(q, f"❌ Erro Crítico: {e}")
            finally: q.put({"done": True})
        threading.Thread(target=worker, daemon=True).start()

    while True:
        try:
            item = q.get(timeout=1800) # 30 minutos para batches gigantescos
            if item.get("done"): break
            yield item
        except: break
