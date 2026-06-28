# Getting started

Five minutes to a working classifier on your machine, zero API keys.

## Install

```bash
git clone https://github.com/derekgallardo01/document-classifier-kit.git
cd document-classifier-kit
pip install -e .
```

Stdlib-only on the default path. The LLM extra is optional
(`pip install -e ".[llm]"`).

## Run the demo

```bash
doc-classifier demo
```

Runs all 7 bundled fixtures. For each one you'll see the predicted
label, the confidence, and which queue the router picked (or whether
it was sent to `human_review`).

## Classify one document

```bash
doc-classifier classify fixtures/invoice-001.txt
```

Shows label + confidence + top-3 candidates + evidence + the routing
decision. Append `--json` for machine-readable output.

## List the catalog

```bash
doc-classifier list-classes
```

Shows each class, its target queue, SLA, and the keywords that signal it.

## Run the tests

```bash
python -m pytest -q
```

23 tests covering the schema, the classifier, the router, and the
backend dispatch. Stub backend is deterministic — runs in under a
second, no network.

## Run the evals

```bash
python evals/run.py
```

7 golden cases. Output includes a per-case PASS/FAIL plus a per-class
metrics table (precision / recall / F1 / support) and overall accuracy.
CI gates on 100% accuracy on the bundled fixtures.

## Classify your own document

```bash
doc-classifier classify path/to/your-doc.txt
```

If it lands in the wrong class, two paths:

1. **Add keywords** to that class in `src/doc_classifier/schema.py`
   (or your own catalog file).
2. **Lower the review threshold** — `Classifier(review_threshold=0.6)`
   sends more borderline cases to human review.

## Swap to the LLM backend

1. Install the optional extra:
   ```bash
   pip install -e ".[llm]"
   ```

2. Set your key:
   ```bash
   export ANTHROPIC_API_KEY=sk-...
   export DOC_CLASSIFIER_BACKEND=llm
   ```

3. Implement `_classify_llm` in
   [src/doc_classifier/classifier.py](../src/doc_classifier/classifier.py)
   per the docstring sketch — about 30 lines of glue against the
   Anthropic SDK.

4. Re-run `doc-classifier demo` — it'll route through the LLM.

The tests pin the backend to `rules` explicitly, so they stay green.

## Next steps

- [Architecture](architecture.md) — classifier design + backend seam
- [Customization](customization.md) — swap the catalog, add a class
- [Evaluation](evaluation.md) — eval harness + per-class metrics
