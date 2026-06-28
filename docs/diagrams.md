# Diagrams

GitHub renders Mermaid natively. These render on the README and in this file.

## Classify -> route pipeline

```mermaid
flowchart LR
    D[Inbound document text] --> C["Classifier.classify(text)"]
    C --> B{Backend?}
    B -- "rules (default)" --> RX[keyword + length-weight scoring]
    B -. "llm" .-> LL[Claude JSON classification]
    RX --> R["ClassificationResult<br/>{label, confidence, candidates, evidence}"]
    LL --> R
    R --> RT["route(result, catalog)"]
    RT --> T{review_required?}
    T -- no --> Q1[Class queue<br/>e.g., accounts_payable]
    T -- yes --> Q2[human_review queue]
```

## The review-routing decision

```mermaid
flowchart TB
    R[ClassificationResult] --> A{label == 'unknown'?}
    A -- yes --> H1["human_review<br/>reason: 'no matching class'"]
    A -- no --> B{confidence >= threshold?}
    B -- no --> H2["human_review<br/>reason: 'confidence below threshold (0.XX)'"]
    B -- yes --> C{class in catalog?}
    C -- no --> H3["human_review<br/>reason: 'class X not in catalog'"]
    C -- yes --> Q["class.queue<br/>(SLA from class.sla_hours)"]
```

## Confidence scoring (rules backend)

```mermaid
flowchart LR
    T[Document text] --> S[Per-class keyword scoring]
    S --> W["weight = 1.0 + 0.1 * len(keyword)<br/>score += count(kw) * weight"]
    W --> R[Top-k candidates by score]
    R --> M["margin = top / (top + runner_up)"]
    R --> ST["strength = min(1.0, top / 10.0)"]
    M --> C["confidence = margin * strength"]
    ST --> C
    C --> RR{confidence < threshold?}
    RR -- yes --> RV[review_required = True]
    RR -- no --> AR[review_required = False]
```

The length-weight is the trick: longer/more-specific keywords get
weighted higher per match, so "demand a refund" outweighs "refund"
when both appear.

## Eval harness

```mermaid
sequenceDiagram
    participant CI as CI
    participant E as evals/run.py
    participant C as Classifier
    participant G as golden.json
    participant M as metrics

    CI->>E: python evals/run.py
    E->>G: load cases
    loop each case
        E->>C: classify(fixture text)
        C-->>E: ClassificationResult
        E->>E: compare actual vs expected
    end
    E->>M: compute_metrics(results)
    M-->>E: per-class P/R/F1 + accuracy
    E->>CI: print report + exit code
    CI-->>CI: PR fails if accuracy < 100%
```

## Rules vs LLM backend

```mermaid
flowchart TB
    subgraph Rules["rules backend (default)"]
        direction TB
        R1[text] --> R2[per-class keyword scoring]
        R2 --> R3[ClassificationResult with heuristic confidence]
    end

    subgraph LLM["llm backend"]
        direction TB
        L1[text] --> L2["build prompt(text, catalog)"]
        L2 --> L3["client.messages.create()"]
        L3 --> L4[parse JSON response]
        L4 --> L5[ClassificationResult with model confidence]
    end

    Rules -. "same shape" .- LLM
```

## Repo shape

```mermaid
flowchart TB
    R[document-classifier-kit]
    R --> SRC[src/doc_classifier/]
    SRC --> S1[schema.py — catalog + validation]
    SRC --> S2[classifier.py — backends + router]
    SRC --> S3[cli.py — classify/demo/list-classes]
    R --> FIX[fixtures/]
    FIX --> F1[invoice / po / contract / complaint / job / spam / ambiguous .txt]
    R --> T[tests/]
    T --> T1[test_schema.py]
    T --> T2[test_classifier.py]
    R --> EV[evals/]
    EV --> EG[golden.json]
    EV --> ER[run.py — per-class P/R/F1]
    R --> DOCS[docs/]
    R --> CI[.github/workflows/ci.yml]
    R --> DK[Dockerfile]
```
