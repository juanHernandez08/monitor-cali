from src.connectors.x_apify import XApifyConnector


class FakeCredits:
    def __init__(self, remaining): self._r = remaining; self.used = 0
    def remaining(self): return self._r
    def consume(self, n): self._r -= n; self.used += n


POST = {"id": "100", "url": "https://x.com/claraluzroldan/status/100", "text": "Cali avanza", "createdAt": "Fri Sep 19 20:11:49 +0000 2026",
        "author": {"userName": "ClaraLuzRoldan"}, "likeCount": 51, "replyCount": 2, "retweetCount": 9, "isReply": False}
REPLY = {"id": "101", "url": "https://x.com/juan/status/101", "text": "No al continuismo", "createdAt": "2026-09-19T21:00:00.000Z",
         "author": {"userName": "juan"}, "likeCount": 3, "replyCount": 0, "retweetCount": 0, "isReply": True, "inReplyToId": "100"}
SELF_REPLY = {**REPLY, "id": "102", "author": {"userName": "ClaraLuzRoldan"}}


def test_posts_and_replies_via_apify(monkeypatch):
    calls = []

    class R:
        def __init__(self, p): self._p = p
        def raise_for_status(self): pass
        def json(self): return self._p

    def fake_post(url, params, json, timeout):
        calls.append(json)
        return R([POST] if "twitterHandles" in json else [REPLY, SELF_REPLY])

    import src.connectors.x_apify as m
    monkeypatch.setattr(m.requests, "post", fake_post)
    accounts = [{"platform": "x", "url": "https://x.com/claraluzroldan", "candidate": "Clara Luz Roldán"},
                {"platform": "instagram", "url": "https://www.instagram.com/x/", "candidate": "Otro"}]
    credits = FakeCredits(1000)
    c = XApifyConnector(token="t", accounts=accounts, known_last_dates={"https://x.com/claraluzroldan": "2026-09-10"},
                        known_post_texts={"100": "Cali avanza"}, credits=credits)
    items = c.fetch([])

    assert calls[0]["twitterHandles"] == ["claraluzroldan"] and calls[0]["start"] == "2026-09-11"
    assert calls[1]["inReplyTo"] == "claraluzroldan"
    ids = {i.external_id for i in items}
    assert ids == {"x:post:100", "x:reply:101"}  # la respuesta de la propia cuenta se descarta
    post = next(i for i in items if i.external_id == "x:post:100")
    reply = next(i for i in items if i.external_id == "x:reply:101")
    assert post.search_term == "Clara Luz Roldán" and post.raw["platform"] == "x" and post.published_at.year == 2026
    assert reply.raw["kind"] == "comment" and reply.raw["account_candidate"] == "Clara Luz Roldán"
    assert reply.url == "https://x.com/claraluzroldan/status/100"  # agrupa bajo el post original
    assert reply.raw["post_title"] == "Cali avanza" and reply.raw["reply_url"] == "https://x.com/juan/status/101"
    assert credits.used == 3


def test_no_calls_without_credits_or_accounts(monkeypatch):
    import src.connectors.x_apify as m
    monkeypatch.setattr(m.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debía llamar")))
    assert XApifyConnector(token="t", accounts=[{"platform": "x", "url": "https://x.com/a", "candidate": None}], credits=FakeCredits(0)).fetch([]) == []
    assert XApifyConnector(token="t", accounts=[]).fetch([]) == []
