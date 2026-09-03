from hive.config import load_config, AppConfig

def test_load_config_defaults():
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.llm.ollama_url.startswith("http")
    assert cfg.llm.lmstudio_url.startswith("http")
