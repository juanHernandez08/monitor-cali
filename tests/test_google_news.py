from src.connectors.google_news import GoogleNewsConnector, build_query_url

SAMPLE = """<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Carlos Arias pide planeación - El País Cali</title>
<link>https://news.google.com/rss/articles/CBMi1</link><guid>CBMi1</guid>
<pubDate>Thu, 18 Sep 2026 12:00:00 GMT</pubDate>
<description>&lt;a href="x"&gt;Carlos Arias pide planeación&lt;/a&gt;&lt;font&gt;El País&lt;/font&gt;</description>
<source url="https://www.elpais.com.co">El País Cali</source></item>
</channel></rss>"""

SAMPLE_2 = """<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Otra nota - Q'hubo Cali</title>
<link>https://news.google.com/rss/articles/CBMi2</link><guid>CBMi2</guid>
<pubDate>Thu, 18 Sep 2026 12:00:00 GMT</pubDate>
<description>&lt;a href="x"&gt;Otra nota&lt;/a&gt;&lt;font&gt;Q'hubo&lt;/font&gt;</description>
<source url="https://www.qhubo.com">Q'hubo Cali</source></item>
</channel></rss>"""


def test_build_query_url_targets_colombia():
    url = build_query_url("Carlos Arias")
    assert "news.google.com/rss/search" in url
    assert "gl=CO" in url and "ceid=CO%3Aes-419" in url
    assert "Cali" in url and "when" not in url
    assert "when%3A7d" in build_query_url("Carlos Arias", window="7d")


def test_google_news_connector_queries_all_windows_and_dedups(monkeypatch):
    import feedparser
    real = feedparser.parse
    urls = []
    monkeypatch.setattr(feedparser, "parse", lambda url, **kw: (urls.append(url), real(SAMPLE))[1])

    items = GoogleNewsConnector(pause_seconds=0).fetch(["Carlos Arias"])

    assert len(urls) == 3 and sum("when" in u for u in urls) == 2  # relevancia + 60d + 7d
    assert len(items) == 1  # el mismo item en las 3 respuestas se deduplica
    assert items[0].external_id == "CBMi1"
    assert items[0].search_term == "Carlos Arias"
    assert items[0].author == "El País Cali"
    assert "<" not in items[0].text


def test_one_term_raising_does_not_lose_the_others(monkeypatch):
    """Mismo bug que se encontró y corrigió en youtube.py (2026-09-26): con 77 términos (9
    candidatos + 19 concejales, cada uno con sus alias) x 3 ventanas = ~231 peticiones por
    corrida, alguna eventualmente falla. feedparser normalmente no lanza (usa bozo), pero si
    algo sí lanza (DNS, un parseo raro), no debe perderse lo que ya funcionó en términos
    anteriores."""
    import feedparser
    real = feedparser.parse

    def fake_parse(url, **kw):
        if "falla" in url:
            raise OSError("DNS caída")
        if "tercero" in url:
            return real(SAMPLE_2)
        return real(SAMPLE)

    monkeypatch.setattr(feedparser, "parse", fake_parse)

    items = GoogleNewsConnector(pause_seconds=0).fetch(["primero", "falla", "tercero"])

    terms = {i.search_term for i in items}
    assert terms == {"primero", "tercero"}
