class QueryTranslator:
    """Translate a canonical query string into source-specific syntax."""

    @staticmethod
    def to_pubmed(query: str) -> str:
        raise NotImplementedError

    @staticmethod
    def to_europepmc(query: str) -> str:
        raise NotImplementedError

    @staticmethod
    def to_semanticscholar(query: str) -> str:
        raise NotImplementedError
