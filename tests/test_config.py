"""Guarda de cordura para listas de config.py que se editan a mano y crecen con el tiempo:
un typo en un nombre con tilde (muy fácil al copiar 25+ concejales) deja una cuenta social
huérfana -- se ingiere pero nunca se le atribuyen menciones a nadie."""
from src.config import SOCIAL_ACCOUNTS, CANDIDATES, COUNCILORS


def test_every_social_account_candidate_matches_a_known_name():
    known = {c["name"] for c in CANDIDATES} | {c["name"] for c in COUNCILORS}
    for account in SOCIAL_ACCOUNTS:
        if account["candidate"] is not None:
            assert account["candidate"] in known, (
                f"{account['candidate']!r} en SOCIAL_ACCOUNTS no coincide con ningún nombre "
                f"de CANDIDATES ni COUNCILORS (revisar tildes/typos)"
            )


def test_no_duplicate_social_account_urls():
    urls = [a["url"] for a in SOCIAL_ACCOUNTS]
    assert len(urls) == len(set(urls))
