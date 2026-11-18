import httpx

from src import model_context


def test_unreachable_local_endpoint_probes_once_then_skips(monkeypatch):
    model_context._context_cache.clear()
    model_context._unreachable_until.clear()
    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(model_context.httpx, "get", fake_get)
    endpoint = "http://192.168.219.48:8000/v1/chat/completions"

    first = model_context.get_context_length(endpoint, "some-unknown-model")
    second = model_context.get_context_length(endpoint, "some-unknown-model")

    assert first == second == model_context.DEFAULT_CONTEXT
    # One timed-out probe, not /slots + /props + /models on every lookup.
    assert len(calls) == 1
    model_context._unreachable_until.clear()


def test_unreachable_remote_endpoint_models_probe_skipped(monkeypatch):
    model_context._context_cache.clear()
    model_context._catalog_ctx_cache.clear()
    model_context._unreachable_until.clear()
    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(model_context.httpx, "get", fake_get)
    endpoint = "http://studio.example.com:1234/v1/chat/completions"

    model_context.get_context_length(endpoint, "unknown-model-a")
    model_context.get_context_length(endpoint, "unknown-model-b")

    assert len(calls) == 1
    model_context._unreachable_until.clear()
