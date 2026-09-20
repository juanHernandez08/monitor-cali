from urllib.parse import urlsplit, parse_qsl, urlencode

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"fbclid", "igshid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src"}


def normalize_url(url: str | None) -> str | None:
    """URL canónica para deduplicar entre fuentes: sin esquema, www, tracking ni barra final."""
    if not url:
        return None
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(_TRACKING_PREFIXES) and k.lower() not in _TRACKING_KEYS
    ]
    path = parts.path.rstrip("/").lower()
    normalized = f"{host}{path}"
    if query:
        normalized += "?" + urlencode(query)
    return normalized or None
