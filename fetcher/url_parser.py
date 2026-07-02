# fetcher/url_parser.py
from urllib.parse import urlparse, parse_qs

ALLOWED_DOMAINS = {"mcard.buct.edu.cn"}

def parse_card_url(url: str) -> str:
    """Extract openid from a BUCT campus card URL.

    Args:
        url: Full URL copied from WeCom campus card page.

    Returns:
        The openid string.

    Raises:
        ValueError: If the URL is invalid, missing openid, or contains
                     only an expired OAuth code.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError(f"Invalid URL: {url}")

    if parsed.hostname not in ALLOWED_DOMAINS:
        raise ValueError(
            f"Unsupported domain '{parsed.hostname}'. "
            f"Expected one of: {ALLOWED_DOMAINS}"
        )

    params = parse_qs(parsed.query)

    if "openid" in params and params["openid"][0]:
        return params["openid"][0]

    if "code" in params:
        raise ValueError(
            "URL contains an OAuth 'code' but no 'openid'. "
            "The code is single-use and likely expired. "
            "Please open the page in WeCom first, then copy the "
            "redirected URL that contains 'openid='."
        )

    raise ValueError(
        "No 'openid' parameter found in URL. "
        "Please copy the full URL from the campus card page in WeCom."
    )
