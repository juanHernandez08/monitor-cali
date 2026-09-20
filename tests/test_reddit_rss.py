from src.connectors.reddit_rss import RedditRSSConnector, build_search_url

SAMPLE = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><author><name>/u/caleño1</name></author>
<id>t3_abc</id><link href="https://www.reddit.com/r/Colombia/comments/abc/x/"/>
<updated>2026-09-18T10:00:00+00:00</updated>
<title>¿Qué opinan de Roberto Ortiz para la alcaldía?</title>
<content type="html">&lt;div&gt;El Chontico otra vez&lt;/div&gt;</content></entry></feed>"""


def test_build_search_url_joins_terms_with_or():
    url = build_search_url(["Roberto Ortiz", "Mabel Lara"])
    assert url.startswith("https://www.reddit.com/search.rss?q=")
    assert "%20OR%20" in url


def test_reddit_rss_connector(monkeypatch):
    import src.connectors.reddit_rss as m
    monkeypatch.setattr(m, "_download", lambda url: SAMPLE.encode())

    items = RedditRSSConnector(pause_seconds=0).fetch(["Roberto Ortiz"])

    assert len(items) == 1
    assert items[0].external_id == "t3_abc"
    assert items[0].author == "/u/caleño1"
    assert "Chontico" in items[0].text
    assert items[0].search_term is None
