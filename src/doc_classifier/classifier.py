"""Classifier with a pluggable backend.

Default backend is keyword/rule-based - deterministic, no API keys.
Set DOC_CLASSIFIER_BACKEND=llm to route through Claude.

For each document, the classifier emits:

    ClassificationResult(
        label=<class name or "unknown">,
        confidence=<float between 0 and 1>,
        candidates=[(label, score), ...],   # top-k explored
        evidence=<matched keywords or LLM rationale>,
        review_required=<bool>,             # confidence below threshold
    )

The shape is identical regardless of backend - downstream code (router,
eval harness, CLI) doesn't know which path produced it.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .schema import Catalog, DocClass, default_catalog


@dataclass
class ClassificationResult:
    label: str
    confidence: float
    candidates: list[tuple[str, float]]
    evidence: list[str]
    review_required: bool
    backend: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "candidates": [(n, round(s, 3)) for n, s in self.candidates],
            "evidence": self.evidence,
            "review_required": self.review_required,
            "backend": self.backend,
        }


class Classifier:
    """Schema-driven classifier."""

    def __init__(
        self,
        catalog: Catalog | None = None,
        backend: str | None = None,
        review_threshold: float = 0.45,
    ):
        self.catalog = catalog or default_catalog()
        self.backend = backend or os.environ.get("DOC_CLASSIFIER_BACKEND", "rules")
        self.review_threshold = review_threshold
        problems = self.catalog.validate()
        if problems:
            raise ValueError(f"Invalid catalog: {problems}")

    def classify(self, text: str) -> ClassificationResult:
        if self.backend == "llm":
            return self._classify_llm(text)
        return self._classify_rules(text)

    # ----- The backend seam -----------------------------------------------

    def _classify_rules(self, text: str) -> ClassificationResult:
        """Keyword-and-weight scoring across the catalog.

        Score per class = sum of (keyword match count * length-weight).
        Long, specific keywords (e.g., "demand a refund") outweigh short,
        generic ones (e.g., "refund"). Final confidence is the top score
        normalized by margin over the runner-up.
        """
        text_lower = text.lower()
        scores: dict[str, float] = {}
        matched: dict[str, list[str]] = {c.name: [] for c in self.catalog.classes}

        for c in self.catalog.classes:
            s = 0.0
            for kw in c.keywords:
                kw_lower = kw.lower()
                count = text_lower.count(kw_lower)
                if count > 0:
                    # Length-weight: each char of the keyword adds 0.1 to the per-match score.
                    weight = 1.0 + 0.1 * len(kw_lower)
                    s += count * weight
                    matched[c.name].append(kw)
            scores[c.name] = s

        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        if not ranked or ranked[0][1] == 0.0:
            return ClassificationResult(
                label="unknown", confidence=0.0, candidates=ranked[:3],
                evidence=[], review_required=True, backend="rules",
            )

        top, top_score = ranked[0]
        runner_up_score = ranked[1][1] if len(ranked) > 1 else 0.0

        # Confidence is the top's share of the (top + runner-up) sum,
        # then squashed into [0, 1] by total signal strength.
        margin = top_score / (top_score + runner_up_score) if (top_score + runner_up_score) > 0 else 1.0
        strength = min(1.0, top_score / 10.0)  # 10+ points = max strength
        confidence = round(margin * strength, 3)

        return ClassificationResult(
            label=top,
            confidence=confidence,
            candidates=ranked[:3],
            evidence=matched[top],
            review_required=confidence < self.review_threshold,
            backend="rules",
        )

    def _classify_llm(self, text: str) -> ClassificationResult:
        """LLM-based classifier (production swap point).

        Implementation sketch:

            from anthropic import Anthropic
            client = Anthropic()
            prompt = build_classification_prompt(text, self.catalog)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            return _parse_llm_response(response, self.catalog,
                                       self.review_threshold)

        The prompt asks Claude to return JSON shaped like:
            {"label": "...", "confidence": 0-1, "evidence": ["..."],
             "candidates": [{"label": "...", "score": 0-1}]}

        Until wired, fall back to rules so the kit still runs.
        """
        return self._classify_rules(text)


# ----- Router ----------------------------------------------------------------

@dataclass
class RoutingDecision:
    """Where the document goes after classification."""
    queue: str
    sla_hours: int
    label: str
    confidence: float
    review_required: bool
    handoff_reason: str | None  # set when sent to manual review


def route(result: ClassificationResult, catalog: Catalog,
          review_queue: str = "human_review") -> RoutingDecision:
    """Decide the downstream queue based on classification + threshold.

    - Confident, known class -> the class's queue
    - Low confidence -> human_review queue
    - Unknown -> human_review queue with explicit reason
    """
    if result.label == "unknown":
        return RoutingDecision(
            queue=review_queue, sla_hours=24, label="unknown",
            confidence=result.confidence, review_required=True,
            handoff_reason="no matching class",
        )
    if result.review_required:
        return RoutingDecision(
            queue=review_queue, sla_hours=24, label=result.label,
            confidence=result.confidence, review_required=True,
            handoff_reason=f"confidence below threshold "
                           f"(got {result.confidence:.2f})",
        )
    cls = catalog.by_name(result.label)
    if cls is None:
        return RoutingDecision(
            queue=review_queue, sla_hours=24, label=result.label,
            confidence=result.confidence, review_required=True,
            handoff_reason=f"class '{result.label}' not in catalog",
        )
    return RoutingDecision(
        queue=cls.queue, sla_hours=cls.sla_hours, label=result.label,
        confidence=result.confidence, review_required=False,
        handoff_reason=None,
    )
