"""Tests for the classifier + router."""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402
from doc_classifier.classifier import Classifier, route  # noqa: E402
from doc_classifier.schema import Catalog, DocClass, default_catalog  # noqa: E402


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _classify(name: str) -> tuple[Classifier, "ClassificationResult"]:
    clf = Classifier()
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return clf, clf.classify(text)


# ---------- Classification accuracy ----------------------------------------

def test_invoice_fixture_classifies_as_invoice():
    _, r = _classify("invoice-001.txt")
    assert r.label == "invoice"
    assert r.confidence > 0.5
    assert r.review_required is False


def test_purchase_order_fixture_classifies_correctly():
    _, r = _classify("purchase-order-001.txt")
    assert r.label == "purchase_order"


def test_contract_fixture_classifies_correctly():
    _, r = _classify("contract-001.txt")
    assert r.label == "contract"
    assert "agreement" in (e.lower() for e in r.evidence) or any(
        "agreement" in e.lower() for e in r.evidence)


def test_complaint_fixture_classifies_correctly():
    _, r = _classify("complaint-001.txt")
    assert r.label == "customer_complaint"
    # The strongest keywords should appear in evidence.
    assert any("refund" in e.lower() or "complaint" in e.lower() for e in r.evidence)


def test_job_application_fixture_classifies_correctly():
    _, r = _classify("job-application-001.txt")
    assert r.label == "job_application"


def test_spam_fixture_classifies_correctly():
    _, r = _classify("spam-001.txt")
    assert r.label == "spam_or_promo"


def test_ambiguous_fixture_falls_through_to_unknown():
    _, r = _classify("ambiguous-001.txt")
    assert r.label == "unknown"
    assert r.review_required is True


# ---------- Confidence + evidence shape ------------------------------------

def test_strong_match_carries_evidence():
    _, r = _classify("complaint-001.txt")
    assert len(r.evidence) >= 1


def test_candidates_list_is_sorted_descending():
    _, r = _classify("invoice-001.txt")
    scores = [s for _, s in r.candidates]
    assert scores == sorted(scores, reverse=True)


def test_review_threshold_is_respected():
    """A doc with a single weak keyword match should be sent to review."""
    clf = Classifier(review_threshold=0.9)  # Make threshold very strict
    text = "We accept the agreement."  # single keyword for `contract`
    r = clf.classify(text)
    assert r.review_required is True


# ---------- Router behaviour ----------------------------------------------

def test_router_sends_unknown_to_review_queue():
    clf = Classifier()
    text = "this is a totally generic message with no signals"
    r = clf.classify(text)
    d = route(r, clf.catalog)
    assert d.queue == "human_review"
    assert d.review_required is True
    assert d.handoff_reason == "no matching class"


def test_router_uses_class_queue_when_confident():
    clf = Classifier()
    text = (FIXTURES / "invoice-001.txt").read_text(encoding="utf-8")
    r = clf.classify(text)
    d = route(r, clf.catalog)
    assert d.queue == "accounts_payable"
    assert d.sla_hours == 72
    assert d.review_required is False


def test_router_sends_low_confidence_to_review():
    # A doc with one weak keyword for `contract` and nothing else.
    # Confidence will be low; with threshold raised above it, review fires.
    clf = Classifier(review_threshold=0.5)
    text = "We accept the agreement."  # single match for contract
    r = clf.classify(text)
    assert r.label == "contract"
    assert r.confidence < 0.5
    d = route(r, clf.catalog)
    assert d.review_required is True
    assert "below threshold" in d.handoff_reason


# ---------- Backend wiring -------------------------------------------------

def test_default_backend_is_rules():
    saved = os.environ.pop("DOC_CLASSIFIER_BACKEND", None)
    try:
        clf = Classifier()
        assert clf.backend == "rules"
    finally:
        if saved is not None:
            os.environ["DOC_CLASSIFIER_BACKEND"] = saved


def test_invalid_catalog_raises_at_init():
    bad = Catalog(classes=[DocClass("a", "qa", -1, [])])
    with pytest.raises(ValueError):
        Classifier(catalog=bad)
