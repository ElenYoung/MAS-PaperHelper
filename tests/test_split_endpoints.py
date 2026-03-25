from core.config import load_config


def test_split_model_embedding_endpoints_are_loaded() -> None:
    cfg = load_config("config/config.yaml")
    assert cfg.global_config.base_model_api_base is not None
    assert cfg.global_config.embedding_api_base is not None
