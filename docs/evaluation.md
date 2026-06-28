# Evaluation

The kit ships a golden eval harness that computes per-class
precision / recall / F1 + overall accuracy on every push. CI gates on
100% accuracy on the bundled fixtures.

## What gets checked

Per [evals/golden.json](../evals/golden.json), each case is a
(fixture, expected_label) pair. The harness:

1. Runs every case through the classifier.
2. Builds a confusion-matrix-style tally of (expected, actual).
3. Computes per-class precision, recall, F1, and support.
4. Reports overall accuracy.

A run passes when accuracy == 100% on the bundled fixtures.

## Running

```bash
python evals/run.py
```

Output:

```
Running 7 eval cases against backend=rules

  PASS  invoice-001              expected=invoice            actual=invoice            conf=1.00
  PASS  purchase-order-001       expected=purchase_order     actual=purchase_order     conf=1.00
  PASS  contract-001             expected=contract           actual=contract           conf=1.00
  PASS  complaint-001            expected=customer_complaint actual=customer_complaint conf=1.00
  PASS  job-application-001      expected=job_application    actual=job_application    conf=1.00
  PASS  spam-001                 expected=spam_or_promo      actual=spam_or_promo      conf=1.00
  PASS  ambiguous-001            expected=unknown            actual=unknown            conf=0.00

Accuracy: 100%  (7/7)

Per-class metrics:
  class                   precision   recall     F1  support
  contract                     1.00     1.00   1.00        1
  customer_complaint           1.00     1.00   1.00        1
  invoice                      1.00     1.00   1.00        1
  ...
```

Non-zero exit code if accuracy drops below 100%.

## Adding new cases

Edit `evals/golden.json`:

```json
{"id": "claim-001", "fixture": "claim-001.txt", "expected": "insurance_claim"}
```

Drop the corresponding text into `fixtures/claim-001.txt`. Re-run
the harness. If it fails, either the classifier needs a rule update
or the expected label is wrong.

## What real-world deployments do differently

The bundled CI gate is **100% accuracy** because the fixtures are
small and clean. In a real engagement, you'd:

1. **Scale up to 200+ fixtures** including ambiguous and adversarial
   cases.
2. **Lower the overall accuracy gate** to ~90% (some misclassifications
   are inevitable on real noisy data).
3. **Add per-class F1 gates** — "customer_complaint F1 must stay
   above 0.85" is the realistic ask, not "100% accuracy".
4. **Add precision floors per class** for high-stakes routing —
   "invoice precision must be above 0.95" because mis-routing a
   contract to AP is expensive.

Wiring those gates is a 10-line change to `evals/run.py` — extend
`compute_metrics` to read a thresholds dict from the JSON, and fail
when any per-class metric is below its threshold.

## Why per-class metrics matter

Accuracy alone hides class imbalance and asymmetric costs.

Example: 100-document inbox, 90 are spam. A classifier that sends
everything to spam gets 90% accuracy — but every real customer
complaint, invoice, and contract is now in the spam bucket. The
per-class metrics catch this immediately:

| Class | Precision | Recall | F1 |
|---|---|---|---|
| spam_or_promo | 0.90 | 1.00 | 0.95 |
| customer_complaint | 0.00 | 0.00 | 0.00 |
| invoice | 0.00 | 0.00 | 0.00 |

The "0.00 / 0.00" rows scream "this is broken" even though overall
accuracy looks fine.

## Running evals against the LLM backend

Once `_classify_llm` is wired:

```bash
pip install -e ".[llm]"
export ANTHROPIC_API_KEY=sk-...
DOC_CLASSIFIER_BACKEND=llm python evals/run.py
```

Expect the LLM backend to score similarly on the bundled fixtures
(they're easy). The real value is running it against your messy
production data + gold labels and watching F1 per class.

This is also how you watch model upgrades: re-run the eval suite
after switching Claude versions, see which classes flipped, decide
if it's drift or improvement.

## Evidence per case

The harness reports the per-case label + confidence. The full
classification (including evidence + top-3 candidates) is in the
JSON output of `doc-classifier classify --json <fixture>`. Use
this when debugging an unexpected pass or fail — the evidence
field tells you exactly which keywords drove the score.

## Performance

The full eval suite runs in ~10ms on the rules backend. Scaling to
500 cases keeps it under a second. The LLM backend will be ~1-3s
per case (use batching for large eval suites).
