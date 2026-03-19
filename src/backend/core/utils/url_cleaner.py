from urllib.parse import urlparse, urlunparse, urljoin

def clean_url(url: str, base_url: str = "https://www.mercadolivre.com.br") -> str:
    """Removes query parameters and fragments from a URL, and makes it absolute if needed."""
    try:
        if not url:
            return ""
        if url.startswith("/"):
            url = urljoin(base_url, url)
        p = urlparse(url)
        # Reconstruct URL without query params (p.query = "") and fragments (p.fragment = "")
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except Exception:
        return url
