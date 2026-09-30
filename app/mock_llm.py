from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any

from .incidents import STATE
from .pii import summarize_text
from .tracing import get_langfuse_client, observe


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class FakeResponse:
    text: str
    usage: FakeUsage
    model: str
    ttft_ms: int


class FakeLLM:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model

    @observe(name="generation", as_type="generation", capture_input=False, capture_output=False)
    def generate(self, prompt: str, *, managed_prompt: Any | None = None) -> FakeResponse:
        started = time.perf_counter()
        time.sleep(0.05)  # mô phỏng thời điểm token đầu tiên sẵn sàng
        ttft_ms = int((time.perf_counter() - started) * 1000)
        time.sleep(0.10)
        input_tokens = max(20, len(prompt) // 4)
        output_tokens = random.randint(80, 180)
        if STATE["cost_spike"]:
            output_tokens *= 4
        answer = (
            "Starter answer. You should improve this output logic and add better quality checks. "
            "Use retrieved context and keep responses concise."
        )
        input_cost = round((input_tokens / 1_000_000) * 3, 6)
        output_cost = round((output_tokens / 1_000_000) * 15, 6)
        total_cost = round(input_cost + output_cost, 6)
        prompt_client = (
            managed_prompt
            if managed_prompt is not None
            and hasattr(managed_prompt, "name")
            and hasattr(managed_prompt, "version")
            and hasattr(managed_prompt, "is_fallback")
            else None
        )
        get_langfuse_client().update_current_generation(
            model=self.model,
            usage_details={
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
            cost_details={
                "input": input_cost,
                "output": output_cost,
                "total": total_cost,
            },
            metadata={
                "ttft_ms": ttft_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": total_cost,
                "answer_preview": summarize_text(answer),
            },
            prompt=prompt_client,
        )
        return FakeResponse(
            text=answer,
            usage=FakeUsage(input_tokens, output_tokens),
            model=self.model,
            ttft_ms=ttft_ms,
        )

