import unicodedata
from urllib.parse import quote


def normalize_lemma(lemma: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", lemma).casefold().split())


def word_id(lemma: str) -> str:
    return "w_" + quote(lemma, safe="'")
