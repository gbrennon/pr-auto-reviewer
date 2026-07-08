import pytest
from pr_auto_reviewer.infrastructure.llm.prompt_budget import PromptBudget

def test_estimate_and_consume_and_remaining():
    text = "x" * 100
    est = PromptBudget.estimate_tokens(text)
    pb = PromptBudget(max_tokens=1000)
    consumed = pb.consume(text)
    assert consumed == est
    assert pb.consumed_tokens == est
    assert pb.remaining_tokens == pb.max_tokens - est

def test_would_fit_and_try_consume():
    pb = PromptBudget(max_tokens=5)
    small = "x" * 4
    assert pb.would_fit(small)
    assert pb.try_consume(small) is True
    big = "x" * 100
    assert not pb.would_fit(big)
    assert pb.try_consume(big) is False
