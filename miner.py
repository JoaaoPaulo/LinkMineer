"""
miner.py – Núcleo de automação do LinkMineer.

Estratégia de links afiliados:
  - Amazon      : scrape de bestsellers; fallback de link com ?tag=
  - Mercado Livre: scrape de ofertas; link com ?tracking_id=
  - Shopee      : scrape de flash sale/home; link com ?aff_id=&aff_platform=affiliate

Modo headless: detectado automaticamente.
  - Railway/servidor: PLAYWRIGHT_HEADLESS=true -> headless=True
  - Localmente      : PLAYWRIGHT_HEADLESS não definida -> headless=False
    (permite resolver captchas/2FA manualmente)

Threading: usa queue.Queue para comunicar progresso ao Streamlit sem race conditions.
"""

import json
import os
import time
import queue
import threading
from urllib.parse import urlparse, urlunparse

# -----------------------------------------------------------------------
# Detecta se estamos rodando em servidor (Railway/Heroku) ou localmente.
# Em servidor, o Chromium DEVE ser headless (sem janela gráfica).
# Para forçar um modo: defina PLAYWRIGHT_HEADLESS=true ou false.
# -----------------------------------------------------------------------
_IS_SERVER = os.environ.get("RAILWAY_ENVIRONMENT") is not None or \
             os.environ.get("PORT") is not None
HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "true" if _IS_SERVER else "false").lower() == "true"


# -----------------------------------------------------------------------
# Helpers de URL
# -----------------------------------------------------------------------

def _clean_url(url: str) -> str:
    """Remove parâmetros de rastreamento, mantendo apenas scheme + host + path."""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def _append_param(url: str, key: str, value: str) -> str:
    """Adiciona um query param à URL, respeitando se já existe '?'."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={value}"


def _load_cookies(page, cookies_json: str) -> bool:
    """
    Injeta cookies no contexto do Playwright.
    Aceita formato JSON array (exportado do DevTools do Chrome).
    Retorna True se bem-sucedido.
    """
    try:
        cookies = json.loads(cookies_json)
        if isinstance(cookies, list) and cookies:
            page.context.add_cookies(cookies)
            return True
    except Exception:
        pass
    return False


# -----------------------------------------------------------------------
# Dados de exemplo para o Modo Demo (sem navegador)
# -----------------------------------------------------------------------

DEMO_PRODUCTS = {
    "Amazon": [
        "https://www.amazon.com.br/dp/B0C4J5L9QP",
        "https://www.amazon.com.br/dp/B09G3GNY2N",
        "https://www.amazon.com.br/dp/B0B17W6SNX",
        "https://www.amazon.com.br/dp/B07PXGQC1Q",
        "https://www.amazon.com.br/dp/B0829DL42W",
    ],
    "Mercado Livre": [
        "https://www.mercadolivre.com.br/apple-iphone-15-128-gb/p/MLB27580088",
        "https://www.mercadolivre.com.br/air-fryer-philips/p/MLB21765432",
        "https://www.mercadolivre.com.br/notebook-dell-i5/p/MLB30001234",
        "https://www.mercadolivre.com.br/smart-tv-samsung-55/p/MLB22443355",
        "https://www.mercadolivre.com.br/aspirador-robotic/p/MLB19887766",
    ],
    "Shopee": [
        "https://shopee.com.br/produto-fone-bluetooh-i.123456.789012",
        "https://shopee.com.br/produto-relogio-smart-i.234567.890123",
        "https://shopee.com.br/produto-capa-celular-i.345678.901234",
        "https://shopee.com.br/produto-carregador-i.456789.012345",
        "https://shopee.com.br/produto-mouse-gamer-i.567890.123456",
    ],
}


def run_mining_demo(config: dict, q: queue.Queue):
    """
    Modo Demo: simula a mineração com produtos fictícios.
    Não abre nenhum navegador. Útil para testar a interface e o download.
    """
    qtd = config.get("qtd_produtos", 5)
    # Conta quantos marketplaces estão ativos
    active = [
        mp for mp in ["Amazon", "Mercado Livre", "Shopee"]
        if config["marketplaces"].get(mp, {}).get("active", False)
    ]
    total = qtd * len(active) if active else 1
    done = 0

    for marketplace in active:
        cfg = config["marketplaces"][marketplace]
        products = DEMO_PRODUCTS.get(marketplace, [])

        for i, link in enumerate(products[:qtd]):
            time.sleep(0.25)  # simula tempo de navegação

            # Gera link afiliado de acordo com o marketplace
            if marketplace == "Amazon":
                tag = cfg.get("tag", "demo-20")
                affiliate_link = _append_param(link, "tag", tag)

            elif marketplace == "Mercado Livre":
                tracking_id = cfg.get("tracking_id", "").strip()
                matt_tool = cfg.get("matt_tool", "").strip()
                
                affiliate_link = link
                if tracking_id:
                    affiliate_link = _append_param(affiliate_link, "tracking_id", tracking_id)
                if matt_tool:
                    # Se o matt_tool já tiver '=', anexa direto, senão prefixa com matt_tool=
                    if "=" in matt_tool:
                        sep = "&" if "?" in affiliate_link else "?"
                        affiliate_link = f"{affiliate_link}{sep}{matt_tool}"
                    else:
                        affiliate_link = _append_param(affiliate_link, "matt_tool", matt_tool)
            
            else:  # Shopee
                aff_id = cfg.get("affiliate_id", "0")
                affiliate_link = _append_param(link, "aff_id", aff_id)
                affiliate_link = _append_param(affiliate_link, "aff_platform", "affiliate")

            done += 1
            progress = done / total
            q.put({"progress": progress, "message": f"[DEMO] {marketplace}: produto {i+1}/{min(qtd, len(products))}"})
            q.put({"result": {"marketplace": marketplace, "link_produto": link, "link_afiliado": affiliate_link}})

    q.put({"done": True})


# -----------------------------------------------------------------------
# Minerador Amazon
# -----------------------------------------------------------------------

def mine_amazon(page, config: dict, q: queue.Queue, p_start: float, p_end: float):
    """
    Coleta produtos da página de mais vendidos da Amazon.
    Tenta usar o SiteStripe (barra de afiliados) para gerar link oficial;
    caso falhe, constrói o link com ?tag= (igualmente válido para comissão).
    """
    cfg = config["marketplaces"]["Amazon"]
    qtd = config.get("qtd_produtos", 5)
    tag = cfg.get("tag", "").strip() or "tag-20"

    q.put({"progress": p_start, "message": "Amazon: preparando sessão..."})

    # Injeta cookies se fornecidos
    if cfg.get("login_type") == "Cookies" and cfg.get("cookies"):
        _load_cookies(page, cfg["cookies"])

    # Tenta múltiplas URLs de produtos populares
    source_urls = [
        "https://www.amazon.com.br/gp/bestsellers/",
        "https://www.amazon.com.br/s?k=mais+vendidos",
        "https://www.amazon.com.br/",
    ]

    product_links = []
    for url in source_urls:
        try:
            page.goto(url, timeout=25000)
            page.wait_for_load_state("domcontentloaded", timeout=12000)
            page.wait_for_timeout(2000)

            # Tenta múltiplos seletores CSS para capturar links de produto
            for sel in [
                'a[href*="/dp/"]',
                '.s-result-item a[href*="/dp/"]',
                '[data-asin] a[href*="/dp/"]',
                '.a-carousel-card a[href*="/dp/"]',
            ]:
                try:
                    links = page.eval_on_selector_all(
                        sel,
                        'els => [...new Set(els.map(e => e.href).filter(h => h.includes("/dp/")))]'
                    )
                    cleaned = [_clean_url(l) for l in links if "/dp/" in l]
                    product_links = list(dict.fromkeys(cleaned))  # deduplica mantendo ordem
                    if product_links:
                        break
                except Exception:
                    continue

            if product_links:
                break
        except Exception as e:
            q.put({"progress": p_start + 0.02, "message": f"Amazon: erro em {url}: {e}"})

    product_links = product_links[:qtd]

    if not product_links:
        q.put({"progress": p_end, "message": "Amazon: nenhum produto encontrado."})
        return

    q.put({"progress": p_start + 0.05,
           "message": f"Amazon: {len(product_links)} produto(s) encontrado(s). Gerando links..."})

    for i, link in enumerate(product_links):
        affiliate_link = ""

        try:
            page.goto(link, timeout=20000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)

            # Tenta clicar no botão de "Texto" do SiteStripe (barra de afiliados Amazon)
            for ss_sel in ["#amzn-ss-text-link-button", "#amzn-ss-text-shortlink-button"]:
                try:
                    if page.locator(ss_sel).count() > 0:
                        page.click(ss_sel, timeout=3000)
                        page.wait_for_timeout(1500)
                        for ls in ["#amzn-ss-text-shortlink-textarea", "textarea[id*='shortlink']"]:
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

        # Fallback: constrói o link com a tag — igualmente válido para rastreio de comissão
        if not affiliate_link:
            affiliate_link = _append_param(link, "tag", tag)

        progress = p_start + (p_end - p_start) * ((i + 1) / len(product_links))
        q.put({"progress": progress, "message": f"Amazon: {i+1}/{len(product_links)} coletados"})
        q.put({"result": {"marketplace": "Amazon", "link_produto": link, "link_afiliado": affiliate_link}})


# -----------------------------------------------------------------------
# Minerador Mercado Livre
# -----------------------------------------------------------------------

def mine_ml(page, config: dict, q: queue.Queue, p_start: float, p_end: float):
    """
    Coleta produtos da página de ofertas do Mercado Livre.
    Gera o link afiliado adicionando o parâmetro tracking_id à URL do produto.
    """
    cfg = config["marketplaces"]["Mercado Livre"]
    qtd = config.get("qtd_produtos", 5)
    tracking_id = cfg.get("tracking_id", "").strip() or "tracking_id"

    q.put({"progress": p_start, "message": "Mercado Livre: preparando sessão..."})

    # Injeta cookies se fornecidos
    if cfg.get("login_type") == "Cookies" and cfg.get("cookies"):
        _load_cookies(page, cfg["cookies"])
    elif cfg.get("login_type") == "Credentials" and cfg.get("user"):
        # Tentativa de login via credenciais (pode exigir interação manual local)
        try:
            page.goto("https://www.mercadolivre.com.br/navigation/login", timeout=20000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            for sel in ["#user_id", 'input[name="user_id"]', 'input[type="email"]']:
                if page.locator(sel).count() > 0:
                    page.fill(sel, cfg["user"])
                    break
            page.click('button[type="submit"]')
            page.wait_for_timeout(2500)
            for sel in ["#password", 'input[type="password"]']:
                if page.locator(sel).count() > 0:
                    page.fill(sel, cfg["password"])
                    break
            page.click('button[type="submit"]')
            page.wait_for_timeout(3000)
        except Exception as e:
            q.put({"progress": p_start + 0.02, "message": f"ML: aviso no login: {e}"})

    # Fontes de produtos para scrape
    source_urls = [
        "https://www.mercadolivre.com.br/ofertas",
        "https://www.mercadolivre.com.br/",
        "https://www.mercadolivre.com.br/mais-vendidos",
    ]

    product_links = []
    for url in source_urls:
        try:
            page.goto(url, timeout=25000)
            page.wait_for_load_state("domcontentloaded", timeout=12000)
            page.wait_for_timeout(2500)

            for sel in [
                ".promotion-item__link",
                ".poly-component__title a",
                ".ui-search-item__group--title a",
                'a[href*="mercadolivre.com.br"][href*="/p/MLB"]',
                'a[href*="mercadolivre.com.br/MLB"]',
                'a[href*="/MLB"]',
            ]:
                try:
                    links = page.eval_on_selector_all(
                        sel,
                        'els => [...new Set(els.map(e => e.href).filter(h => h.includes("mercadolivre.com.br")))]'
                    )
                    cleaned = [_clean_url(l) for l in links if "mercadolivre.com.br" in l]
                    product_links = list(dict.fromkeys(cleaned))
                    if product_links:
                        break
                except Exception:
                    continue

            if product_links:
                break
        except Exception as e:
            q.put({"progress": p_start + 0.02, "message": f"ML: erro em {url}: {e}"})

    product_links = product_links[:qtd]

    if not product_links:
        q.put({"progress": p_end, "message": "ML: nenhum produto encontrado."})
        return

    q.put({"progress": p_start + 0.05,
           "message": f"ML: {len(product_links)} produto(s) encontrado(s). Gerando links..."})

    for i, link in enumerate(product_links):
        # Suporte para ID simples e/ou string completa do Matt Tool
        affiliate_link = link
        
        if tracking_id:
            affiliate_link = _append_param(affiliate_link, "tracking_id", tracking_id)
            
        if matt_tool:
            if "=" in matt_tool:
                sep = "&" if "?" in affiliate_link else "?"
                affiliate_link = f"{affiliate_link}{sep}{matt_tool}"
            else:
                affiliate_link = _append_param(affiliate_link, "matt_tool", matt_tool)

        progress = p_start + (p_end - p_start) * ((i + 1) / len(product_links))
        q.put({"progress": progress, "message": f"ML: {i+1}/{len(product_links)} coletados"})
        q.put({"result": {"marketplace": "Mercado Livre", "link_produto": link, "link_afiliado": affiliate_link}})


# -----------------------------------------------------------------------
# Minerador Shopee
# -----------------------------------------------------------------------

def mine_shopee(page, config: dict, q: queue.Queue, p_start: float, p_end: float):
    """
    Coleta produtos da home/flash sale da Shopee.
    Gera link de afiliado com parâmetros aff_id e aff_platform.
    """
    cfg = config["marketplaces"]["Shopee"]
    qtd = config.get("qtd_produtos", 5)
    aff_id = cfg.get("affiliate_id", "").strip() or "0"

    q.put({"progress": p_start, "message": "Shopee: preparando sessão..."})

    # Injeta cookies se fornecidos
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
            q.put({"progress": p_start + 0.02, "message": f"Shopee: aviso no login: {e}"})

    source_urls = [
        "https://shopee.com.br/",
        "https://shopee.com.br/flash_sale",
        "https://shopee.com.br/Smartphones-cat.11228048",
    ]

    product_links = []
    for url in source_urls:
        try:
            page.goto(url, timeout=25000)
            page.wait_for_load_state("domcontentloaded", timeout=12000)
            page.wait_for_timeout(3500)

            for sel in [
                'a[href*="-i."]',
                'a[data-sqe="link"]',
                'a[href*="shopee.com.br"][href*="-i."]',
            ]:
                try:
                    links = page.eval_on_selector_all(
                        sel,
                        'els => [...new Set(els.map(e => e.href).filter(h => h.includes("-i.")))]'
                    )
                    cleaned = [_clean_url(l) for l in links if "shopee.com.br" in l and "-i." in l]
                    product_links = list(dict.fromkeys(cleaned))
                    if product_links:
                        break
                except Exception:
                    continue

            if product_links:
                break
        except Exception as e:
            q.put({"progress": p_start + 0.02, "message": f"Shopee: erro em {url}: {e}"})

    product_links = product_links[:qtd]

    if not product_links:
        q.put({"progress": p_end, "message": "Shopee: nenhum produto encontrado."})
        return

    q.put({"progress": p_start + 0.05,
           "message": f"Shopee: {len(product_links)} produto(s) encontrado(s). Gerando links..."})

    for i, link in enumerate(product_links):
        # Link afiliado Shopee: parâmetros padrão do programa de afiliados
        affiliate_link = _append_param(link, "aff_id", aff_id)
        affiliate_link = _append_param(affiliate_link, "aff_platform", "affiliate")

        progress = p_start + (p_end - p_start) * ((i + 1) / len(product_links))
        q.put({"progress": progress, "message": f"Shopee: {i+1}/{len(product_links)} coletados"})
        q.put({"result": {"marketplace": "Shopee", "link_produto": link, "link_afiliado": affiliate_link}})


# -----------------------------------------------------------------------
# Entry point principal – gerador de progresso
# -----------------------------------------------------------------------

def run_mining(config: dict):
    """
    Generator principal. Roda a mineração em thread separada e faz yield de updates.
    Cada update é um dict que pode conter:
      - {"progress": float, "message": str}  → atualiza a barra de progresso
      - {"result": dict}                      → um produto coletado
      - {"done": True}                        → sinaliza fim da execução

    Uso:
        for update in run_mining(config):
            if "result" in update:
                results.append(update["result"])
    """
    q = queue.Queue()

    # ---- Modo Demo: sem navegador ----
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

    # ---- Modo Real: Playwright ----
    active_markets = [
        mp for mp in ["Amazon", "Mercado Livre", "Shopee"]
        if config["marketplaces"].get(mp, {}).get("active", False)
    ]

    if not active_markets:
        yield {"progress": 1.0, "message": "Nenhum marketplace ativo selecionado."}
        return

    # Divide o espaço de progresso igualmente entre os marketplaces ativos
    segment = 1.0 / len(active_markets)
    market_ranges = {
        mp: (i * segment, (i + 1) * segment)
        for i, mp in enumerate(active_markets)
    }

    def worker():
        """Thread que executa o Playwright e envia updates via queue."""
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=HEADLESS,  # True em Railway, False localmente
                    args=[
                        "--no-sandbox",           # necessário em containers Linux
                        "--disable-dev-shm-usage", # evita crash por /dev/shm pequeno
                        "--disable-gpu",           # sem GPU em servidor
                    ]
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
                        q.put({"progress": p_end,
                               "message": f"{marketplace}: erro inesperado – {e}"})

                browser.close()

        except Exception as e:
            q.put({"progress": 1.0, "message": f"Erro fatal: {e}"})
        finally:
            q.put({"done": True})

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    # Consome a queue e faz yield dos updates para o Streamlit
    while True:
        try:
            item = q.get(timeout=120)  # espera até 2 min por update
            if item.get("done"):
                break
            yield item
        except queue.Empty:
            yield {"progress": 1.0, "message": "Timeout aguardando navegador. Encerrando."}
            break
