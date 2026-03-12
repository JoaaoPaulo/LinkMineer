"""
miner.py – Núcleo de automação do LinkMineer.

Estratégia de links afiliados:
  - Amazon  : tenta SiteStripe (DOM injection); fallback ?tag=
  - ML      : scrape de ofertas; affiliate link via ?tracking_id=
  - Shopee  : scrape de home/flash sale; affiliate link via ?aff_id=&aff_platform=affiliate

Threading: usa queue.Queue para comunicar progresso ao Streamlit sem race-conditions.
"""

import json
import time
import queue
import threading
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_url(url: str) -> str:
    """Remove parâmetros de rastreamento desnecessários, mantendo o path limpo."""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def _append_param(url: str, key: str, value: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={value}"


def _load_cookies(page, cookies_json: str):
    """Injeta cookies no contexto do Playwright. Aceita JSON array."""
    try:
        cookies = json.loads(cookies_json)
        if isinstance(cookies, list) and cookies:
            page.context.add_cookies(cookies)
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Demo Mode
# ---------------------------------------------------------------------------

DEMO_PRODUCTS = {
    "Amazon": [
        "https://www.amazon.com.br/dp/B0C4J5L9QP",
        "https://www.amazon.com.br/dp/B09G3GNY2N",
        "https://www.amazon.com.br/dp/B0B17W6SNX",
        "https://www.amazon.com.br/dp/B07PXGQC1Q",
        "https://www.amazon.com.br/dp/B0829DL42W",
    ],
    "Mercado Livre": [
        "https://www.mercadolivre.com.br/produto-exemplo-1/p/MLB12345678",
        "https://www.mercadolivre.com.br/produto-exemplo-2/p/MLB98765432",
        "https://www.mercadolivre.com.br/produto-exemplo-3/p/MLB11223344",
        "https://www.mercadolivre.com.br/produto-exemplo-4/p/MLB55667788",
        "https://www.mercadolivre.com.br/produto-exemplo-5/p/MLB99001122",
    ],
    "Shopee": [
        "https://shopee.com.br/produto-exemplo-1-i.123456.789012",
        "https://shopee.com.br/produto-exemplo-2-i.234567.890123",
        "https://shopee.com.br/produto-exemplo-3-i.345678.901234",
        "https://shopee.com.br/produto-exemplo-4-i.456789.012345",
        "https://shopee.com.br/produto-exemplo-5-i.567890.123456",
    ],
}


def run_mining_demo(config: dict, q: queue.Queue):
    """Simula mineração com dados de exemplo, sem abrir navegador."""
    qtd = config.get("qtd_produtos", 5)
    total_markets = sum(
        1 for mp in ["Amazon", "Mercado Livre", "Shopee"]
        if config["marketplaces"].get(mp, {}).get("active", False)
    )
    total = qtd * total_markets
    done = 0

    for marketplace, products in DEMO_PRODUCTS.items():
        cfg = config["marketplaces"].get(marketplace, {})
        if not cfg.get("active", False):
            continue

        for i, link in enumerate(products[:qtd]):
            time.sleep(0.3)  # simula tempo de navegação

            if marketplace == "Amazon":
                tag = cfg.get("tag", "demo-20")
                affiliate_link = _append_param(link, "tag", tag)
            elif marketplace == "Mercado Livre":
                tracking_id = cfg.get("tracking_id", "demo_tracking")
                affiliate_link = _append_param(link, "tracking_id", tracking_id)
            else:  # Shopee
                aff_id = cfg.get("affiliate_id", "0")
                affiliate_link = _append_param(link, "aff_id", aff_id)
                affiliate_link = _append_param(affiliate_link, "aff_platform", "affiliate")

            done += 1
            progress = done / total if total > 0 else 1.0
            q.put({"progress": progress, "message": f"[DEMO] {marketplace}: produto {i+1}/{qtd}"})
            q.put({"result": {"marketplace": marketplace, "link_produto": link, "link_afiliado": affiliate_link}})

    q.put({"done": True})


# ---------------------------------------------------------------------------
# Amazon
# ---------------------------------------------------------------------------

def mine_amazon(page, config: dict, q: queue.Queue, progress_start: float, progress_end: float):
    cfg = config["marketplaces"]["Amazon"]
    qtd = config.get("qtd_produtos", 5)
    tag = cfg.get("tag", "").strip() or "tag-20"

    q.put({"progress": progress_start, "message": "Amazon: preparando sessão..."})

    # Autenticação
    if cfg.get("login_type") == "Cookies" and cfg.get("cookies"):
        _load_cookies(page, cfg["cookies"])

    # Navegar para produtos mais vendidos
    best_seller_urls = [
        "https://www.amazon.com.br/gp/bestsellers/",
        "https://www.amazon.com.br/s?k=mais+vendidos&emi=true",
    ]

    product_links = []
    for url in best_seller_urls:
        try:
            page.goto(url, timeout=20000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            page.wait_for_timeout(2000)

            # Múltiplos seletores para capturar links de produto
            selectors = [
                'a[href*="/dp/"]',
                '.s-result-item a[href*="/dp/"]',
                '.a-carousel-card a[href*="/dp/"]',
                '[data-asin] a[href*="/dp/"]',
            ]
            for sel in selectors:
                try:
                    links = page.eval_on_selector_all(
                        sel,
                        'els => [...new Set(els.map(e => e.href).filter(h => h.includes("/dp/"))))'
                    )
                    clean = [_clean_url(l) for l in links if "/dp/" in l]
                    product_links = list(dict.fromkeys(clean))  # deduplica mantendo ordem
                    if product_links:
                        break
                except Exception:
                    continue

            if product_links:
                break
        except Exception as e:
            q.put({"progress": progress_start + 0.02, "message": f"Amazon: erro ao acessar {url}: {e}"})

    product_links = product_links[:qtd]

    if not product_links:
        q.put({"progress": progress_end, "message": "Amazon: nenhum produto encontrado. Verifique conexão."})
        return

    q.put({"progress": progress_start + 0.05, "message": f"Amazon: {len(product_links)} produtos encontrados. Gerando links afiliados..."})

    for i, link in enumerate(product_links):
        affiliate_link = ""
        try:
            page.goto(link, timeout=20000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)

            # Tentar SiteStripe (barra da Amazon Associates no topo da página)
            ss_selectors = [
                "#amzn-ss-text-link-button",
                "#amzn-ss-text-shortlink-button",
                "a[id*='ss-text']",
            ]
            for ss_sel in ss_selectors:
                try:
                    if page.locator(ss_sel).count() > 0:
                        page.click(ss_sel, timeout=3000)
                        page.wait_for_timeout(1500)
                        link_selectors = [
                            "#amzn-ss-text-shortlink-textarea",
                            "textarea[id*='shortlink']",
                            "input[id*='shortlink']",
                        ]
                        for ls in link_selectors:
                            try:
                                val = page.input_value(ls, timeout=2000)
                                if val and "amzn" in val:
                                    affiliate_link = val
                                    break
                            except Exception:
                                pass
                        if affiliate_link:
                            break
                except Exception:
                    pass
        except Exception:
            pass

        # Fallback: construir link com tag
        if not affiliate_link:
            affiliate_link = _append_param(link, "tag", tag)

        progress = progress_start + (progress_end - progress_start) * ((i + 1) / len(product_links))
        q.put({"progress": progress, "message": f"Amazon: coletado {i+1}/{len(product_links)}"})
        q.put({"result": {"marketplace": "Amazon", "link_produto": link, "link_afiliado": affiliate_link}})


# ---------------------------------------------------------------------------
# Mercado Livre
# ---------------------------------------------------------------------------

def mine_ml(page, config: dict, q: queue.Queue, progress_start: float, progress_end: float):
    cfg = config["marketplaces"]["Mercado Livre"]
    qtd = config.get("qtd_produtos", 5)
    tracking_id = cfg.get("tracking_id", "").strip() or "tracking_id"

    q.put({"progress": progress_start, "message": "Mercado Livre: preparando sessão..."})

    # Autenticação
    if cfg.get("login_type") == "Cookies" and cfg.get("cookies"):
        _load_cookies(page, cfg["cookies"])
    elif cfg.get("login_type") == "Credentials" and cfg.get("user"):
        try:
            page.goto("https://www.mercadolivre.com.br/navigation/login", timeout=20000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            for sel in ["#user_id", 'input[name="user_id"]', 'input[type="email"]']:
                if page.locator(sel).count() > 0:
                    page.fill(sel, cfg["user"])
                    break
            page.click('button[type="submit"]')
            page.wait_for_timeout(2500)
            for sel in ["#password", 'input[name="password"]', 'input[type="password"]']:
                if page.locator(sel).count() > 0:
                    page.fill(sel, cfg["password"])
                    break
            page.click('button[type="submit"]')
            page.wait_for_timeout(3000)
        except Exception as e:
            q.put({"progress": progress_start + 0.02, "message": f"ML: aviso no login: {e}"})

    # Páginas de produtos para scrape
    source_urls = [
        "https://www.mercadolivre.com.br/ofertas",
        "https://www.mercadolivre.com.br/",
        "https://www.mercadolivre.com.br/mais-vendidos",
    ]

    product_links = []
    for url in source_urls:
        try:
            page.goto(url, timeout=20000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            page.wait_for_timeout(2000)

            selectors = [
                ".promotion-item__link",
                'a[href*="mercadolivre.com.br"][href*="/p/MLB"]',
                'a[href*="mercadolivre.com.br"][href*="/MLB"]',
                ".poly-component__title a",
                ".ui-search-item__group--title a",
                'a[class*="result-link"]',
                'a[href*="/MLB"]',
            ]
            for sel in selectors:
                try:
                    links = page.eval_on_selector_all(
                        sel,
                        'els => [...new Set(els.map(e => e.href).filter(h => h.includes("mercadolivre.com.br")))]'
                    )
                    clean = [_clean_url(l) for l in links if "mercadolivre.com.br" in l]
                    product_links = list(dict.fromkeys(clean))
                    if product_links:
                        break
                except Exception:
                    continue

            if product_links:
                break
        except Exception as e:
            q.put({"progress": progress_start + 0.02, "message": f"ML: erro ao acessar {url}: {e}"})

    product_links = product_links[:qtd]

    if not product_links:
        q.put({"progress": progress_end, "message": "ML: nenhum produto encontrado. Verifique conexão."})
        return

    q.put({"progress": progress_start + 0.05, "message": f"ML: {len(product_links)} produtos. Gerando links afiliados..."})

    for i, link in enumerate(product_links):
        affiliate_link = _append_param(link, "tracking_id", tracking_id)
        progress = progress_start + (progress_end - progress_start) * ((i + 1) / len(product_links))
        q.put({"progress": progress, "message": f"ML: coletado {i+1}/{len(product_links)}"})
        q.put({"result": {"marketplace": "Mercado Livre", "link_produto": link, "link_afiliado": affiliate_link}})


# ---------------------------------------------------------------------------
# Shopee
# ---------------------------------------------------------------------------

def mine_shopee(page, config: dict, q: queue.Queue, progress_start: float, progress_end: float):
    cfg = config["marketplaces"]["Shopee"]
    qtd = config.get("qtd_produtos", 5)
    aff_id = cfg.get("affiliate_id", "").strip() or "0"

    q.put({"progress": progress_start, "message": "Shopee: preparando sessão..."})

    # Autenticação
    if cfg.get("login_type") == "Cookies" and cfg.get("cookies"):
        _load_cookies(page, cfg["cookies"])
    elif cfg.get("login_type") == "Credentials" and cfg.get("user"):
        try:
            page.goto("https://shopee.com.br/buyer/login", timeout=20000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            page.wait_for_timeout(2000)
            for sel in ['input[name="loginKey"]', 'input[type="text"]']:
                if page.locator(sel).count() > 0:
                    page.fill(sel, cfg["user"])
                    break
            for sel in ['input[name="password"]', 'input[type="password"]']:
                if page.locator(sel).count() > 0:
                    page.fill(sel, cfg["password"])
                    break
            page.click('button:has-text("Log in"), button:has-text("Entre"), button[type="submit"]')
            page.wait_for_timeout(5000)
        except Exception as e:
            q.put({"progress": progress_start + 0.02, "message": f"Shopee: aviso no login: {e}"})

    source_urls = [
        "https://shopee.com.br/",
        "https://shopee.com.br/flash_sale",
        "https://shopee.com.br/Smartphones-cat.11228048",
    ]

    product_links = []
    for url in source_urls:
        try:
            page.goto(url, timeout=20000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            page.wait_for_timeout(3000)

            selectors = [
                'a[href*="-i."]',
                'a[data-sqe="link"]',
                'a[href*="shopee.com.br"][href*="-i."]',
            ]
            for sel in selectors:
                try:
                    links = page.eval_on_selector_all(
                        sel,
                        'els => [...new Set(els.map(e => e.href).filter(h => h.includes("-i.")))]'
                    )
                    clean = [_clean_url(l) for l in links if "shopee.com.br" in l and "-i." in l]
                    product_links = list(dict.fromkeys(clean))
                    if product_links:
                        break
                except Exception:
                    continue

            if product_links:
                break
        except Exception as e:
            q.put({"progress": progress_start + 0.02, "message": f"Shopee: erro ao acessar {url}: {e}"})

    product_links = product_links[:qtd]

    if not product_links:
        q.put({"progress": progress_end, "message": "Shopee: nenhum produto encontrado. Verifique conexão."})
        return

    q.put({"progress": progress_start + 0.05, "message": f"Shopee: {len(product_links)} produtos. Gerando links afiliados..."})

    for i, link in enumerate(product_links):
        affiliate_link = _append_param(link, "aff_id", aff_id)
        affiliate_link = _append_param(affiliate_link, "aff_platform", "affiliate")
        progress = progress_start + (progress_end - progress_start) * ((i + 1) / len(product_links))
        q.put({"progress": progress, "message": f"Shopee: coletado {i+1}/{len(product_links)}"})
        q.put({"result": {"marketplace": "Shopee", "link_produto": link, "link_afiliado": affiliate_link}})


# ---------------------------------------------------------------------------
# Main entry point (generator)
# ---------------------------------------------------------------------------

def run_mining(config: dict):
    """
    Generator que roda a mineração em thread separada e faz yield de updates.
    Cada update é um dict com chave 'progress', 'message', 'result' ou 'done'.
    """
    q = queue.Queue()

    # Modo demo: sem navegador
    if config.get("demo_mode", False):
        t = threading.Thread(target=run_mining_demo, args=(config, q), daemon=True)
        t.start()
        while True:
            try:
                item = q.get(timeout=30)
                if item.get("done"):
                    break
                yield item
            except queue.Empty:
                break
        return

    # Modo real: Playwright
    active_markets = [
        mp for mp in ["Amazon", "Mercado Livre", "Shopee"]
        if config["marketplaces"].get(mp, {}).get("active", False)
    ]

    if not active_markets:
        yield {"progress": 1.0, "message": "Nenhum marketplace ativo selecionado."}
        return

    # Divide o progresso igualmente entre marketplaces
    segment = 1.0 / len(active_markets)
    market_ranges = {
        mp: (i * segment, (i + 1) * segment)
        for i, mp in enumerate(active_markets)
    }

    def worker():
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,  # False para o usuário resolver captchas/2FA
                    args=["--start-maximized"]
                )
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 900},
                )
                page = context.new_page()

                miners = {
                    "Amazon": mine_amazon,
                    "Mercado Livre": mine_ml,
                    "Shopee": mine_shopee,
                }

                for marketplace in active_markets:
                    p_start, p_end = market_ranges[marketplace]
                    try:
                        miners[marketplace](page, config, q, p_start, p_end)
                    except Exception as e:
                        q.put({
                            "progress": p_end,
                            "message": f"{marketplace}: erro inesperado – {e}"
                        })

                browser.close()
        except Exception as e:
            q.put({"progress": 1.0, "message": f"Erro fatal no navegador: {e}"})
        finally:
            q.put({"done": True})

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    while True:
        try:
            item = q.get(timeout=120)  # timeout de 2 min por item
            if item.get("done"):
                break
            yield item
        except queue.Empty:
            yield {"progress": 1.0, "message": "Timeout aguardando o navegador. Encerrando."}
            break
