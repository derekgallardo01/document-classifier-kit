# Walkthrough

End-to-end tour of `doc-classifier demo`.

## Step 1: Load the catalog

```python
from doc_classifier.schema import default_catalog
cat = default_catalog()
# Catalog with 6 DocClass entries, each declaring keywords + queue + SLA
```

`default_catalog()` returns the bundled 6-class catalog (invoice,
purchase_order, contract, customer_complaint, job_application,
spam_or_promo). For your engagement you'd replace it entirely.

## Step 2: Build the classifier

```python
from doc_classifier.classifier import Classifier
clf = Classifier(catalog=cat, review_threshold=0.45)
# Validates the catalog on init - raises if it's malformed
```

`review_threshold=0.45` means any classification below 0.45 confidence
goes to human review instead of the class's queue.

## Step 3: Classify

```python
text = open("fixtures/invoice-001.txt").read()
r = clf.classify(text)
```

`r` is a `ClassificationResult`:

```python
ClassificationResult(
    label="invoice",
    confidence=1.0,
    candidates=[("invoice", 12.3), ("purchase_order", 1.8), ("contract", 0.0)],
    evidence=["invoice", "invoice #", "bill to", "remit to", "amount due"],
    review_required=False,
    backend="rules",
)
```

The classifier:
- Scored every class by keyword count × length-weight
- Picked the top class
- Computed confidence from margin × strength
- Recorded which keywords matched
- Decided whether confidence is below the review threshold

## Step 4: Route

```python
from doc_classifier.classifier import route
d = route(r, cat)
```

`d` is a `RoutingDecision`:

```python
RoutingDecision(
    queue="accounts_payable",
    sla_hours=72,
    label="invoice",
    confidence=1.0,
    review_required=False,
    handoff_reason=None,
)
```

If the classification had been low-confidence or unknown:

```python
RoutingDecision(
    queue="human_review",
    sla_hours=24,
    label="unknown",                          # or the low-confidence label
    confidence=0.0,                           # or the actual low confidence
    review_required=True,
    handoff_reason="no matching class",       # or "confidence below threshold (0.XX)"
)
```

## Step 5: Send to your queue

The kit gives you the **decision**; you give it the **transport**:

```python
import json
from dataclasses import asdict

def send_to_queue(decision, doc_text):
    payload = {
        "doc_id": doc_id,
        "doc_text": doc_text,
        "classification": r.to_dict(),
        "routing": asdict(decision),
    }
    # Azure Service Bus example:
    with sb_client.get_queue_sender(decision.queue) as sender:
        sender.send_messages(ServiceBusMessage(json.dumps(payload)))
```

Or use any other transport — Cosmos, Postgres, Redis, etc.

## Step 6: When the classifier misroutes

Run `doc-classifier classify <doc>` on the failing case:

```
$ doc-classifier classify path/to/weird-doc.txt

  weird-doc.txt
    label:      customer_complaint
    confidence: 0.42
    backend:    rules
    evidence:   ['cancel my', 'unacceptable']
    top 3:      [('customer_complaint', 4.2), ('contract', 3.8), ('spam_or_promo', 0.0)]
    -> queue:   human_review  (SLA 24h)
    review:     confidence below threshold (got 0.42)
```

This is doing the right thing — confidence is below the 0.45
threshold, so the router sent the doc to human review instead of
gambling on a wrong queue. Two possible responses:

1. **Improve the catalog**: add more distinguishing keywords to
   the class that should have won, or add a class that the doc
   actually belongs to.

2. **Lower the threshold** for this engagement if human-review
   throughput is the bottleneck. Be careful: the wrong queue is
   harder to recover from than a human review queue.

Either way: **add this doc as a fixture and an eval case** so the
fix is locked in.
