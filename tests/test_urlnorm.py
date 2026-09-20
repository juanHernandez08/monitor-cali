from src.urlnorm import normalize_url


def test_strips_scheme_www_utm_and_trailing_slash():
    url = "https://www.ElPais.com.co/cali/nota-1/?utm_source=x&utm_medium=y&fbclid=abc"
    assert normalize_url(url) == "elpais.com.co/cali/nota-1"


def test_keeps_meaningful_query_params():
    assert normalize_url("https://youtube.com/watch?v=abc&igshid=1") == "youtube.com/watch?v=abc"


def test_none_and_empty():
    assert normalize_url(None) is None
    assert normalize_url("") is None
