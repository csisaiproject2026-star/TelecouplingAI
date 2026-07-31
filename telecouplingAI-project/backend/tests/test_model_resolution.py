from agent import _supports_thinking
from config import resolve_model_name, settings


def test_frontend_25_identifier_resolves_to_35():
    assert resolve_model_name("gemini-2.5-flash") == "gemini-3.5-flash"


def test_other_model_identifier_passes_through():
    assert resolve_model_name("gemini-3.6-flash") == "gemini-3.6-flash"


def test_missing_model_uses_configured_default(monkeypatch):
    monkeypatch.setattr(settings, "DEFAULT_MODEL", "configured-default")
    assert resolve_model_name(None) == "configured-default"
    assert resolve_model_name("  ") == "configured-default"


def test_migrated_model_keeps_thinking_support():
    assert _supports_thinking("gemini-2.5-flash")
    assert _supports_thinking("gemini-3.5-flash")
    assert not _supports_thinking("gemini-2.0-flash")
