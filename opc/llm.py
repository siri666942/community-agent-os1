"""MiMo API 调用封装 + 全量留痕(07-log.md)。"""
import json
import os
import ssl
import time
import urllib.request

from . import config


def _ssl_context() -> ssl.SSLContext:
    """macOS Python 框架版缺 CA 证书,优先用 certifi,保持校验开启。"""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


class LLMError(RuntimeError):
    pass


def chat(system: str, user: str, max_tokens: int = 1500,
         temperature: float = 0.4, agent: str = "agent",
         input_summary: str = "", retries: int = 2) -> str:
    """调用 MiMo-V2.6-Pro,返回文本。每次调用自动写入动作日志。"""
    if not config.API_BASE or not config.API_KEY:
        raise LLMError("缺少 ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN 环境变量")

    payload = {
        "model": config.MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    data = None
    last_err: Exception | None = None
    t0 = time.time()
    for attempt in range(retries):
        req = urllib.request.Request(
            config.API_BASE + "/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": config.API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=480,
                                        context=_ssl_context()) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            log_action(agent, input_summary or user[:60],
                       f"调用失败(第 {attempt + 1}/{retries} 次): {e}", status="WARN")
            if attempt < retries - 1:
                time.sleep(3)
    if data is None:
        log_action(agent, input_summary or user[:60], f"调用失败: {last_err}",
                   status="ERROR")
        raise LLMError(f"MiMo API 调用失败: {last_err}") from last_err

    text = "".join(
        b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
    ).strip()
    usage = data.get("usage", {})
    log_action(
        agent,
        input_summary or user[:60],
        text,
        status="OK",
        extra=f"耗时 {time.time() - t0:.1f}s | tokens in/out {usage.get('input_tokens')}/{usage.get('output_tokens')}",
    )
    return text


def log_action(agent: str, input_summary: str, output: str,
               status: str = "OK", extra: str = "") -> None:
    """每个 Agent 动作写入 07-log.md:时间、Agent、输入摘要、输出、状态。"""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(config.LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"## {ts} | {agent} | {status}\n")
        f.write(f"- 输入: {_clip(input_summary)}\n")
        f.write(f"- 输出: {_clip(output)}\n")
        if extra:
            f.write(f"- 备注: {extra}\n")
        f.write("\n")


def _clip(s: str, n: int = 300) -> str:
    s = " ".join(str(s).split())
    return s[:n] + ("…" if len(s) > n else "")
