import json

def sanitize_cookies(cookies: list) -> list:
    """Validates and fixes cookie formats for Playwright execution."""
    valid_samesite = ["Strict", "Lax", "None"]
    sanitized = []
    
    for c in cookies:
        if not isinstance(c, dict): 
            continue
            
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

def load_cookies_to_page(page, cookies_json: str, marketplace: str, logger=None):
    """Parses JSON cookies and adds them to the Playwright page context."""
    try:
        cookies = json.loads(cookies_json)
        if isinstance(cookies, list):
            sanitized = sanitize_cookies(cookies)
            page.context.add_cookies(sanitized)
            if logger: 
                logger.info(f"✅ {marketplace}: Cookies injetados.")
            return True
    except Exception as e:
        if logger: 
            logger.error(f"❌ {marketplace}: Erro nos cookies: {str(e)[:50]}")
    return False
