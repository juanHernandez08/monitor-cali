import datetime as dt

from src import stats
from src.models import Candidate, Mention, SentimentLabel, SentimentScore, Source, SourceType
from src.queries import (_social_metrics, candidate_reach_comparison, social_insights, social_strong_posts,
                         weekly_conversation)


def test_wilson_interval_is_wide_with_few_observations_and_narrow_with_many():
    lo3, hi3 = stats.wilson(3, 3)
    lo300, hi300 = stats.wilson(300, 300)
    assert hi3 == 100.0 and lo3 < 45  # 3 de 3 no prueba un 100%
    assert lo300 > 98
    assert stats.wilson(0, 0) is None


def test_count_change_needs_enough_volume_to_call_a_trend():
    assert stats.count_change_test(3, 1)["small_sample"] is True  # "+200%" con 4 menciones: ruido
    big = stats.count_change_test(160, 100)
    assert big["significant"] is True and big["p_value"] < 0.01
    assert stats.count_change_test(52, 48)["significant"] is False


def test_binomial_p_value_matches_known_values():
    assert abs(stats.binom_two_sided_p(5, 10) - 1.0) < 1e-9
    assert abs(stats.binom_two_sided_p(9, 10) - 0.021484375) < 1e-9


def test_robust_z_ignores_a_single_viral_outlier_in_the_baseline():
    history = [100, 110, 90, 105, 95, 5000]
    assert stats.robust_z(400, history) > 3.5


def _mention(raw, text="x"):
    m = Mention(candidate_id=1, source_id=1, external_id="e", text=text, raw=raw)
    return m


def test_social_metrics_reads_bright_data_instagram_likes():
    """Bug real: los reels de Carlos traídos por Bright Data (campo `likes`) contaban 0 likes."""
    m = _mention({"platform": "instagram", "kind": "post", "num_comments": 33,
                  "record": {"likes": 231, "content_type": "Reel"}})
    got = _social_metrics(m)
    assert got["likes"] == 231 and got["comments"] == 33 and got["format"] == "reel"


def test_social_metrics_marks_hidden_likes_instead_of_counting_minus_one():
    m = _mention({"platform": "instagram", "kind": "post", "num_comments": 12,
                  "record": {"likesCount": -1, "productType": "clips"}})
    got = _social_metrics(m)
    assert got["likes_hidden"] is True and got["likes"] == 0


def test_social_metrics_reads_x_likes_and_facebook_shares():
    x = _social_metrics(_mention({"platform": "x", "kind": "post", "num_comments": 0,
                                  "record": {"likeCount": 8, "viewCount": 696, "retweetCount": 1}}))
    assert x["likes"] == 8 and x["views"] == 696 and x["shares"] == 1
    fb = _social_metrics(_mention({"platform": "facebook", "kind": "post", "num_comments": 3,
                                   "record": {"likes": 40, "shares": 7, "isVideo": True}}))
    assert fb["shares"] == 7 and fb["format"] == "video"


def _seed_posts(db_session, spec):
    src = Source(type=SourceType.SOCIAL, name="Redes")
    db_session.add(src)
    cands = {}
    for name in {s[0] for s in spec}:
        c = Candidate(name=name, aliases=[])
        db_session.add(c)
        cands[name] = c
    db_session.commit()
    now = dt.datetime.utcnow()
    for i, (name, likes, days_ago, fmt) in enumerate(spec):
        db_session.add(Mention(candidate_id=cands[name].id, source_id=src.id, external_id=f"p{i}", text="post",
                               url=f"https://instagram.com/p/{i}", published_at=now - dt.timedelta(days=days_ago),
                               raw={"kind": "post", "platform": "instagram", "num_comments": 0,
                                    "record": {"likesCount": likes, "productType": fmt}}))
    db_session.commit()


def test_reach_comparison_excludes_hidden_likes_and_reports_median(db_session):
    _seed_posts(db_session, [("Carlos Arias", 100, 20, "clips"), ("Carlos Arias", 120, 15, "clips"),
                             ("Carlos Arias", 5000, 10, "clips"), ("Carlos Arias", -1, 5, "clips")])
    row = candidate_reach_comparison(db_session, days=30)[0]
    assert row["posts"] == 3 and row["hidden_likes_posts"] == 1
    assert row["median_engagement"] == 120 and row["avg_engagement"] > 1700


def test_strong_posts_baseline_is_the_recent_median_not_an_inflated_mean(db_session):
    """Con promedio, el reel viral de hace 20 días inflaba la base y escondía el pico de hoy."""
    _seed_posts(db_session, [("Mabel Lara", 100, 30, "clips"), ("Mabel Lara", 110, 25, "clips"),
                             ("Mabel Lara", 9000, 20, "clips"), ("Mabel Lara", 105, 15, "clips"),
                             ("Mabel Lara", 600, 1, "clips")])
    strong = social_strong_posts(db_session, days=7, multiplier=3.0)
    assert len(strong) == 1 and strong[0]["baseline"] == 108


def test_social_insights_uses_engagement_relative_to_each_account(db_session):
    _seed_posts(db_session, [("Carlos Arias", 100, 10, "clips"), ("Carlos Arias", 300, 8, "clips"),
                             ("Carlos Arias", 50, 6, "carousel_container"),
                             ("Mabel Lara", 1000, 9, "clips"), ("Mabel Lara", 3000, 7, "clips"),
                             ("Mabel Lara", 500, 5, "feed")])
    ins = social_insights(db_session, days=30)
    fmt = {r["key"]: r for r in ins["all"]["format"]}
    assert fmt["reel"]["median_rel"] > fmt["carrusel"]["median_rel"]
    assert ins["posts_candidate"] == 3 and "weekly" in ins


def test_weekly_conversation_share_and_net_sentiment(db_session):
    src = Source(type=SourceType.GOOGLE_NEWS, name="GN")
    carlos, rival = Candidate(name="Carlos Arias", aliases=[]), Candidate(name="Mabel Lara", aliases=[])
    db_session.add_all([src, carlos, rival])
    db_session.commit()
    now = dt.datetime.utcnow()
    for i, (cand, label) in enumerate([(carlos, "POSITIVE"), (carlos, "NEGATIVE"), (carlos, "POSITIVE"), (rival, None)]):
        m = Mention(candidate_id=cand.id, source_id=src.id, external_id=f"n{i}", text="t", published_at=now)
        db_session.add(m)
        db_session.commit()
        if label:
            db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel[label], score=0.5, model="t"))
    db_session.commit()
    wk = weekly_conversation(db_session, days=14)["weeks"][-1]
    assert wk["mentions"] == 3 and wk["all_mentions"] == 4 and wk["share_pct"] == 75.0
    assert wk["net_sentiment"] == 33 and wk["net_low"] < 0 < wk["net_high"]
