"""Class catalog - what categories the classifier knows about and how
documents route once classified.

A class declares:
  - name (label emitted by the classifier)
  - queue (downstream destination)
  - sla_hours (review SLA)
  - keywords (signals the rule-based classifier looks for)
  - description (used in LLM prompts + the `list-classes` CLI output)

Adding a class is one entry. The classifier loop, the eval harness, and
the human-review router pick it up automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DocClass:
    name: str
    queue: str
    sla_hours: int
    keywords: list[str]
    description: str = ""


@dataclass
class Catalog:
    classes: list[DocClass]

    def by_name(self, name: str) -> DocClass | None:
        return next((c for c in self.classes if c.name == name), None)

    def names(self) -> list[str]:
        return [c.name for c in self.classes]

    def validate(self) -> list[str]:
        problems = []
        seen_names: set[str] = set()
        for c in self.classes:
            if c.name in seen_names:
                problems.append(f"Duplicate class name: {c.name}")
            seen_names.add(c.name)
            if not c.keywords:
                problems.append(f"Class '{c.name}' declares zero keywords.")
            if c.sla_hours <= 0:
                problems.append(f"Class '{c.name}' has non-positive sla_hours.")
        if not self.classes:
            problems.append("Catalog has zero classes.")
        return problems


def default_catalog() -> Catalog:
    """A worked catalog for an SMB ops mailbox.

    Six classes covering the most common categories of incoming
    business documents. Drop in your own catalog for a real engagement.
    """
    return Catalog(classes=[
        DocClass(
            name="invoice",
            queue="accounts_payable",
            sla_hours=72,
            keywords=["invoice", "invoice #", "bill to", "remit to",
                      "amount due", "subtotal", "tax", "net 30", "net 60"],
            description="Vendor invoice requiring payment.",
        ),
        DocClass(
            name="purchase_order",
            queue="procurement",
            sla_hours=48,
            keywords=["purchase order", "po #", "po number",
                      "ship to", "supplier", "order date"],
            description="Outgoing or incoming purchase order.",
        ),
        DocClass(
            name="contract",
            queue="legal_review",
            sla_hours=120,
            keywords=["agreement", "contract", "parties", "effective date",
                      "governing law", "termination", "renewal", "whereas"],
            description="Service or supply contract requiring legal review.",
        ),
        DocClass(
            name="customer_complaint",
            queue="customer_success",
            sla_hours=24,
            keywords=["complaint", "disappointed", "refund", "cancel my",
                      "unacceptable", "very unhappy", "demand a refund",
                      "filing a chargeback", "this is the third time"],
            description="Customer-facing complaint requiring response.",
        ),
        DocClass(
            name="job_application",
            queue="recruiting",
            sla_hours=120,
            keywords=["resume", "curriculum vitae", "cv", "cover letter",
                      "i am applying", "for the position", "years of experience",
                      "references available"],
            description="Inbound job application.",
        ),
        DocClass(
            name="spam_or_promo",
            queue="archive_spam",
            sla_hours=999999,  # effectively none
            keywords=["limited time offer", "click here", "unsubscribe",
                      "you've been selected", "act now",
                      "free trial", "promotional"],
            description="Marketing / spam; archive without review.",
        ),
    ])
