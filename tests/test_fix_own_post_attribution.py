from src.models import Candidate, Source, SourceType, Mention


def test_reassigns_post_to_its_account_owner(db_session, monkeypatch):
    from src import config
    from scripts.fix_own_post_attribution import run
    monkeypatch.setattr(config, "SOCIAL_ACCOUNTS", [
        {"platform": "instagram", "url": "https://www.instagram.com/soycarlosaarias/", "candidate": "Carlos Arias"}])
    carlos = Candidate(name="Carlos Arias", aliases=[])
    mondragon = Candidate(name="Alfredo Mondragón", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add_all([carlos, mondragon, ig])
    db_session.commit()
    m = Mention(candidate_id=mondragon.id, source_id=ig.id, external_id="ig:post:1", text="No Alfredo Mondragón...",
               url="https://www.instagram.com/p/AAA/", raw={"kind": "post", "account": "https://www.instagram.com/soycarlosaarias/"})
    db_session.add(m)
    db_session.commit()

    assert run(db_session) == 1
    assert db_session.query(Mention).one().candidate_id == carlos.id


def test_leaves_correctly_attributed_posts_alone(db_session, monkeypatch):
    from src import config
    from scripts.fix_own_post_attribution import run
    monkeypatch.setattr(config, "SOCIAL_ACCOUNTS", [
        {"platform": "instagram", "url": "https://www.instagram.com/soycarlosaarias/", "candidate": "Carlos Arias"}])
    carlos = Candidate(name="Carlos Arias", aliases=[])
    ig = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add_all([carlos, ig])
    db_session.commit()
    m = Mention(candidate_id=carlos.id, source_id=ig.id, external_id="ig:post:1", text="Gracias Cali",
               url="https://www.instagram.com/p/AAA/", raw={"kind": "post", "account": "https://www.instagram.com/soycarlosaarias/"})
    db_session.add(m)
    db_session.commit()

    assert run(db_session) == 0
    assert db_session.query(Mention).one().candidate_id == carlos.id
