"""Two explicit HTTP protocols. Text only; no tools, fallback, or implicit retries."""

from __future__ import annotations

import codecs
import json
from dataclasses import dataclass, field

import httpx

from .ai_schema import ProviderConfig

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_STREAM_BYTES = 8 * 1024 * 1024


class ProviderFailure(ValueError):
    pass


def request_body(config, prompt):
    body = {"model": config.model, "stream": config.stream}
    if config.temperature is not None:
        body["temperature"] = config.temperature
    messages = [{"role": key, "content": prompt[key]} for key in ("system", "user")]
    if config.protocol == "responses":
        body.update(input=messages, max_output_tokens=config.max_output_tokens, store=False)
    else:
        body.update(messages=messages, **{config.chat_token_field: config.max_output_tokens})
        if config.stream and config.include_usage:
            body["stream_options"] = {"include_usage": True}
    return body


def usage_of(data):
    if not isinstance(data, dict):
        return None
    a, b = data.get("input_tokens", data.get("prompt_tokens")), data.get("output_tokens", data.get("completion_tokens"))
    if any(type(value) is not int or value < 0 for value in (a, b)):
        return None
    return {"input_tokens": a, "output_tokens": b, "total_tokens": a + b}


def response_text(data):
    parts = []
    for item in data.get("output", []):
        if item.get("type") == "reasoning":
            continue
        if item.get("type") != "message":
            raise ProviderFailure("供应商返回了未启用的工具输出")
        for part in item.get("content", []):
            if part.get("type") == "refusal":
                raise ProviderFailure("供应商拒绝了本次请求")
            if part.get("type") == "output_text":
                parts.append(part["text"])
    return "".join(parts)


@dataclass
class Completion:
    text: str = ""
    meta: dict = field(default_factory=dict)
    usage: dict | None = None
    complete: bool = False

    def append(self, text):
        if not isinstance(text, str):
            raise ProviderFailure("供应商文本响应格式错误")
        self.text += text
        if len(self.text.encode()) > MAX_RESPONSE_BYTES:
            raise ProviderFailure("供应商响应超过 2 MiB 上限")

    def event(self, value, protocol, *, streaming=True):
        if not isinstance(value, dict):
            raise ProviderFailure("供应商事件必须为对象")
        if value.get("error"):
            raise ProviderFailure("供应商返回错误事件")
        if protocol == "chat":
            if value.get("model"):
                self.meta["reported_model"] = str(value["model"])[:200]
            if value.get("id"):
                self.meta["response_id"] = str(value["id"])[:300]
            if value.get("usage"):
                self.usage = usage_of(value["usage"])
            for choice in value.get("choices", []):
                if choice.get("index", 0) != 0:
                    raise ProviderFailure("供应商返回了多个候选；当前工具仅接受单个结果")
                message = choice.get("delta" if streaming else "message", {}) or {}
                if message.get("refusal"):
                    raise ProviderFailure("供应商拒绝了本次请求")
                if message.get("tool_calls") or message.get("function_call"):
                    raise ProviderFailure("供应商返回了未启用的工具调用")
                if message.get("content"):
                    self.append(message["content"])
                reason = choice.get("finish_reason")
                if reason is not None:
                    self.meta["finish_reason"] = reason
                    if reason != "stop":
                        raise ProviderFailure("供应商未正常完成输出（截断、过滤或工具调用）")
                    self.complete = True
        else:
            kind = value.get("type")
            if kind == "response.output_text.delta":
                self.append(value["delta"])
            if kind in ("error", "response.failed", "response.incomplete", "response.refusal.delta"):
                raise ProviderFailure("供应商输出失败、不完整或拒绝")
            if kind == "response.completed" or not streaming:
                response = value.get("response", {}) if streaming else value
                if response.get("status") != "completed":
                    raise ProviderFailure("供应商没有确认完整响应")
                text = response_text(response)
                if self.text and self.text != text:
                    raise ProviderFailure("流式文本与最终响应不一致")
                self.text = ""
                self.append(text)
                self.usage = usage_of(response.get("usage"))
                self.meta = {
                    "response_id": str(response.get("id", ""))[:300],
                    "reported_model": str(response.get("model", ""))[:200],
                    "finish_reason": "completed",
                }
                self.complete = True


class SSE:
    def __init__(self, completion, protocol):
        self.completion, self.protocol = completion, protocol
        self.decoder = codecs.getincrementaldecoder("utf-8")("strict")
        self.buffer = ""
        self.data = []
        self.total = 0
        self.ended = False

    def feed(self, raw, *, final=False):
        self.total += len(raw)
        if self.total > MAX_STREAM_BYTES:
            raise ProviderFailure("供应商事件流超过 8 MiB 上限")
        self.buffer += self.decoder.decode(raw, final=final)
        if len(self.buffer.encode()) > MAX_RESPONSE_BYTES:
            raise ProviderFailure("供应商单个事件行过大")
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line == "":
                self.dispatch()
            elif line.startswith("data:"):
                self.data.append(line[5:].removeprefix(" "))
        if final and (self.buffer or self.data):
            # A partial last event is not a confirmed completion.
            raise ProviderFailure("供应商事件流在完整事件边界之前断开")

    def dispatch(self):
        if not self.data:
            return
        raw, self.data = "\n".join(self.data), []
        if self.ended:
            raise ProviderFailure("供应商在流结束后继续返回数据")
        if raw == "[DONE]":
            self.ended = True
            return
        self.completion.event(json.loads(raw), self.protocol)


async def complete(config: ProviderConfig, secrets, prompt, result: Completion, progress, *, transport=None):
    headers = {"Accept": "text/event-stream" if config.stream else "application/json"}
    if secrets.get("api_key"):
        headers["Authorization"] = "Bearer " + secrets["api_key"]
    proxy = None
    if config.proxy_url:
        proxy = httpx.Proxy(
            config.proxy_url,
            auth=(config.proxy_username, secrets.get("proxy_password", "")) if config.proxy_username else None,
        )
    suffix = "/responses" if config.protocol == "responses" else "/chat/completions"
    url = config.base_url if config.base_url.endswith(suffix) else config.base_url + suffix
    async with (
        httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_s, connect=min(15, config.timeout_s)),
            follow_redirects=False,
            trust_env=False,
            proxy=proxy,
            transport=transport,
        ) as client,
        client.stream("POST", url, headers=headers, json=request_body(config, prompt)) as response,
    ):
        if response.status_code != 200:
            # Never persist a provider's raw error body, proxy URL or headers.
            raise ProviderFailure(f"供应商 HTTP {response.status_code}；请检查协议、模型、凭据及配额")
        if config.stream:
            if "text/event-stream" not in response.headers.get("content-type", ""):
                raise ProviderFailure("供应商未返回请求的 SSE 流；可在配置中关闭流式响应")
            parser = SSE(result, config.protocol)
            async for chunk in response.aiter_bytes():
                parser.feed(chunk)
                await progress(result)
            parser.feed(b"", final=True)
        else:
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ProviderFailure("供应商响应超过 2 MiB 上限")
            result.event(json.loads(raw), config.protocol, streaming=False)
        if not result.complete or not result.text.strip():
            raise ProviderFailure("没有收到完整且非空的文本响应；部分内容不能用于工具执行")
    return result
