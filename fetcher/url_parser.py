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
            f"不支持的域名 '{parsed.hostname}'。"
            f"期望的域名: {ALLOWED_DOMAINS}"
        )

    params = parse_qs(parsed.query)

    if "openid" in params and params["openid"][0]:
        return params["openid"][0]

    if "code" in params:
        raise ValueError(
            "链接中包含 OAuth 'code' 但没有 'openid'。"
            "code 是一次性的且可能已过期。"
            "请先在企业微信中打开页面，然后复制包含 'openid=' 的完整链接。"
        )

    raise ValueError(
        "链接中未找到 'openid' 参数。"
        "请从企业微信中的校园卡页面复制完整链接。"
    )
