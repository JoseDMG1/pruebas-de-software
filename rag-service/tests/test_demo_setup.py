import io
import json
from importlib.resources import files

import pytest

from pypdf import PdfReader

from rag_service.demo_setup import corpus, make_pdf
from rag_service.evaluation import acceptance_met, contains_fact, score


def test_generated_pdf_preserves_spanish_and_pages():
    documents = corpus()
    assert len(documents) == 11
    for item in documents:
        first = make_pdf(item["pages"])
        assert first == make_pdf(item["pages"])
        reader = PdfReader(io.BytesIO(first))
        assert len(reader.pages) == 3
        assert "Universidad del Valle" in reader.pages[0].extract_text()
        for page, expected in zip(reader.pages, item["pages"], strict=True):
            assert " ".join(page.extract_text().split()) == expected


def test_evaluation_requires_facts_sources_and_abstention():
    positive = {"key": "reglamento", "facts": [["11", "once"]]}
    assert score(
        positive,
        {
            "answer": "Once",
            "insufficient_context": False,
            "sources": [{"key": "demo-s1-reglamento"}],
        },
    )
    assert not score(positive, {"answer": "11", "insufficient_context": False, "sources": []})
    assert score({"insufficient": True}, {"insufficient_context": True, "sources": []})
    assert not score({"insufficient": True}, {"insufficient_context": False, "sources": []})


def test_evaluation_does_not_count_numbers_inside_other_numbers_or_words():
    assert not contains_fact("110", "11")
    assert not contains_fact("entonces", "once")
    assert not contains_fact("todos", "dos")
    assert contains_fact("la nota es 11.", "11")


@pytest.mark.parametrize("passed,expected", [(29, False), (32, False), (33, True), (36, True)])
def test_final_acceptance_requires_ninety_percent(passed, expected):
    assert acceptance_met(passed, 36, 5, 5, 41, 41) is expected


def test_final_acceptance_rejects_incomplete_run_or_failed_abstention():
    assert not acceptance_met(36, 36, 4, 5, 41, 41)
    assert not acceptance_met(36, 36, 5, 5, 40, 41)
    assert not acceptance_met(0, 0, 0, 0, 0, 0)


def test_rectification_accepts_gender_variant_without_weakening_facts():
    cases = json.loads(files("rag_service").joinpath("demo/evaluation.json").read_text())
    case = next(item for item in cases if item["id"] == "P19")
    response = {
        "answer": "La rectificación es gratuita y tarda dos días hábiles.",
        "insufficient_context": False,
        "sources": [{"key": "demo-s1-tramites"}],
    }
    assert score(case, response)
    assert not score(case, response | {"answer": "La rectificación es gratuita."})
