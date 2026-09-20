from src.connectors.youtube import YouTubeConnector


def test_youtube_connector_returns_videos_and_comments(monkeypatch):
    queries = []

    def fake_get(url, params, timeout):
        if url.endswith("/search"):
            queries.append(params["q"])

        class R:
            def __init__(self, payload): self._p = payload
            def raise_for_status(self): pass
            def json(self): return self._p
        if url.endswith("/search"):
            return R({"items": [{"id": {"videoId": "v1"}, "snippet": {
                "title": "Entrevista a Irene Vélez", "description": "Cali 2027",
                "channelTitle": "Noticali", "publishedAt": "2026-09-18T10:00:00Z"}}]})
        return R({"items": [{"id": "c1", "snippet": {"topLevelComment": {"snippet": {
            "textDisplay": "No confío en ella", "authorDisplayName": "juan",
            "publishedAt": "2026-09-18T11:00:00Z"}}}}]})

    import src.connectors.youtube as m
    monkeypatch.setattr(m.requests, "get", fake_get)

    items = YouTubeConnector(api_key="k", max_videos=5, max_comments=20, pause_seconds=0).fetch(["Irene Vélez"])

    assert queries == ['"Irene Vélez" Cali']
    ids = {i.external_id for i in items}
    assert ids == {"yt:video:v1", "yt:comment:c1"}
    video = next(i for i in items if i.external_id == "yt:video:v1")
    comment = next(i for i in items if i.external_id == "yt:comment:c1")
    assert video.url == "https://www.youtube.com/watch?v=v1"
    assert comment.url == "https://www.youtube.com/watch?v=v1&lc=c1"
    assert comment.search_term == "Irene Vélez"
    assert comment.author == "juan"


def test_youtube_video_not_about_candidate_gets_no_hint(monkeypatch):
    def fake_get(url, params, timeout):
        class R:
            def __init__(self, payload): self._p = payload
            def raise_for_status(self): pass
            def json(self): return self._p
        if url.endswith("/search"):
            return R({"items": [{"id": {"videoId": "v9"}, "snippet": {
                "title": "Salomón sobrevivió al terremoto", "description": "Historia de un rescate",
                "channelTitle": "Noticias", "publishedAt": "2026-09-18T10:00:00Z"}}]})
        return R({"items": [{"id": "c9", "snippet": {"topLevelComment": {"snippet": {
            "textDisplay": "qué milagro", "authorDisplayName": "ana", "publishedAt": "2026-09-18T11:00:00Z"}}}}]})

    import src.connectors.youtube as m
    monkeypatch.setattr(m.requests, "get", fake_get)
    items = YouTubeConnector(api_key="k", pause_seconds=0).fetch(["Carlos Arias"])
    assert all(i.search_term is None for i in items)  # ni el video ni el comentario se atribuyen
