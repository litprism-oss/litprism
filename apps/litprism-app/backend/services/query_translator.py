import re


class QueryTranslator:
    """Translate a canonical PubMed query string into source-specific syntax."""

    @staticmethod
    def to_pubmed(query: str) -> str:
        return query

    @staticmethod
    def to_europepmc(query: str) -> str:
        q = query
        q = re.sub(r'"([^"]+)"\[MeSH(?:[^\]]*)\]', r'MESH:"\1"', q)
        q = re.sub(r"(\S+)\[tiab\]", r"\1", q)
        q = re.sub(r"(\S+)\[ti\]", r"TITLE:\1", q)
        q = re.sub(r"(\S+)\[ab\]", r"ABSTRACT:\1", q)
        q = re.sub(r"(\S+)\[au\]", r'AUTH:"\1"', q)
        return q.strip()

    @staticmethod
    def to_semantic_scholar(query: str) -> str:
        q = re.sub(r'"([^"]+)"\[MeSH(?:[^\]]*)\]', r'"\1"', query)
        q = re.sub(r"\[\w+\]", "", q)
        q = re.sub(r"\s+", " ", q).strip()
        return q
