"""SophNet / MiMo 模型调用封装与动作留痕。"""
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
         input_summary: str = "") -> str:
    """返回完整模型文本；失败、截断、空输出均抛出 LLMError。"""
    if config.LLM_PROVIDER == 'magpie':
        payload = {'model': config.MODEL, 'max_output_tokens': max_tokens,
                   'input': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
        url = config.MAGPIE_BASE + '/v1/responses'
        headers = {'Authorization': 'Bearer ' + config.MAGPIE_TOKEN,
                   'x-openai-actor-authorization': config.MAGPIE_ACTOR_TOKEN,
                   'content-type': 'application/json'}
    elif config.LLM_PROVIDER == 'mimo':
        if not config.API_BASE or not config.API_KEY:
            raise LLMError('缺少 ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN 环境变量')
        payload = {'model': config.MODEL, 'max_tokens': max_tokens, 'temperature': temperature,
                   'system': system, 'messages': [{'role': 'user', 'content': user}]}
        url = config.API_BASE + '/v1/messages'
        headers = {'x-api-key': config.API_KEY, 'anthropic-version': '2023-06-01',
                   'content-type': 'application/json'}
    else:
        raise LLMError('不支持的 OPC_LLM_PROVIDER，请选择 magpie 或 mimo')
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180, context=_ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        log_action(agent, input_summary or user[:60], '模型调用失败', status='ERROR')
        raise LLMError(f'模型调用失败（{type(e).__name__}）') from e

    if not isinstance(data, dict):
        raise LLMError('模型响应格式无效')
    if config.LLM_PROVIDER == 'magpie':
        if data.get('status') != 'completed':
            raise LLMError('模型响应未完整完成')
        output = data.get('output')
        if not isinstance(output, list): raise LLMError('模型响应格式无效')
        blocks = [block for item in output if isinstance(item, dict) and item.get('type') == 'message'
                  for block in (item.get('content') if isinstance(item.get('content'), list) else [])
                  if isinstance(block, dict) and block.get('type') == 'output_text']
        if any(not isinstance(block.get('text'), str) for block in blocks): raise LLMError('模型文本格式无效')
        text = ''.join(block['text'] for block in blocks).strip()
    else:
        if data.get('stop_reason') != 'end_turn':
            raise LLMError('MiMo 响应未完整完成')
        blocks = data.get('content')
        if not isinstance(blocks, list): raise LLMError('模型响应格式无效')
        blocks = [block for block in blocks if isinstance(block, dict) and block.get('type') == 'text']
        if any(not isinstance(block.get('text'), str) for block in blocks): raise LLMError('模型文本格式无效')
        text = ''.join(block['text'] for block in blocks).strip()
    if not text:
        raise LLMError('模型未返回文本')
    usage = data.get('usage') if isinstance(data.get('usage'), dict) else {}
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
