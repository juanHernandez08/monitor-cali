from types import SimpleNamespace

from src.connectors.social_accounts import SocialAccountConnector, ACCOUNT_KEYS


class FakeAsyncClient:
    """Imita client.search.instagram / client.scrape.* con datos de prueba y registra las llamadas."""

    def __init__(self, posts, comments):
        self._posts, self._comments = posts, comments
        self.calls = []

    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

    @property
    def search(self):
        async def ig_posts(**kw): self.calls.append(("ig_posts", kw)); return SimpleNamespace(data=self._posts)
        return SimpleNamespace(instagram=SimpleNamespace(posts=ig_posts))

    @property
    def scrape(self):
        async def ig_comments(url): self.calls.append(("ig_comments", url)); return SimpleNamespace(data=self._comments)
        async def fb_posts(**kw): self.calls.append(("fb_posts", kw)); return SimpleNamespace(data=self._posts)
        async def fb_comments(url, num_of_comments): self.calls.append(("fb_comments", url)); return SimpleNamespace(data=self._comments)
        return SimpleNamespace(
            instagram=SimpleNamespace(comments=ig_comments),
            facebook=SimpleNamespace(posts_by_profile=fb_posts, comments=fb_comments),
        )


class FakeCredits:
    def __init__(self, remaining): self._r = remaining; self.used = 0
    def remaining(self): return self._r
    def consume(self, n): self._r -= n; self.used += n


POSTS = [
    {"post_id": "p1", "url": "https://www.instagram.com/p/AAA/", "description": "Cali merece más. #BuenosCiudadanos",
     "user_posted": "soycarlosaarias", "date_posted": "2026-09-18T15:00:00.000Z", "num_comments": "12"},
    {"post_id": "p2", "url": "https://www.instagram.com/p/BBB/", "description": "Gracias por acompañarnos",
     "user_posted": "soycarlosaarias", "date_posted": "2026-09-10T15:00:00.000Z", "num_comments": "0"},
]
COMMENTS = [
    {"comment_id": "c1", "comment": "Este señor no ha hecho nada por Cali", "comment_user": "vecino1",
     "comment_date": "2026-09-18T16:00:00.000Z", "post_url": "https://www.instagram.com/p/AAA/"},
]
ACCOUNT = {"platform": "instagram", "url": "https://www.instagram.com/soycarlosaarias/", "candidate": "Carlos Arias"}


def _patch(monkeypatch, fake):
    import src.connectors.social_accounts as m
    monkeypatch.setattr(m, "BrightDataClient", lambda token, auto_create_zones: fake)


def test_posts_by_date_window_excluding_known_and_comments_for_new_posts(monkeypatch):
    fake = FakeAsyncClient(POSTS, COMMENTS)
    _patch(monkeypatch, fake)
    credits = FakeCredits(1000)
    c = SocialAccountConnector(api_token="t", accounts=[ACCOUNT], window_days=60, max_posts=40,
                               known_post_ids={ACCOUNT["url"]: ["old1", "old2"]}, credits=credits)
    items = c.fetch([])

    kw = fake.calls[0][1]
    assert kw["num_of_posts"] == 40 and kw["posts_to_not_include"] == ["old1", "old2"]
    assert len(kw["start_date"]) == 10 and kw["start_date"][2] == "-" and kw["start_date"][5] == "-"  # Instagram: MM-DD-YYYY
    assert {i.external_id for i in items} == {"ig:post:p1", "ig:post:p2", "ig:comment:c1"}
    comment = next(i for i in items if i.external_id == "ig:comment:c1")
    assert comment.search_term == "Carlos Arias" and comment.raw["account_candidate"] == "Carlos Arias"
    assert comment.raw["post_title"].startswith("Cali merece")
    # solo el post con comentarios se consulta, y queda registrado como intentado
    assert [x for x in fake.calls if x[0] == "ig_comments"] == [("ig_comments", "https://www.instagram.com/p/AAA/")]
    assert c.comments_attempted == {"https://www.instagram.com/p/AAA/"}
    assert credits.used == 3  # 2 posts + 1 comentario


def test_pending_comment_posts_from_db_are_fetched_and_credit_guard_stops(monkeypatch):
    fake = FakeAsyncClient([], COMMENTS)
    _patch(monkeypatch, fake)
    pending = [{"url": "https://www.instagram.com/p/OLD/", "platform": "instagram", "candidate": "Carlos Arias",
                "account": ACCOUNT["url"], "title": "Trincheras en Cali", "num_comments": 300}]
    c = SocialAccountConnector(api_token="t", accounts=[ACCOUNT], pending_comment_posts=pending, credits=FakeCredits(5))
    items = c.fetch([])
    assert [x for x in fake.calls if x[0] == "ig_comments"] == [("ig_comments", "https://www.instagram.com/p/OLD/")]
    assert items[0].raw["post_title"] == "Trincheras en Cali"

    # sin créditos: no se llama a nada
    fake2 = FakeAsyncClient(POSTS, COMMENTS)
    _patch(monkeypatch, fake2)
    assert SocialAccountConnector(api_token="t", accounts=[ACCOUNT], credits=FakeCredits(0)).fetch([]) == []
    assert fake2.calls == []


def test_media_account_has_no_candidate_hint(monkeypatch):
    fake = FakeAsyncClient(POSTS, [])
    _patch(monkeypatch, fake)
    items = SocialAccountConnector(api_token="t", accounts=[{"platform": "facebook", "url": "https://www.facebook.com/noticali/", "candidate": None}]).fetch([])
    assert all(i.search_term is None for i in items)
    assert fake.calls[0][0] == "fb_posts"


def test_account_keys_cover_alternative_field_names():
    assert ACCOUNT_KEYS["text"][0] == "description"


def test_x_accounts_fetched_in_one_batch_via_rest(monkeypatch):
    calls = []

    class R:
        def __init__(self, payload, status=200): self._p, self.status_code = payload, status
        def raise_for_status(self): pass
        def json(self): return self._p

    def fake_post(url, headers, params, json, timeout):
        calls.append(("trigger", params, json)); return R({"snapshot_id": "sd_1"})

    def fake_get(url, headers, params=None, timeout=None):
        if "/progress/" in url:
            return R({"status": "ready", "records": 1})
        return R([{"id": "111", "url": "https://x.com/claraluzroldan/status/111", "description": "Cali avanza",
                   "user_posted": "ClaraLuzRoldan", "date_posted": "2026-09-19T20:11:49.000Z", "likes": "51",
                   "views": "3624", "replies": "2", "reposts": "9", "photos": ["https://pbs/img.jpg"]}])

    import src.connectors.social_accounts as m
    monkeypatch.setattr(m.requests, "post", fake_post)
    monkeypatch.setattr(m.requests, "get", fake_get)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    _patch(monkeypatch, FakeAsyncClient([], []))

    accounts = [{"platform": "x", "url": "https://x.com/claraluzroldan", "candidate": "Clara Luz Roldán"},
                {"platform": "x", "url": "https://x.com/otro", "candidate": "Roberto Ortiz"}]
    credits = FakeCredits(100)
    c = SocialAccountConnector(api_token="t", accounts=accounts, credits=credits,
                               known_last_dates={"https://x.com/claraluzroldan": "2026-09-10"})
    items = c.fetch([])

    trigger = calls[0]
    assert trigger[1]["dataset_id"] == "gd_lwxkxvnf1cynvib9co" and trigger[1]["discover_by"] == "profile_url"
    assert [i["url"] for i in trigger[2]] == ["https://x.com/claraluzroldan", "https://x.com/otro"]
    assert trigger[2][0]["start_date"] == "2026-09-11"  # solo posts nuevos desde la última fecha conocida
    assert items[0].external_id == "x:post:111" and items[0].search_term == "Clara Luz Roldán"
    assert items[0].raw["platform"] == "x" and items[0].raw["record"]["views"] == "3624"
    assert credits.used == 1
