from src.connectors.news_rss import RSSConnector

SAMPLE_FEED = """<?xml version="1.0"?>
<rss version="2.0">
<channel>
<title>Feed de prueba</title>
<item>
<title>Ana Pérez presenta plan de seguridad</title>
<summary>La candidata Ana Pérez anunció medidas para Cali.</summary>
<link>https://example.com/nota-1</link>
<guid>nota-1</guid>
<pubDate>Mon, 01 Sep 2026 10:00:00 GMT</pubDate>
</item>
<item>
<title>Buenos Ciudadanos: balance de Carlos Arias en el Concejo</title>
<summary>Un repaso a la gestión del presidente del Concejo.</summary>
<link>https://example.com/nota-2</link>
<guid>nota-2</guid>
</item>
<item>
<title>Partido de fútbol en Cali</title>
<summary>Resultado del clásico vallecaucano.</summary>
<link>https://example.com/nota-3</link>
<guid>nota-3</guid>
</item>
</channel>
</rss>"""


def test_rss_connector_filters_by_search_terms(monkeypatch):
    import feedparser
    real_parse = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda url: real_parse(SAMPLE_FEED))

    connector = RSSConnector(feed_url="https://example.com/feed.xml")
    items = connector.fetch(search_terms=["Ana Pérez", "Buenos Ciudadanos"])

    ids = {item.external_id for item in items}
    assert ids == {"nota-1", "nota-2"}


def test_rss_connector_can_return_whole_feed_for_city_sources(monkeypatch):
    import feedparser
    real_parse = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda url: real_parse(SAMPLE_FEED))
    items = RSSConnector(feed_url="https://example.com/feed.xml", filter_terms=False).fetch(search_terms=["Ana Pérez"])
    assert {i.external_id for i in items} == {"nota-1", "nota-2", "nota-3"}


HTML_FEED = """<?xml version="1.0"?>
<rss version="2.0">
<channel>
<title>Feed de prueba</title>
<item>
<title>Ana Pérez presenta plan de seguridad</title>
<summary>&lt;p&gt;La candidata Ana P&amp;eacute;rez anunci&amp;oacute; medidas. &lt;a href="https://example.com"&gt;Ver más&lt;/a&gt;&lt;/p&gt;</summary>
<link>https://example.com/nota-1</link>
<guid>nota-1</guid>
</item>
</channel>
</rss>"""


def test_rss_connector_strips_html_from_summary(monkeypatch):
    import feedparser
    real_parse = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda url: real_parse(HTML_FEED))
    items = RSSConnector(feed_url="https://example.com/feed.xml").fetch(search_terms=["Ana Pérez"])
    assert len(items) == 1
    assert "<p>" not in items[0].text
    assert "<a href" not in items[0].text
    assert "Ver más" in items[0].text
