from src.connectors.social_apify import SocialApifyConnector


class FakeCredits:
    def __init__(self, remaining): self._r = remaining; self.used = 0
    def remaining(self): return self._r
    def consume(self, n): self._r -= n; self.used += n


IG_POST_NEW = {"id": "p1", "url": "https://www.instagram.com/p/AAA/", "caption": "Cali merece más #BuenosCiudadanos",
               "ownerUsername": "soycarlosaarias", "timestamp": "2026-09-18T15:00:00.000Z", "commentsCount": 12}
IG_POST_KNOWN = {"id": "p0", "url": "https://www.instagram.com/p/OLD/", "caption": "viejo",
                 "ownerUsername": "soycarlosaarias", "timestamp": "2026-09-01T15:00:00.000Z", "commentsCount": 3}
IG_COMMENT = {"id": "c1", "text": "Este señor no ha hecho nada por Cali", "ownerUsername": "vecino1",
              "timestamp": "2026-09-18T16:00:00.000Z", "postUrl": "https://www.instagram.com/p/AAA/"}

FB_POST_NEW = {"postId": 555, "url": "https://www.facebook.com/ClaraLuzRoldanG/posts/555", "text": "Gracias Cali",
               "time": "2026-09-19T02:00:00.000Z", "comments": 4, "user": {"name": "Clara Luz Roldan"}}
FB_COMMENT = {"commentId": 900, "text": "Vamos Clara", "profileName": "juan p", "date": "2026-09-19T03:00:00.000Z",
              "likesCount": 2}

IG_ACCOUNT = {"platform": "instagram", "url": "https://www.instagram.com/soycarlosaarias/", "candidate": "Carlos Arias"}
FB_ACCOUNT = {"platform": "facebook", "url": "https://www.facebook.com/ClaraLuzRoldanG/", "candidate": "Clara Luz Roldán"}


def _patch(monkeypatch, by_actor: dict):
    calls = []

    class R:
        def __init__(self, p): self._p = p
        def raise_for_status(self): pass
        def json(self): return self._p

    def fake_post(url, params, json, timeout):
        calls.append((url, json))
        actor = url.split("/acts/")[1].split("/run-sync")[0]
        return R(by_actor[actor])

    import src.connectors.social_apify as m
    monkeypatch.setattr(m.requests, "post", fake_post)
    return calls


def test_instagram_posts_excludes_known_and_fetches_comments_for_commented_posts(monkeypatch):
    calls = _patch(monkeypatch, {
        "apify~instagram-scraper": [IG_POST_NEW, IG_POST_KNOWN],
        "apify~instagram-comment-scraper": [IG_COMMENT],
    })
    credits = FakeCredits(1000)
    c = SocialApifyConnector(token="t", accounts=[IG_ACCOUNT], known_post_ids={IG_ACCOUNT["url"]: ["p0"]},
                             credits=credits, comment_posts=4)
    items = c.fetch([])

    posts_call = next(j for u, j in calls if "instagram-scraper" in u)
    assert posts_call["directUrls"] == [IG_ACCOUNT["url"]] and posts_call["resultsLimit"] == 40

    ids = {i.external_id for i in items}
    assert ids == {"ig:post:p1", "ig:comment:c1"}  # p0 ya conocido, se descarta
    post = next(i for i in items if i.external_id == "ig:post:p1")
    assert post.text == "Cali merece más #BuenosCiudadanos" and post.search_term == "Carlos Arias"
    assert post.raw["platform"] == "instagram" and post.raw["num_comments"] == 12
    comment = next(i for i in items if i.external_id == "ig:comment:c1")
    assert comment.raw["kind"] == "comment" and comment.raw["account_candidate"] == "Carlos Arias"
    assert comment.url == "https://www.instagram.com/p/AAA/"
    assert credits.used == 2 + 1  # 2 posts devueltos + 1 comentario, aunque uno se descarte después
    assert c.comments_attempted == {"https://www.instagram.com/p/AAA/"}


def test_facebook_posts_and_comments(monkeypatch):
    _patch(monkeypatch, {
        "apify~facebook-posts-scraper": [FB_POST_NEW],
        "apify~facebook-comments-scraper": [FB_COMMENT],
    })
    c = SocialApifyConnector(token="t", accounts=[FB_ACCOUNT], credits=FakeCredits(1000))
    items = c.fetch([])
    ids = {i.external_id for i in items}
    assert ids == {"fb:post:555", "fb:comment:900"}
    post = next(i for i in items if i.external_id == "fb:post:555")
    assert post.text == "Gracias Cali" and post.author == "Clara Luz Roldan" and post.search_term == "Clara Luz Roldán"
    comment = next(i for i in items if i.external_id == "fb:comment:900")
    assert comment.text == "Vamos Clara" and comment.author == "juan p"


def test_uses_last_known_date_to_narrow_the_window(monkeypatch):
    calls = _patch(monkeypatch, {"apify~instagram-scraper": [], "apify~instagram-comment-scraper": []})
    c = SocialApifyConnector(token="t", accounts=[IG_ACCOUNT], known_last_dates={IG_ACCOUNT["url"]: "2026-09-10"})
    c.fetch([])
    posts_call = next(j for u, j in calls if "instagram-scraper" in u)
    assert posts_call["onlyPostsNewerThan"] == "2026-09-11"


def test_no_calls_without_credits_or_accounts(monkeypatch):
    import src.connectors.social_apify as m
    monkeypatch.setattr(m.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debía llamar")))
    assert SocialApifyConnector(token="t", accounts=[IG_ACCOUNT], credits=FakeCredits(0)).fetch([]) == []
    assert SocialApifyConnector(token="t", accounts=[]).fetch([]) == []


def test_ignores_x_accounts(monkeypatch):
    import src.connectors.social_apify as m
    monkeypatch.setattr(m.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debía llamar")))
    x_account = {"platform": "x", "url": "https://x.com/a", "candidate": None}
    assert SocialApifyConnector(token="t", accounts=[x_account]).fetch([]) == []


def test_investigate_profile_fetches_any_instagram_url_live_with_metrics(monkeypatch):
    from src.connectors.social_apify import investigate_profile
    calls = _patch(monkeypatch, {"apify~instagram-scraper": [IG_POST_NEW, IG_POST_KNOWN]})
    posts = investigate_profile(token="t", url="https://www.instagram.com/unrival/", platform="instagram", max_posts=20)

    posts_call = next(j for u, j in calls if "instagram-scraper" in u)
    assert posts_call["directUrls"] == ["https://www.instagram.com/unrival/"] and posts_call["resultsLimit"] == 20
    assert "onlyPostsNewerThan" not in posts_call  # investigar trae lo más reciente sin ventana fija

    assert len(posts) == 2  # a diferencia del pipeline normal, no filtra "ya conocidos"
    newest = posts[0]
    assert newest["id"] == "p1" and newest["text"] == "Cali merece más #BuenosCiudadanos"
    assert newest["likes"] == 0 and newest["comments"] == 12  # IG_POST_NEW no trae likesCount
    assert newest["engagement"] == 12


def test_investigate_profile_facebook(monkeypatch):
    from src.connectors.social_apify import investigate_profile
    _patch(monkeypatch, {"apify~facebook-posts-scraper": [FB_POST_NEW]})
    posts = investigate_profile(token="t", url="https://www.facebook.com/unrival/", platform="facebook")
    assert len(posts) == 1
    assert posts[0]["text"] == "Gracias Cali" and posts[0]["author"] == "Clara Luz Roldan"
    assert posts[0]["comments"] == 4
