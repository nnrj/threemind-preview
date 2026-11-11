from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True, allow_inf_nan=False)


def endpoint_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if (
        parts.scheme not in ("https", "http")
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or any(ord(ch) < 33 for ch in value)
    ):
        raise ValueError("地址必须是 HTTP(S) 地址，不能包含凭据、查询参数、片段或空白")
    _ = parts.port  # Reject malformed ports now, before any network request.
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def origin(value: str) -> str:
    parts = urlsplit(endpoint_url(value))
    return f"{parts.scheme}://{parts.hostname}:{parts.port or (443 if parts.scheme == 'https' else 80)}"


class ProviderConfig(Strict):
    name: str = Field(min_length=1, max_length=120)
    protocol: Literal["chat", "responses"] = "chat"
    base_url: str = Field(min_length=1, max_length=2000)
    model: str = Field(min_length=1, max_length=200)
    enabled: bool = Field(False, strict=True)
    priority: int = Field(100, ge=0, le=10000, strict=True)
    timeout_s: int = Field(60, ge=1, le=600, strict=True)
    max_output_tokens: int = Field(2048, ge=1, le=131072, strict=True)
    temperature: float | None = Field(None, ge=0, le=2, strict=True)
    stream: bool = Field(True, strict=True)
    include_usage: bool = Field(True, strict=True)
    chat_token_field: Literal["max_completion_tokens", "max_tokens"] = "max_completion_tokens"
    max_pending: int = Field(4, ge=1, le=100, strict=True)
    daily_request_limit: int = Field(1000, ge=1, le=1000000, strict=True)
    monthly_budget_usd: float | None = Field(None, gt=0, le=1000000, strict=True)
    input_usd_per_million: float | None = Field(None, ge=0, le=100000, strict=True)
    output_usd_per_million: float | None = Field(None, ge=0, le=100000, strict=True)
    proxy_url: str | None = Field(None, max_length=2000)
    proxy_username: str = Field("", max_length=200)

    @field_validator("name", "model")
    @classmethod
    def nonblank(cls, value):
        if not value.strip() or any(ord(ch) < 32 for ch in value):
            raise ValueError("名称与模型必须填写，不能包含控制字符")
        return value.strip()

    @field_validator("base_url")
    @classmethod
    def base(cls, value):
        return endpoint_url(value)

    @field_validator("proxy_url")
    @classmethod
    def proxy(cls, value):
        if not value:
            return None
        value = endpoint_url(value)
        if urlsplit(value).path:
            raise ValueError("HTTP 代理地址不含路径")
        return value

    @model_validator(mode="after")
    def priced_budget(self):
        if self.monthly_budget_usd is not None and (
            self.input_usd_per_million is None or self.output_usd_per_million is None
        ):
            raise ValueError("启用金额预算需要填写输入、输出单价；免费本地模型可明确填写 0")
        if not self.proxy_url and self.proxy_username:
            raise ValueError("代理用户名需要同时配置代理地址")
        return self


class ProviderEdit(Strict):
    config: ProviderConfig
    expected_revision: int = Field(0, ge=0, strict=True)
    api_key: str = Field("", max_length=8192)
    proxy_password: str = Field("", max_length=8192)
    clear_api_key: bool = Field(False, strict=True)
    clear_proxy_password: bool = Field(False, strict=True)

    @model_validator(mode="after")
    def secret_actions(self):
        if self.api_key and self.clear_api_key or self.proxy_password and self.clear_proxy_password:
            raise ValueError("不能同时填写新凭据和清除同一凭据")
        if any(c in self.api_key for c in "\r\n"):
            raise ValueError("API Key 不能包含换行")
        return self


class TestRequest(Strict):
    request_id: UUID
    prompt: str = Field("请仅回复：连接成功。", min_length=1, max_length=2000)


class Grants(Strict):
    projects: list[UUID] = Field(max_length=1000)
