from pydantic import BaseModel


class PICOInput(BaseModel):
    population: str | None = None
    intervention: str | None = None
    comparator: str | None = None
    outcome: str | None = None
    free_text: str | None = None


def build_pubmed_query(pico: PICOInput) -> str:
    """
    If free_text is set, return it unchanged.
    Otherwise, wrap each non-empty PICO component in quotes and join with AND.
    Comma-separated values within a component are joined with OR.
    """
    if pico.free_text:
        return pico.free_text.strip()

    groups = []
    for component in [pico.population, pico.intervention, pico.comparator, pico.outcome]:
        if not component:
            continue
        terms = [t.strip() for t in component.split(",") if t.strip()]
        if len(terms) == 1:
            groups.append(f'"{terms[0]}"[tiab]')
        else:
            inner = " OR ".join(f'"{t}"[tiab]' for t in terms)
            groups.append(f"({inner})")
    return " AND ".join(groups)
