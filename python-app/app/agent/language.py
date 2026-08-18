import re

# Any Romanian diacritic, or any of a fixed list of Romanian keyword tokens
# (both diacritic and no-diacritic spellings) present anywhere in the
# lower-cased text triggers Romanian; otherwise English is assumed. Ported
# verbatim from JournalApplicationService.romanian() in the Java predecessor.
_ROMANIAN_PATTERN = re.compile(
    r"ă|â|î|ș|ț|azi|ieri|adauga|adaugă|pune|muta|mută|sterge|șterge|estimeaza|"
    r"estimează|cate|câte|calorii|mâncat|mancat|arată|arata|mic dejun|pranz|"
    r"prânz|cina|gustare|te rog"
)


def is_romanian(text: str | None) -> bool:
    if not text:
        return False
    return _ROMANIAN_PATTERN.search(text.lower()) is not None
