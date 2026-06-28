# Customization

How to shape the kit for a real engagement.

## Swap the catalog

The bundled catalog is generic SMB-ops. For your engagement, you'll
typically replace it entirely. Build your own and pass it in:

```python
from doc_classifier.classifier import Classifier
from doc_classifier.schema import Catalog, DocClass

my_catalog = Catalog(classes=[
    DocClass(
        name="insurance_claim",
        queue="claims_intake",
        sla_hours=24,
        keywords=["policy number", "date of loss", "claim form",
                  "incident report", "adjuster"],
        description="Insurance claim filed by a policyholder.",
    ),
    DocClass(
        name="renewal_notice",
        queue="renewals_team",
        sla_hours=72,
        keywords=["renewal", "policy expires", "renewal date",
                  "premium notice"],
        description="Outgoing renewal notice.",
    ),
    # ... etc
])

clf = Classifier(catalog=my_catalog)
```

That's it. The classifier, router, eval harness, and CLI work with
any catalog as long as `validate()` passes.

## Add a single class to the bundled catalog

Edit `src/doc_classifier/schema.py::default_catalog`:

```python
DocClass(
    name="service_ticket",
    queue="support_l1",
    sla_hours=8,
    keywords=["ticket #", "service request", "support case",
              "issue id", "incident #"],
    description="Inbound service ticket.",
),
```

Add a fixture and an eval case, run `python evals/run.py` to confirm
the new class doesn't break any others.

## Tune the review threshold

Default is 0.45. Tighter (higher) threshold means more docs sent to
human review; looser (lower) threshold means more autonomous routing.

```python
# Strict - send anything below 0.7 to a human
clf = Classifier(review_threshold=0.7)

# Permissive - only send total fall-throughs (unknown) to human
clf = Classifier(review_threshold=0.1)
```

How to pick: run a sample of real docs through the classifier, look
at the distribution of confidences, and set the threshold where the
distribution has a gap (or where false-positive cost > human-review
cost).

## Improve a class that misclassifies

Two paths:

### Path 1: Add more keywords

If your `insurance_claim` class keeps missing docs that say "loss
report" instead of "incident report", add it:

```python
DocClass(
    name="insurance_claim",
    keywords=["policy number", "date of loss", "claim form",
              "incident report", "loss report", "adjuster",
              "first notice of loss"],
    ...
)
```

Add a fixture + eval case to lock the new behaviour in.

### Path 2: Add a distinguishing keyword to the **other** class

If your `insurance_claim` is being confused with `policy_question`,
the answer might be to make the other class more specific:

```python
DocClass(
    name="policy_question",
    keywords=["coverage limit", "what does my policy cover",
              "is X covered", "exclusion", "policy terms"],
    ...
)
```

Often easier than adding more to the class you want to win.

## Swap to the LLM backend

Implement `_classify_llm` in
[src/doc_classifier/classifier.py](../src/doc_classifier/classifier.py):

```python
def _classify_llm(self, text):
    from anthropic import Anthropic
    client = Anthropic()

    classes_block = "\n".join(
        f"- {c.name}: {c.description}" for c in self.catalog.classes
    )
    prompt = f"""Classify the following document into exactly one of these classes:
{classes_block}

If the document doesn't clearly fit any class, return label="unknown".

Return JSON: {{"label": "...", "confidence": 0.0-1.0,
"candidates": [{{"label": "...", "score": 0.0-1.0}}],
"evidence": ["phrases from the doc that support the label"]}}

Document:
{text[:4000]}
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = json.loads(response.content[0].text)
    return ClassificationResult(
        label=raw["label"],
        confidence=raw["confidence"],
        candidates=[(c["label"], c["score"]) for c in raw.get("candidates", [])],
        evidence=raw.get("evidence", []),
        review_required=raw["confidence"] < self.review_threshold,
        backend="llm",
    )
```

About 30 lines. Tests pin the backend to `rules` so they still pass.
Run `DOC_CLASSIFIER_BACKEND=llm python evals/run.py` to verify the
LLM path agrees with your gold labels.

## Add a hybrid backend

Run rules first; for low-confidence rules results, call the LLM:

```python
def classify(self, text):
    rules_r = self._classify_rules(text)
    if rules_r.confidence >= self.review_threshold:
        return rules_r
    return self._classify_llm(text)  # only the hard cases
```

Most cost-effective production pattern - rules handle the obvious
70-80%, LLM handles the long tail.

## Use a different downstream queue system

`RoutingDecision` is just a dataclass — it doesn't know about
ServiceBus, Cosmos, or any specific queue. Wire it up in your
caller:

```python
import json
from azure.servicebus import ServiceBusClient

def send_to_queue(decision, doc):
    msg = json.dumps({"doc": doc, "decision": asdict(decision)})
    with sb_client.get_queue_sender(decision.queue) as sender:
        sender.send_messages(ServiceBusMessage(msg))

# In your pipeline:
result = clf.classify(text)
decision = route(result, clf.catalog)
send_to_queue(decision, raw_doc)
```

The kit gives you the **decision**; you give it the **transport**.

## Persist classification history for active learning

When the human reviewer corrects a label, you want that signal back:

```python
# Pseudocode for the feedback loop
def on_human_correction(doc_id, original_label, corrected_label, original_confidence):
    feedback_db.insert({
        "doc_id": doc_id,
        "original_label": original_label,
        "corrected_label": corrected_label,
        "original_confidence": original_confidence,
        "corrected_at": now(),
    })

# Periodically (cron / scheduled job):
def retune_catalog():
    corrections = feedback_db.recent(days=30)
    for c in corrections:
        if c["confidence"] > 0.7 and c["original_label"] != c["corrected_label"]:
            # The classifier was confidently wrong - investigate.
            alert_engineer(c)
```

The kit doesn't ship this because every deployment has different
storage. But the confidence score on every classification gives you
the signal you need to triage corrections by surprise.
