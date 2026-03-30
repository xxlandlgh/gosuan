from __future__ import annotations

from gosuan.openai_compat import ai_config_from_env


def test_ai_config_defaults_to_free_openrouter(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOSUAN_SKIP_LOCAL_ENV", "true")
    monkeypatch.delenv("GOSUAN_AI_API_KEY", raising=False)
    monkeypatch.delenv("GOSUAN_AI_ENABLED", raising=False)
    monkeypatch.delenv("GOSUAN_AI_BASE_URL", raising=False)
    monkeypatch.delenv("GOSUAN_AI_MODEL", raising=False)
    cfg = ai_config_from_env()
    assert cfg.base_url == "https://openrouter.ai/api/v1"
    assert cfg.model == "openrouter/free"


def test_ai_config_can_load_from_local_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "GOSUAN_AI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3\n"
        "GOSUAN_AI_MODEL=doubao-1-5-pro-32k-250115\n"
        "GOSUAN_AI_API_KEY=test-key\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GOSUAN_SKIP_LOCAL_ENV", raising=False)
    monkeypatch.delenv("GOSUAN_AI_BASE_URL", raising=False)
    monkeypatch.delenv("GOSUAN_AI_MODEL", raising=False)
    monkeypatch.delenv("GOSUAN_AI_API_KEY", raising=False)
    cfg = ai_config_from_env()
    assert cfg.base_url == "https://ark.cn-beijing.volces.com/api/v3"
    assert cfg.model == "doubao-1-5-pro-32k-250115"
    assert cfg.api_key == "test-key"
