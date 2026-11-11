"""Bounded, explicit email transports; database facts are rendered as plain text."""

import json
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, parseaddr

import httpx

TITLES = {
    "test": ("通知测试", "Notification test"),
    "structure_recurrence": ("观察到结构复现", "Structural recurrence observed"),
    "run_completed": ("运行时长已完成", "Run completed"),
    "run_failed": ("运行失败", "Run failed"),
    "run_dead": ("模型活动已耗尽", "Model activity exhausted"),
    "run_blocked": ("运行需要处理", "Run needs attention"),
    "export_ready": ("导出文件已生成", "Export ready"),
    "analysis_ready": ("统计分析已完成", "Analysis ready"),
    "job_failed": ("后台任务失败", "Background task failed"),
    "execution_health": ("执行资源或进度预警", "Execution resource or progress warning"),
}


def message(config, notice):
    locale = config.ui_language if config.language == "follow-ui" else config.language
    title = TITLES.get(notice["kind"], ("研究通知", "Research notification"))[locale == "en"]
    explanation = (
        "以下是已提交的工具事件摘要。结构复现不是意识或理解能力的证明；停止实验也不等于模型死亡。"
        if locale == "zh-CN"
        else "This summarizes a committed tool event. Recurrence does not prove consciousness or understanding; ending an experiment does not imply model death."
    )
    text = f"{title}\n\n{explanation}\n\nnotification_id: {notice['id']}\nproject_id: {notice['project_id']}\n"
    text += json.dumps(notice["facts"], ensure_ascii=False, indent=2, default=str, allow_nan=False)
    return "ThreeMind · " + title, text


def send_resend(config, secrets, notice, *, transport=None):
    subject, text = message(config, notice)
    try:
        with (
            httpx.Client(
                timeout=config.timeout_s, follow_redirects=False, trust_env=False, transport=transport
            ) as client,
            client.stream(
                "POST",
                "https://api.resend.com/emails",
                headers={
                    "Authorization": "Bearer " + secrets["api_key"],
                    "Idempotency-Key": "threemind-" + str(notice["id"]),
                },
                json={"from": config.sender, "to": config.recipients, "subject": subject, "text": text},
            ) as response,
        ):
            if not 200 <= response.status_code < 300:
                return {
                    "status": "failed" if 300 <= response.status_code < 500 else "uncertain",
                    "reason": f"resend_http_{response.status_code}",
                }
            raw = bytearray()
            for chunk in response.iter_bytes():
                if len(raw) + len(chunk) > 65536:
                    return {"status": "uncertain", "reason": "resend_response_limit"}
                raw.extend(chunk)
            value = json.loads(raw)
            provider_id = value.get("id") if isinstance(value, dict) else None
            if not isinstance(provider_id, str) or not 1 <= len(provider_id) <= 200:
                return {"status": "uncertain", "reason": "resend_missing_receipt"}
            return {"status": "sent", "provider_id": provider_id}
    except (httpx.HTTPError, UnicodeError, ValueError):
        return {"status": "uncertain", "reason": "resend_connection_or_response"}


def send_smtp(config, secrets, notice):
    subject, text = message(config, notice)
    payload = EmailMessage()
    payload["From"], payload["To"], payload["Subject"] = config.sender, ", ".join(config.recipients), subject
    payload["Message-ID"] = f"<threemind-{notice['id']}@notifications.threemind.invalid>"
    payload["Date"] = formatdate(localtime=False)
    payload.set_content(text)
    result = None
    try:
        connection = smtplib.SMTP_SSL if config.smtp_security == "tls" else smtplib.SMTP
        options = {"context": ssl.create_default_context()} if config.smtp_security == "tls" else {}
        with connection(config.smtp_host, config.smtp_port, timeout=config.timeout_s, **options) as client:
            client.ehlo()
            if config.smtp_security == "starttls":
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            if config.smtp_username:
                client.login(config.smtp_username, secrets.get("smtp_password", ""))
            refused = client.send_message(payload, from_addr=parseaddr(config.sender)[1], to_addrs=config.recipients)
            result = (
                {"status": "partial", "reason": "smtp_partial_recipient_refusal"} if refused else {"status": "sent"}
            )
        return result
    except smtplib.SMTPAuthenticationError:
        return result or {"status": "failed", "reason": "smtp_authentication"}
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError):
        return result or {"status": "failed", "reason": "smtp_rejected"}
    except (smtplib.SMTPNotSupportedError, smtplib.SMTPConnectError, smtplib.SMTPHeloError):
        return result or {"status": "failed", "reason": "smtp_setup"}
    except (OSError, smtplib.SMTPException, ValueError, UnicodeError):
        return result or {"status": "uncertain", "reason": "smtp_connection_or_response"}


def deliver(config, secrets, notice, *, transport=None):
    return (
        send_resend(config, secrets, notice, transport=transport)
        if config.transport == "resend"
        else send_smtp(config, secrets, notice)
    )
