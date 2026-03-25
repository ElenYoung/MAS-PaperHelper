from core.config import load_config
from core.diagnostics import run_diagnostics


def test_run_diagnostics_has_required_keys() -> None:
    cfg = load_config("config/config.yaml")
    report = run_diagnostics(cfg)

    assert "generation_endpoint" in report
    assert "embedding_endpoint" in report
    assert "sources" in report
    assert "users" in report
    assert "overall_ok" in report
