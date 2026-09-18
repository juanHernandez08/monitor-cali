from src.models import Candidate, Mention, SentimentScore
from src.matching import all_search_terms_flat, find_matching_candidate
from src.sentiment import SentimentEngine
from src.connectors.base import Connector


def run_pipeline(session, source, connector: Connector, sentiment_engine: SentimentEngine) -> int:
    """Corre cualquier conector contra una fuente ya registrada y guarda menciones nuevas."""
    candidates = session.query(Candidate).filter_by(active=True).all()
    search_terms = all_search_terms_flat(candidates)

    new_mentions = 0
    for item in connector.fetch(search_terms):
        exists = session.query(Mention).filter_by(
            source_id=source.id, external_id=item.external_id,
        ).first()
        if exists:
            continue

        matched_candidate = find_matching_candidate(item.text, candidates)
        if matched_candidate is None:
            continue

        mention = Mention(
            candidate_id=matched_candidate.id,
            source_id=source.id,
            external_id=item.external_id,
            url=item.url,
            author=item.author,
            text=item.text,
            published_at=item.published_at,
            raw=item.raw,
        )
        session.add(mention)
        session.flush()

        result = sentiment_engine.score(item.text)
        session.add(SentimentScore(
            mention_id=mention.id, label=result.label, score=result.score,
            topic=result.topic, model=result.model,
        ))
        new_mentions += 1

    session.commit()
    return new_mentions
