"""Tests for the catalog schema."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402
from doc_classifier.schema import Catalog, DocClass, default_catalog  # noqa: E402


def test_default_catalog_validates_clean():
    cat = default_catalog()
    assert cat.validate() == []


def test_default_catalog_has_six_classes():
    cat = default_catalog()
    assert len(cat.classes) == 6
    assert "invoice" in cat.names()
    assert "spam_or_promo" in cat.names()


def test_catalog_catches_duplicate_class_names():
    cat = Catalog(classes=[
        DocClass("a", "qa", 24, ["x"]),
        DocClass("a", "qb", 24, ["y"]),
    ])
    problems = cat.validate()
    assert any("Duplicate" in p for p in problems)


def test_catalog_catches_empty_keywords():
    cat = Catalog(classes=[DocClass("a", "qa", 24, [])])
    problems = cat.validate()
    assert any("zero keywords" in p for p in problems)


def test_catalog_catches_non_positive_sla():
    cat = Catalog(classes=[DocClass("a", "qa", 0, ["x"])])
    problems = cat.validate()
    assert any("sla_hours" in p for p in problems)


def test_catalog_catches_empty_class_list():
    cat = Catalog(classes=[])
    problems = cat.validate()
    assert any("zero classes" in p for p in problems)


def test_by_name_finds_class():
    cat = default_catalog()
    c = cat.by_name("contract")
    assert c is not None
    assert c.queue == "legal_review"


def test_by_name_returns_none_for_unknown():
    cat = default_catalog()
    assert cat.by_name("nope") is None
