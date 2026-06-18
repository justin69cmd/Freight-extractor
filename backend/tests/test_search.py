"""Phase 8 — NLQ routing, embeddings, chunk-text builders (pure, no DB)."""
from types import SimpleNamespace

from app.core.enums import PricingPattern, RateBasis, SearchIntent, TransportMode
from app.search.embedder import _local_embed, cosine, embed
from app.search.indexer import build_clause_text, build_metadata_text, build_rate_text
from app.search.nlq_parser import parse_query


# --- intent routing -------------------------------------------------------- #
def test_freight_search_intent_and_lane():
    pq = parse_query("What is the freight rate from Meerut to Bangalore?")
    assert pq.intent is SearchIntent.FREIGHT_SEARCH
    assert pq.origin == "Meerut" and pq.destination == "Bangalore"


def test_clause_search_intent():
    assert parse_query("what is the penalty clause for late delivery").intent is SearchIntent.CLAUSE_SEARCH
    assert parse_query("show the fuel surcharge terms").intent is SearchIntent.CLAUSE_SEARCH


def test_comparison_intent():
    assert parse_query("compare rates between vendors to Kolkata").intent is SearchIntent.VENDOR_COMPARISON


def test_analytics_intent():
    assert parse_query("which transporter is cheapest to Kolkata").intent is SearchIntent.AGREEMENT_ANALYTICS
    assert parse_query("show all vendors serving Bangalore").intent is SearchIntent.AGREEMENT_ANALYTICS
    assert parse_query("which agreements are expiring").intent is SearchIntent.AGREEMENT_ANALYTICS


def test_mode_detection():
    assert parse_query("air rate to Chennai").mode is TransportMode.AIR
    assert parse_query("courier charge to Pune").mode is TransportMode.COURIER


# --- embeddings ------------------------------------------------------------ #
def test_local_embedding_deterministic_and_unit():
    a, b = embed("Meerut to Bangalore road freight"), embed("Meerut to Bangalore road freight")
    assert a == b                                   # deterministic
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6  # unit length


def test_similar_text_scores_higher_than_unrelated():
    q = embed("freight rate Meerut to Bangalore")
    near = embed("Meerut to Bangalore freight cost")
    far = embed("insurance liability arbitration clause")
    assert cosine(q, near) > cosine(q, far)


# --- chunk text builders --------------------------------------------------- #
def test_build_rate_text():
    rate = SimpleNamespace(
        transport_mode=TransportMode.ROAD, rate_basis=RateBasis.PER_TRIP,
        origin="Meerut", destination="Bangalore", origin_state=None,
        destination_state="Karnataka", destination_zone=None, vehicle_type="Tata 407",
        service_level=None, temperature_band=None, rate_value=12500.0,
    )
    text = build_rate_text(rate, "Safexpress")
    assert "Safexpress" in text and "Meerut" in text and "Bangalore" in text
    assert "Tata 407" in text and "12500" in text


def test_build_clause_and_metadata_text():
    clause = SimpleNamespace(clause_type=SimpleNamespace(value="PENALTY"), text="Rs 500 per day")
    assert "PENALTY" in build_clause_text(clause, "Safexpress")
    meta = SimpleNamespace(vendor_name="Safexpress", effective_date="2024-04-01",
                           expiry_date="2025-03-31", payment_terms="30 days")
    assert "expires 2025-03-31" in build_metadata_text(meta, "Safexpress")
