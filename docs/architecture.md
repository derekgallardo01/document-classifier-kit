# Architecture

The kit is built around three ideas:

1. **Catalog declares what classes exist** (separate from how to detect them).
2. **Backend decides how to classify** (rules deterministic by default; LLM swap is one method).
3. **Router decides where to send the doc** (confident classifications go to the class's queue; below-threshold goes to `human_review`).

## The pipeline

```
Inbound document text
    -> Classifier.classify(text)
        -> _classify_rules(text)  OR  _classify_llm(text)
        -> ClassificationResult{label, confidence, candidates, evidence, review_required}
    -> route(result, catalog)
        -> RoutingDecision{queue, sla_hours, review_required, handoff_reason}
    -> downstream system (your queue or human review)
```

Each component is testable in isolation:

- `schema` — pure data
- `classifier` — tested against fixtures
- `route` — tested with synthetic results

## The catalog

[src/doc_classifier/schema.py](../src/doc_classifier/schema.py) exports
`DocClass` and `Catalog`. Each `DocClass` declares:

- **name** — label emitted by the classifier
- **queue** — downstream destination (your routing key)
- **sla_hours** — review SLA (used by downstream queueing systems)
- **keywords** — signals the rules backend looks for
- **description** — used in LLM prompts and the `list-classes` output

`Catalog.validate()` catches structural problems before init:
- Duplicate class names
- Empty keyword lists (rules backend can never match)
- Non-positive SLAs
- Empty class list

This runs in `Classifier.__init__` so a misconfigured catalog raises
immediately, not at first classification.

## The classifier

```python
def classify(self, text):
    if self.backend == "llm":
        return self._classify_llm(text)
    return self._classify_rules(text)
```

The rules backend scores per class:

```
score(class) = sum over class.keywords of:
    count(keyword in text) * (1.0 + 0.1 * len(keyword))
```

The length-weight is the key trick. Without it, the keyword "tax"
would outweigh "demand a refund" because "tax" appears in more
documents. With it, longer + more specific keywords carry more
signal — which is what humans intuit when they label data.

Confidence is then:

```
confidence = (top_score / (top_score + runner_up_score))    # margin over second-best
           * min(1.0, top_score / 10.0)                     # absolute signal strength
```

So a doc that scores 8 for `invoice` and 0 for everything else gets
margin=1.0 but strength=0.8, so confidence=0.8.

A doc that scores 1 for `invoice` and 0 for everything else gets
margin=1.0 but strength=0.1, so confidence=0.1 — fires the human
review threshold even though "invoice" was the top class.

The same shape gets produced by the LLM backend (the LLM returns
both margin-like and strength-like signals, mapped to the same
0-1 confidence number).

## The router

```python
def route(result, catalog) -> RoutingDecision:
    if result.label == "unknown":      # no class scored > 0
        return RoutingDecision(queue="human_review", ..., handoff_reason="no matching class")
    if result.review_required:         # confidence below threshold
        return RoutingDecision(queue="human_review", ..., handoff_reason=f"confidence below threshold ({result.confidence:.2f})")
    cls = catalog.by_name(result.label)
    return RoutingDecision(queue=cls.queue, sla_hours=cls.sla_hours, ...)
```

Three review paths:

| Path | When | Reason emitted |
|---|---|---|
| no matching class | `result.label == "unknown"` | `"no matching class"` |
| below threshold | `confidence < review_threshold` | `"confidence below threshold (0.XX)"` |
| stale catalog | predicted class no longer in catalog | `"class 'X' not in catalog"` |

The `handoff_reason` is what downstream review queues use to display
"why am I looking at this?" to the human reviewer. Vague reasons
("low confidence") force the human to guess. Specific reasons cut
review time by a factor of 2-3 in our experience.

## Why a rules backend at all?

Three reasons:

1. **Deterministic CI.** The eval harness asserts per-class metrics.
   An LLM backend's scores fluctuate across runs; rules don't.
2. **Zero cost / zero keys.** Reviewers clone-and-run in 60 seconds.
   No `ANTHROPIC_API_KEY` blocker.
3. **Forces good class design.** If your rules can't tell two classes
   apart, the classes themselves are overlapping. Fix the catalog,
   not the LLM prompt.

The hybrid pattern is what most production deployments end up running:
rules first for the obvious cases (cost-free, instant); LLM only for
the ambiguous ones (where the rules backend's confidence is below the
review threshold but the doc is worth not sending to a human). The
kit makes that hybrid swap painless because the shape doesn't change.

## Why per-class metrics (vs just accuracy)?

Accuracy hides class imbalance. If 90% of your inbox is spam and the
classifier sends everything to spam, you get 90% accuracy but every
real invoice goes to the wrong queue.

The eval harness computes per-class precision (of docs we said were
class X, how many actually were?) and recall (of docs that were
actually class X, how many did we catch?). For different classes you
care about different metrics:

- **Customer complaints**: recall first (missing one is expensive)
- **Spam classification**: precision first (false positive = real
  email goes to spam)
- **Job applications**: balanced (both matter)

The harness gives you the numbers; you set the per-class thresholds
your engagement cares about.

## What's deliberately NOT in the kit

- **Multi-label classification** — the kit assumes one label per
  document. For multi-label (doc could be both invoice + contract),
  fork and adjust `_classify_rules` to emit all classes above a
  threshold instead of the top one.
- **Active learning** — when the human reviewer corrects a label,
  the kit doesn't auto-update the catalog. That's a feature you'd
  add at the queue layer (Cosmos / Postgres trigger that retrains
  on a schedule).
- **Document parsing** — the kit operates on text. Pair with
  `pdf-extraction-kit` (parse text first) for PDFs, or a custom
  email parser for inbox documents.
