from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from .models import AiConfig, AiResult


def load_local_env() -> None:
    """
    从项目根目录按顺序加载 `.env.local` / `.env`。
    已存在的环境变量不覆盖，避免影响外部部署环境。
    """
    if os.getenv("GOSUAN_SKIP_LOCAL_ENV", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    roots = [Path.cwd(), Path(__file__).resolve().parents[2]]
    loaded: set[Path] = set()
    for root in roots:
        for filename in (".env.local", ".env"):
            env_file = (root / filename).resolve()
            if env_file in loaded or not env_file.exists():
                continue
            loaded.add(env_file)
            for line in env_file.read_text(encoding="utf-8").splitlines():
                text = line.strip()
                if not text or text.startswith("#") or "=" not in text:
                    continue
                key, value = text.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


def ai_config_from_env() -> AiConfig:
    load_local_env()
    enabled = os.getenv("GOSUAN_AI_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    base_url = os.getenv("GOSUAN_AI_BASE_URL", "https://openrouter.ai/api/v1").strip()
    api_key = os.getenv("GOSUAN_AI_API_KEY", "").strip()
    model = os.getenv("GOSUAN_AI_MODEL", "openrouter/free").strip()
    temperature = float(os.getenv("GOSUAN_AI_TEMPERATURE", "0.7"))
    max_output_tokens = int(os.getenv("GOSUAN_AI_MAX_OUTPUT_TOKENS", "900"))
    timeout_s = float(os.getenv("GOSUAN_AI_TIMEOUT_S", "30"))
    return AiConfig(
        enabled=enabled,
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout_s=timeout_s,
    )


def generate_ai_text(*, prompt: str, ai: AiConfig) -> AiResult:
    """
    使用 OpenAI 兼容接口生成文本。

    默认走 `POST {base_url}/chat/completions`，以最大化兼容性（各家网关通常都支持）。
    """
    if not ai.api_key:
        raise ValueError(
            "AI 已启用但未提供 API Key。可先使用免费方案："
            "设置 GOSUAN_AI_BASE_URL=https://openrouter.ai/api/v1、"
            "GOSUAN_AI_MODEL=openrouter/free，并填入 GOSUAN_AI_API_KEY。"
        )

    url = ai.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {ai.api_key}",
        "Content-Type": "application/json",
        **(ai.extra_headers or {}),
    }
    payload: dict[str, Any] = {
        "model": ai.model,
        "temperature": ai.temperature,
        "messages": [
            {"role": "system", "content": "你是一个严谨、克制、可解释的命理与择日分析助手。"},
            {"role": "user", "content": prompt},
        ],
    }

    # 兼容不同实现：有的用 max_tokens，有的用 max_output_tokens
    payload["max_tokens"] = ai.max_output_tokens

    with httpx.Client(timeout=ai.timeout_s) as client:
        resp = client.post(url, headers=headers, json=payload)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _friendly_http_error(exc.response, ai)
            raise ValueError(detail) from exc
        data = resp.json()

    text = (
        (data.get("choices") or [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    if not text:
        text = str(data)
    return AiResult(text=text, raw=data)


def _friendly_http_error(response: httpx.Response, ai: AiConfig) -> str:
    status = response.status_code
    body = response.text[:500]
    provider_hint = "当前提供方可能要求更换模型名、开通权限，或使用对应控制台里创建的专用 endpoint/model 标识。"
    if "volces.com" in ai.base_url:
        provider_hint = "豆包/火山引擎返回拒绝。请优先检查 API Key 是否可用、模型名是否为你账号已开通的模型或专用推理接入点。"
    if status in {401, 403}:
        return f"AI 服务鉴权失败（HTTP {status}）。{provider_hint} 响应片段：{body}"
    if status == 404:
        return f"AI 接口地址或模型不存在（HTTP 404）。请检查 base_url/model 是否正确。响应片段：{body}"
    return f"AI 服务调用失败（HTTP {status}）。响应片段：{body}"

