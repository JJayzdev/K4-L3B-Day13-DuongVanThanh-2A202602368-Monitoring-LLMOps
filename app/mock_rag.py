from __future__ import annotations

import time

from .incidents import STATE
from .pii import summarize_text
from .tracing import get_langfuse_client, observe

CORPUS = {
    "refund": ["Refunds are available within 7 days with proof of purchase."],
    "monitoring": ["Metrics detect incidents, logs identify affected requests, traces localize the root cause."],
    "policy": ["Do not expose PII in logs. Use sanitized summaries only."],
}


@observe(name="retrieval", as_type="retriever", capture_input=False, capture_output=False)
def retrieve(message: str) -> list[str]:
    if STATE["tool_fail"]:
        raise RuntimeError("Vector store timeout")
    if STATE["rag_slow"]:
        time.sleep(2.5)
    lowered = message.lower()
    matched_docs = ["No domain document matched. Use general fallback answer."]
    for key, docs in CORPUS.items():
        if key in lowered:
            matched_docs = docs
            break
    get_langfuse_client().update_current_span(
        metadata={
            "doc_count": len(matched_docs),
            "query_preview": summarize_text(message),
            "docs_preview": [summarize_text(doc) for doc in matched_docs],
        },
    )
    return matched_docs

