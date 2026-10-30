import uuid
import pytest

from retrieval.context import ContextBuilder
from retrieval.models import SearchResult
from retrieval.reranker import BGEReranker


@pytest.fixture(scope="module")
def reranker():
    return BGEReranker(model_name="BAAI/bge-reranker-base")


def test_bge_reranker_scoring_and_ranking(reranker):
    """Verify BGE cross-encoder reranks passages by relevance with normalized scores."""
    query = "What is the policy on international travel flight class?"

    c1 = SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name="Corporate Travel Policy",
        canonical_id="CORP-TRV-01",
        version="2.0",
        section_context="Air Travel > Flight Class",
        page_number=4,
        content="Economy class is required for all flights under 6 hours. Business class is permitted for international flights exceeding 6 hours with VP approval.",
        score=0.45,
        rank=2,
        source_method="hybrid",
    )

    c2 = SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name="Office Supplies Policy",
        canonical_id="CORP-OPS-03",
        version="1.0",
        section_context="Supplies > Ordering",
        page_number=1,
        content="Pens, paper, notebooks, and dry erase markers can be requested via the office portal.",
        score=0.85,
        rank=1,
        source_method="hybrid",
    )

    # Reranker should identify c1 as much more relevant to the query than c2
    reranked = reranker.rerank(query=query, candidates=[c2, c1], top_k=2)

    assert len(reranked) == 2
    assert reranked[0].chunk_id == c1.chunk_id
    assert reranked[0].rank == 1
    assert reranked[0].source_method == "reranked"
    assert 0.0 <= reranked[0].score <= 1.0
    assert reranked[0].score > reranked[1].score


def test_context_builder_formatting_and_citations():
    """Verify ContextBuilder builds LLM context blocks with strict citation metadata."""
    doc_id = uuid.uuid4()
    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()

    results = [
        SearchResult(
            chunk_id=c1_id,
            document_id=doc_id,
            document_name="Travel Policy 2024",
            canonical_id="POL-TRV-24",
            version="2.1",
            section_context="4.0 Meals > 4.2 Per Diem",
            page_number=7,
            content="Breakfast per diem is $20, lunch is $25, and dinner is $40.",
            score=0.95,
            rank=1,
        ),
        SearchResult(
            chunk_id=c2_id,
            document_id=doc_id,
            document_name="Travel Policy 2024",
            canonical_id="POL-TRV-24",
            version="2.1",
            section_context="5.0 Lodging > 5.1 Hotel Rates",
            page_number=9,
            content="Hotel nightly rate caps are $250 for tier 1 cities.",
            score=0.88,
            rank=2,
        ),
    ]

    builder = ContextBuilder(max_tokens=1000)
    ctx = builder.build_context(results)

    assert ctx.chunk_count == 2
    assert len(ctx.citations) == 2
    assert "Travel Policy 2024" in ctx.context_text
    assert "POL-TRV-24" in ctx.context_text
    assert "4.0 Meals > 4.2 Per Diem" in ctx.context_text
    assert "Page: 7" in ctx.context_text
    assert str(c1_id) in ctx.context_text

    # Citation metadata verification
    cit1 = ctx.citations[0]
    assert cit1.chunk_id == c1_id
    assert cit1.document_id == doc_id
    assert cit1.document_name == "Travel Policy 2024"
    assert cit1.version == "2.1"
    assert cit1.page_number == 7
    assert "Breakfast per diem" in cit1.text_excerpt


def test_context_builder_budget_enforcement():
    """Verify ContextBuilder stops gracefully when character budget is exceeded."""
    results = [
        SearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            document_name="Doc 1",
            version="1.0",
            section_context="Sec 1",
            page_number=1,
            content="Long chunk content " * 30,
            score=0.9,
            rank=1,
        ),
        SearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            document_name="Doc 2",
            version="1.0",
            section_context="Sec 2",
            page_number=2,
            content="Second chunk content " * 30,
            score=0.8,
            rank=2,
        ),
    ]

    # Constrain to small character budget that only fits the first chunk
    builder = ContextBuilder(max_characters=400)
    ctx = builder.build_context(results)

    assert ctx.chunk_count == 1
    assert len(ctx.citations) == 1
    assert "Doc 1" in ctx.context_text
    assert "Doc 2" not in ctx.context_text
