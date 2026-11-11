"""Unit tests for the benchmark metrics — no LLM calls."""

from datetime import UTC, datetime

from litprism.screen.benchmark import compute_metrics, load_records
from litprism.screen.models import ScreeningResult


def _res(aid: str, decision: str) -> ScreeningResult:
    return ScreeningResult(
        article_id=aid,
        decision=decision,
        confidence=0.9,
        reasoning="x",
        criteria_hits=[],
        stage="abstract",
        model_used="m",
        llm_provider="p",
        screened_at=datetime.now(UTC),
    )


def test_metrics_count_uncertain_as_kept():
    labels = {"a": True, "b": True, "c": False, "d": False, "e": False}
    results = [
        _res("a", "include"),  # tp
        _res("b", "exclude"),  # fn (missed)
        _res("c", "uncertain"),  # fp (kept for full text)
        _res("d", "exclude"),  # tn
        _res("e", "exclude"),  # tn
    ]
    m = compute_metrics(results, labels, errors=1)
    assert m.recall == 0.5
    assert m.precision == 0.5
    assert m.missed == 1
    assert m.work_saved == 3 / 5
    assert m.errors == 1
    assert "recall=50.0%" in m.summary()


def test_metrics_without_relevant_records_has_no_recall():
    m = compute_metrics([_res("a", "exclude")], {"a": False})
    assert m.recall is None and m.work_saved == 1.0


def test_load_records_parses_labels(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("id,title,abstract,label\n1,T1,A1,1\n2,T2,,0\n")
    recs = load_records(p)
    assert [r.label for r in recs] == [True, False]
    assert recs[1].abstract is None


def test_load_records_accepts_asreview_label_column(tmp_path):
    from litprism.screen.benchmark import load_records

    f = tmp_path / "d.csv"
    f.write_text("Title,Abstract,label_included\nA,abc,1\nB,,0\n", encoding="utf-8")
    recs = load_records(f)
    assert [r.label for r in recs] == [True, False]
    assert recs[1].abstract is None
