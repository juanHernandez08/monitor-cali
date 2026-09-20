from types import SimpleNamespace

from src.connectors.social_accounts import SocialAccountConnector, ACCOUNT_KEYS


class FakeAsyncClient:
    """Imita client.scrape.instagram / .facebook con datos de prueba."""

    def __init__(self, posts, comments):
        self._posts, self._comments = posts, comments
        self.calls = []

    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

    @property
    def search(self):
        async def ig_posts(url, num_of_posts): self.calls.append(("ig_posts", url, num_of_posts)); return SimpleNamespace(data=self._posts)
        return SimpleNamespace(instagram=SimpleNamespace(posts=ig_posts))

    @property
    def scrape(self):
        async def ig_comments(url): self.calls.append(("ig_comments", url)); return SimpleNamespace(data=self._comments)
        async def fb_posts(url, num_of_posts): self.calls.append(("fb_posts", url, num_of_posts)); return SimpleNamespace(data=self._posts)
        async def fb_comments(url, num_of_comments): self.calls.append(("fb_comments", url, num_of_comments)); return SimpleNamespace(data=self._comments)
        return SimpleNamespace(
            instagram=SimpleNamespace(comments=ig_comments),
            facebook=SimpleNamespace(posts_by_profile=fb_posts, comments=fb_comments),
        )


POSTS = [
    {"post_id": "p1", "url": "https://www.instagram.com/p/AAA/", "description": "Cali merece más. #BuenosCiudadanos",
     "user_posted": "soycarlosaarias", "date_posted": "2026-09-18T15:00:00.000Z", "num_comments": 12},
    {"post_id": "p2", "url": "https://www.instagram.com/p/BBB/", "description": "Gracias por acompañarnos",
     "user_posted": "soycarlosaarias", "date_posted": "2026-09-10T15:00:00.000Z", "num_comments": 0},
]
COMMENTS = [
    {"comment_id": "c1", "comment": "Este señor no ha hecho nada por Cali", "comment_user": "vecino1",
     "comment_date": "2026-09-18T16:00:00.000Z", "post_url": "https://www.instagram.com/p/AAA/"},
]


def test_instagram_account_yields_posts_and_comments_attributed_to_candidate(monkeypatch):
    fake = FakeAsyncClient(POSTS, COMMENTS)
    import src.connectors.social_accounts as m
    monkeypatch.setattr(m, "BrightDataClient", lambda token, auto_create_zones: fake)

    accounts = [{"platform": "instagram", "url": "https://www.instagram.com/soycarlosaarias/", "candidate": "Carlos Arias"}]
    items = SocialAccountConnector(api_token="t", accounts=accounts, max_posts=5, max_comments=25, comment_posts=3).fetch([])

    ids = {i.external_id for i in items}
    assert ids == {"ig:post:p1", "ig:post:p2", "ig:comment:c1"}
    post = next(i for i in items if i.external_id == "ig:post:p1")
    comment = next(i for i in items if i.external_id == "ig:comment:c1")
    assert post.search_term == "Carlos Arias" and post.raw["kind"] == "post" and post.author == "soycarlosaarias"
    assert comment.search_term == "Carlos Arias" and comment.raw["kind"] == "comment"
    assert comment.url == "https://www.instagram.com/p/AAA/" and comment.author == "vecino1"
    assert comment.published_at is not None and comment.published_at.year == 2026
    # solo se piden comentarios de posts que tienen comentarios, máximo `comment_posts`
    assert [c for c in fake.calls if c[0] == "ig_comments"] == [("ig_comments", "https://www.instagram.com/p/AAA/")]


def test_media_account_has_no_candidate_hint(monkeypatch):
    fake = FakeAsyncClient(POSTS, [])
    import src.connectors.social_accounts as m
    monkeypatch.setattr(m, "BrightDataClient", lambda token, auto_create_zones: fake)

    accounts = [{"platform": "facebook", "url": "https://www.facebook.com/noticali/", "candidate": None}]
    items = SocialAccountConnector(api_token="t", accounts=accounts).fetch([])

    assert all(i.search_term is None for i in items)
    assert fake.calls[0][0] == "fb_posts"


def test_account_keys_cover_alternative_field_names():
    # Bright Data no documenta los campos; el conector tolera varios nombres.
    assert ACCOUNT_KEYS["text"][0] == "description"
