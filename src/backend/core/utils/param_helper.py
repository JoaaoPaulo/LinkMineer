def append_param(url: str, key: str, value: str) -> str:
    """Safely appends a query parameter to a URL."""
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{key}={value}"
