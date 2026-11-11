"""Host-side localized notification service; never a Core runtime rule."""
from __future__ import annotations
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from threemind.security import SecretStore

class NotificationService:
    def __init__(self, data_dir: Path) -> None:
        self.store = SecretStore(data_dir, data_name="notifications.enc")
        try: rows = self.store.load()
        except RuntimeError: rows = []
        self.key = str(rows[0].get("resend_api_key") or "") if rows else ""
    def public(self, values: dict[str, Any]) -> dict[str, Any]:
        result = dict(values); result.pop("resend_api_key", None); result.pop("clear_resend_api_key", None)
        result["enabled"] = bool(result.get("enabled", False)); result["sender"] = str(result.get("sender") or "ThreeMind <onboarding@resend.dev>")
        raw = result.get("recipients", []); result["recipients"] = [str(x).strip() for x in raw if str(x).strip()] if isinstance(raw, list) else []
        result["language"] = result.get("language") if result.get("language") in {"zh-CN", "en", "follow-ui"} else "follow-ui"
        result["resend_api_key_configured"] = bool(self.key); result["resend_api_key_hint"] = f"re_••••{self.key[-4:]}" if len(self.key) >= 4 else ("configured" if self.key else "")
        return result
    def update(self, current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        for name in ("enabled", "sender", "language"):
            if name in patch: current[name] = bool(patch[name]) if name == "enabled" else str(patch[name])
        if "recipients" in patch:
            raw = patch["recipients"] if isinstance(patch["recipients"], list) else str(patch["recipients"]).replace(";", ",").replace("\n", ",").split(",")
            current["recipients"] = list(dict.fromkeys(str(x).strip() for x in raw if str(x).strip()))
        if isinstance(patch.get("resend_api_key"), str) and patch["resend_api_key"].strip(): self.key = patch["resend_api_key"].strip(); self.store.save([{"resend_api_key": self.key}])
        if patch.get("clear_resend_api_key") is True: self.key = ""; self.store.save([])
        current.pop("resend_api_key", None); return self.public(current)
    def send(self, values: dict[str, Any], event: dict[str, Any], *, force: bool = False, ui_locale: str = "zh-CN") -> dict[str, Any]:
        s = self.public(values)
        if not force and not s["enabled"]: return {"state":"disabled", "detail":"email notifications are disabled"}
        if not self.key or not s["recipients"]: return {"state":"not_configured", "detail":"Resend API key or recipient addresses are missing"}
        zh = (ui_locale if s["language"] == "follow-ui" else s["language"]).startswith("zh")
        subject = "ThreeMind：通知测试" if force and zh else "ThreeMind: notification test" if force else "ThreeMind：检测到可重复结构" if zh else "ThreeMind: repeatable structure detected"
        heading = "这是一封 ThreeMind 通知测试邮件。" if force and zh else "ThreeMind 检测到一个可重复的输出结构。" if zh else "ThreeMind notification test." if force else "ThreeMind detected a repeatable output structure."
        labels = ("意识 ID", "重复次数", "内部连接", "被动读出", "结构指纹") if zh else ("Consciousness ID", "Occurrences", "Internal edges", "Readout", "Signature")
        text = "\n".join([heading, f"{labels[0]}：{event.get('consciousness_id','')}", f"tick：{event.get('tick',0)}", f"{labels[1]}：{event.get('occurrences',0)}", f"{labels[2]}：{event.get('internal_edges',0)}", f"{labels[3]}：{event.get('readout',event.get('text',''))}", f"{labels[4]}：{event.get('signature','')}"])
        request = urllib.request.Request("https://api.resend.com/emails", data=json.dumps({"from":s["sender"],"to":s["recipients"],"subject":subject,"text":text},ensure_ascii=False).encode(), headers={"Authorization":f"Bearer {self.key}","Content-Type":"application/json","Idempotency-Key":f"threemind-{event.get('id','test')}"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=12) as r: return {"state":"sent","provider_id":json.loads(r.read().decode()).get("id")}
        except urllib.error.HTTPError as e: return {"state":"failed","detail":e.read().decode(errors="replace")[:500]}
        except urllib.error.URLError as e: return {"state":"failed","detail":str(e.reason)}
