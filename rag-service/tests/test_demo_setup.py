import io

from pypdf import PdfReader

from rag_service.demo_setup import corpus, make_pdf
from rag_service.evaluation import contains_fact, score


def test_synthetic_pdf_preserves_spanish_and_pages():
    documents = corpus()
    assert len(documents) == 3
    for item in documents:
        first = make_pdf(item["pages"])
        assert first == make_pdf(item["pages"])
        reader = PdfReader(io.BytesIO(first))
        assert len(reader.pages) == 3
        assert "DOCUMENTO FICTICIO" in reader.pages[0].extract_text()
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
