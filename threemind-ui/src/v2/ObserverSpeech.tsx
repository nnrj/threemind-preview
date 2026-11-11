import { useEffect, useState } from "react";
import { api } from "./api";
import { t, useLocale } from "./i18n";
import { Button, ErrorBox, Field } from "./ui";

type Session = { voice: SpeechSynthesisVoice; rate: number };

export default function ObserverSpeech({
  root,
  revision,
}: {
  root: string;
  revision: number;
}) {
  const language = useLocale() === "en" ? "en" : "zh";
  const supported =
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    "SpeechSynthesisUtterance" in window;
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [voice, setVoice] = useState("");
  const [rate, setRate] = useState(1);
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [played, setPlayed] = useState(0),
    [skipped, setSkipped] = useState(0);
  useEffect(() => {
    if (!supported) return;
    const update = () => {
      const available = window.speechSynthesis.getVoices();
      setVoices(available);
      const local = available.filter((item) => item.localService);
      const recommended =
        local.find((item) => item.lang.startsWith(language)) ?? local[0];
      setVoice((previous) => previous || recommended?.voiceURI || "");
    };
    update();
    window.speechSynthesis.addEventListener("voiceschanged", update);
    return () =>
      window.speechSynthesis.removeEventListener("voiceschanged", update);
  }, [supported, language]);

  useEffect(() => {
    if (!session || !supported) return;
    const synthesis = window.speechSynthesis;
    const controller = new AbortController();
    let stopped = false,
      cursor: string | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined,
      stall: ReturnType<typeof setTimeout> | undefined;
    let pending: any[] = [],
      speaking: SpeechSynthesisUtterance | null = null;
    function fail(reason: unknown) {
      if (stopped) return;
      stopped = true;
      setError(reason);
      setSession(null);
    }
    function next() {
      if (stopped || speaking || !pending.length) return;
      const row = pending.shift();
      const text = row.body.text[language];
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = session!.voice;
      utterance.lang = session!.voice.lang;
      utterance.rate = session!.rate;
      speaking = utterance;
      utterance.onend = () => {
        clearTimeout(stall);
        if (stopped) return;
        speaking = null;
        setPlayed((value) => value + 1);
        next();
      };
      utterance.onerror = (event) =>
        fail(
          t("语音服务返回错误：{code}。已停止播报，原始记录不受影响。", {
            code: event.error,
          }),
        );
      stall = setTimeout(
        () => fail(t("语音服务长时间没有完成播报，请检查系统语音设置。")),
        120000,
      );
      try {
        synthesis.speak(utterance);
      } catch (cause) {
        fail(cause);
      }
    }
    async function poll() {
      try {
        const query = new URLSearchParams({
          configuration_revision: String(revision),
        });
        if (cursor !== undefined) query.set("after", cursor);
        const response = await api<any>(root + "/live?" + query, {
          signal: controller.signal,
        });
        if (stopped) return;
        cursor = response.cursor;
        if (!response.baseline && response.rows.length) {
          // Keep the newest three pending messages. The durable evidence feed
          // and its cursor are separate and never acknowledge a speech drop.
          const dropped = response.omitted + pending.length;
          setSkipped((value) => value + dropped);
          pending = response.rows;
          next();
        }
        timer = setTimeout(poll, 3000);
      } catch (cause) {
        if (!stopped) fail(cause);
      }
    }
    void poll();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
      clearTimeout(stall);
      pending = [];
      synthesis.cancel();
    };
  }, [session, supported, root, revision, language]);

  const selected = voices.find((item) => item.voiceURI === voice);
  return (
    <details className="observer-speech">
      <summary>{t("语音播报（默认关闭）")}</summary>
      <p className="footnote">
        {t(
          "只播报启用后当前规则版本的新小结和预警，不播报历史筛选结果。更改规则或离开页面会停止播报。",
        )}
      </p>
      {!supported ? (
        <p role="status">{t("当前浏览器不支持语音播报。")}</p>
      ) : (
        <>
          <div className="observer-fields">
            <Field label={t("播报语音")}>
              <select
                aria-label={t("播报语音")}
                value={voice}
                disabled={!!session}
                onChange={(event) => setVoice(event.target.value)}
              >
                <option value="">{t("请选择可用语音")}</option>
                {voices.map((item) => (
                  <option key={item.voiceURI} value={item.voiceURI}>
                    {item.name} · {item.lang} ·{" "}
                    {item.localService ? t("本机语音") : t("网络语音")}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("播报语速")}>
              <input
                type="number"
                min={0.5}
                max={2}
                step={0.1}
                value={rate}
                disabled={!!session}
                onChange={(event) => setRate(Number(event.target.value))}
              />
            </Field>
          </div>
          {!voices.length && (
            <p role="status">
              {t(
                "尚无可用语音，请检查浏览器和系统语音包；加载完成后会更新列表。",
              )}
            </p>
          )}
          {selected && !selected.localService && (
            <p className="notice">
              {t(
                "所选语音由网络服务提供。启用后，播报文本可能发送给浏览器的语音服务。",
              )}
            </p>
          )}
          <div className="query-controls">
            <Button
              disabled={
                !session &&
                (!selected || !Number.isFinite(rate) || rate < 0.5 || rate > 2)
              }
              onClick={() => {
                if (session) setSession(null);
                else if (selected) {
                  setError(null);
                  setPlayed(0);
                  setSkipped(0);
                  window.speechSynthesis.resume();
                  setSession({ voice: selected, rate });
                }
              }}
            >
              {session ? t("停止播报") : t("启用播报")}
            </Button>
            <span role="status">
              {session ? t("正在等待或播报新观察") : t("播报已关闭")}
            </span>
          </div>
          <p className="footnote">
            {t(
              "已播报 {played} 条；为跟上进度跳过 {skipped} 条。完整观察记录仍然保留。",
              { played, skipped },
            )}
          </p>
          <ErrorBox error={error} />
        </>
      )}
    </details>
  );
}
