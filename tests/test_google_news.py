from src.connectors.google_news import GoogleNewsConnector, build_query_url

SAMPLE = """<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Carlos Arias pide planeación - El País Cali</title>
<link>https://news.google.com/rss/articles/CBMi1</link><guid>CBMi1</guid>
<pubDate>Thu, 18 Sep 2026 12:00:00 GMT</pubDate>
<description>&lt;a href="x"&gt;Carlos Arias pide planeación&lt;/a&gt;&lt;font&gt;El País&lt;/font&gt;</description>
<source url="https://www.elpais.com.co">El País Cali</source></item>
</channel></rss>"""


def test_build_query_url_targets_colombia():
    url = build_query_url("Carlos Arias")
    assert "news.google.com/rss/search" in url
    assert "gl=CO" in url and "ceid=CO%3Aes-419" in url
    assert "Cali" in url and "when" not in url
    assert "when%3A7d" in build_query_url("Carlos Arias", window="7d")


def test_google_news_connector_one_item_per_term(monkeypatch):
    import feedparser
    real = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda url, **kw: real(SAMPLE))

    items = GoogleNewsConnector(pause_seconds=0).fetch(["Carlos Arias"])

    assert len(items) == 1
    assert items[0].external_id == "CBMi1"
    assert items[0].search_term == "Carlos Arias"
    assert items[0].author == "El País Cali"
    assert "<" not in items[0].text
