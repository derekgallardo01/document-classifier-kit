# FAQ

## Is keyword scoring really good enough for production?

For about 70-80% of business documents, yes. The bundled catalog
hits 100% accuracy on its fixtures and would hit similar on
well-formed real docs for those classes. The kit is designed so
you can:

- **Start with rules** — get 80% of the value at zero LLM cost
- **Add an LLM backend** for the remaining 20% where rules struggle
- **Use a hybrid** — rules first, LLM fallback only when confidence
  is low

The rules backend's confidence + threshold mechanism already routes
the ambiguous cases to human review by default. You only need the
LLM when even *with* human review, the volume is unsustainable.

## Why not just use an LLM from the start?

Three reasons:

1. **Cost.** Classifying 100,000 docs/month at Claude prices is
   ~$50-200/month for Haiku, more for Opus. Rules cost $0.
2. **Latency.** Rules classify in microseconds; LLM calls add
   200-1500ms per doc. For real-time routing, rules win.
3. **Determinism in CI.** The eval suite asserts exact labels.
   LLM responses fluctuate; rules don't. Without a deterministic
   baseline, you can't tell whether a "drop in accuracy" is a
   real regression or an LLM weather event.

The kit makes the LLM swap painless when you need it. The default
just makes sure you're not paying for it before you have to.

## How is this different from `nocode-ai-lead-workflow`?

`nocode-ai-lead-workflow` is the same confidence-routed pattern
applied to **leads** (where do incoming customer enquiries go?),
with cross-channel dedupe baked in.

This kit applies the pattern to **documents** (where do incoming
PDFs / emails / forms go?). Different input shape, different class
catalog, same architecture.

In a real engagement you might run both — the lead workflow handles
the inbound enquiry; this kit handles any documents attached to it.

## How is this different from `pdf-extraction-kit`?

`pdf-extraction-kit` answers **"what's in this document?"** — given
that you know it's an invoice, extract the invoice number, total,
line items.

This kit answers **"what kind of document is this?"** — given an
unknown document, decide if it's an invoice (and which queue to
send it to).

They pair: classify first to figure out what schema to apply, then
extract with that schema. Many production pipelines run them
together as a "doc intake" stage.

## Why does the `ambiguous-001` fixture exist?

It's the test that the human-review path actually fires when
nothing matches. Without it, the kit could ship looking correct
(all known classes route confidently) but be broken on the case
that matters most in production — the doc that doesn't fit any
class.

It's also the test that the eval harness handles `unknown` as a
first-class label, not a sentinel for "skip this case".

## How do I add a new class with very few keywords?

Two paths:

1. **Add the class with whatever keywords you have.** The rules
   backend will likely produce low confidence for matches. The
   human-review path will fire often. Use those reviews to learn
   what keywords to add over the next few weeks.

2. **Skip rules entirely for that class and rely on the LLM
   backend** for it. Wire the hybrid backend (see
   [customization.md](customization.md)) and let the LLM handle
   the class with low rules coverage.

Either way: don't make up keywords you don't have evidence for —
that's how you end up with rules that match too much and a
confused classifier.

## What's the review threshold supposed to be?

Default is 0.45. The right value depends on:

- **Cost of misclassification** (high → tighten threshold)
- **Cost of human review** (high → loosen threshold)
- **Distribution of confidences** in your real docs (set the
  threshold where the distribution has a gap)

For the bundled fixtures, every known class scores 1.0, so any
threshold between 0.01 and 0.99 sends `ambiguous-001` to review
and routes the rest. For your real docs, run a sample through and
look at the histogram.

## Does the classifier learn from human corrections?

Not automatically. The kit emits the data you need (label,
confidence, evidence) but doesn't ship a feedback loop because
every deployment has different storage (Postgres / Cosmos /
Snowflake / etc.).

The simplest active-learning pattern is documented in
[customization.md](customization.md): log corrections, alert
when the classifier was confidently wrong (those are the
catalog updates that matter most), retrain or update rules on
a schedule.

## Why six classes and not 60?

Six covers the common shape categories (financial, legal, HR,
customer service, ops, junk). The point is to demonstrate the
pattern, not to ship a universal catalog. For a real engagement
you'd replace the catalog entirely — usually with 8-20 classes
specific to that organization.

The rules backend handles dozens of classes fine; the LLM backend
handles hundreds. The bottleneck isn't class count — it's class
overlap (the classes you can't tell apart no matter how many
keywords you add).

## Can I run this on emails / chat messages / PDFs?

Yes — the kit operates on text. Upstream parsers turn each into
text first:

- **Email** — `email.parser` (stdlib) to extract the body
- **PDF** — `pdf-extraction-kit`'s `pdf_reader.read_text()` or
  `pypdf` directly
- **Chat** — already text; concatenate the recent messages

Pass the text to `Classifier.classify()`. Same shape out
regardless of source.
