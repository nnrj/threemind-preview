"""Lab notification policy; no field changes the Core or its protocol."""

import ipaddress
import re
from email.utils import getaddresses
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .ai_schema import Strict
from .health_schema import HealthConfig

EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}")


def mailbox(value, *, display=False):
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("邮箱不能包含换行或控制字符")
    pairs = getaddresses([value])
    if len(pairs) != 1 or not EMAIL.fullmatch(pairs[0][1]) or not display and pairs[0][0]:
        raise ValueError("请填写有效邮箱；收件地址不包含显示名称")
    return value.strip()


class NotificationEvents(Strict):
    structure_recurrence: bool = Field(True, strict=True)
    run_completed: bool = Field(True, strict=True)
    run_failed: bool = Field(True, strict=True)
    run_dead: bool = Field(True, strict=True)
    run_blocked: bool = Field(True, strict=True)
    export_ready: bool = Field(False, strict=True)
    analysis_ready: bool = Field(True, strict=True)
    job_failed: bool = Field(True, strict=True)
    execution_health: bool = Field(True, strict=True)


class NotificationConfig(Strict):
    enabled: bool = Field(False, strict=True)
    email_enabled: bool = Field(False, strict=True)
    language: Literal["follow-ui", "zh-CN", "en"] = "follow-ui"
    ui_language: Literal["zh-CN", "en"] = "zh-CN"
    events: NotificationEvents = Field(default_factory=NotificationEvents)
    execution_health: HealthConfig = Field(default_factory=HealthConfig)
    transport: Literal["resend", "smtp"] = "resend"
    sender: str = Field("ThreeMind <onboarding@resend.dev>", min_length=1, max_length=320)
    recipients: list[str] = Field(default_factory=list, max_length=20)
    smtp_host: str = Field("", max_length=253)
    smtp_port: int = Field(587, ge=1, le=65535, strict=True)
    smtp_security: Literal["starttls", "tls", "none"] = "starttls"
    smtp_username: str = Field("", max_length=320)
    timeout_s: float = Field(12.0, ge=1, le=30, strict=True)
    cooldown_s: int = Field(60, ge=0, le=86400, strict=True)
    daily_email_limit: int = Field(50, ge=1, le=10000, strict=True)

    @field_validator("sender")
    @classmethod
    def sender_address(cls, value):
        return mailbox(value, display=True)

    @field_validator("recipients")
    @classmethod
    def recipient_addresses(cls, values):
        return list(dict.fromkeys(mailbox(v) for v in values))

    @field_validator("smtp_host", "smtp_username")
    @classmethod
    def no_controls(cls, value):
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("SMTP 配置不能包含控制字符")
        return value.strip()

    @field_validator("smtp_host")
    @classmethod
    def host_only(cls, value):
        if not value:
            return value
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            try:
                host = value.encode("idna").decode().lower()
            except UnicodeError:
                raise ValueError("SMTP 主机无效") from None
            if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in host.split(".")):
                raise ValueError("SMTP 主机只填主机名或 IP，不填协议、路径或凭据")
            return host

    @model_validator(mode="after")
    def configured_email(self):
        if self.email_enabled and (not self.recipients or self.transport == "smtp" and not self.smtp_host):
            raise ValueError("启用邮件需要收件人；SMTP 还需要主机")
        return self


class NotificationEdit(Strict):
    config: NotificationConfig
    expected_revision: int = Field(0, ge=0, strict=True)
    api_key: str = Field("", max_length=8192)
    smtp_password: str = Field("", max_length=8192)
    clear_api_key: bool = Field(False, strict=True)
    clear_smtp_password: bool = Field(False, strict=True)

    @model_validator(mode="after")
    def secret_actions(self):
        if self.api_key and self.clear_api_key or self.smtp_password and self.clear_smtp_password:
            raise ValueError("不能同时填写和清除同一凭据")
        return self


class NotificationTest(Strict):
    request_id: UUID


class NotificationRead(Strict):
    ids: list[UUID] = Field(min_length=1, max_length=100)
