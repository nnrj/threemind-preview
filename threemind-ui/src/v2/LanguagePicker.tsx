import { usePreferences, updatePreferences } from "./preferences";
import { t } from "./i18n";

export default function LanguagePicker({
  compact = false,
}: {
  compact?: boolean;
}) {
  const p = usePreferences();
  return (
    <label
      className={compact ? "language-picker compact" : "field language-picker"}
    >
      {!compact && <span>{t("界面语言")}</span>}
      <select
        aria-label={t(compact ? "切换界面语言" : "界面语言")}
        value={p.locale}
        onChange={(e) =>
          updatePreferences({ locale: e.target.value as typeof p.locale })
        }
      >
        <option value="zh-CN">{compact ? t("中文") : t("简体中文")}</option>
        <option value="en">{compact ? "EN" : "English"}</option>
        <option value="auto">{compact ? "Auto" : t("跟随浏览器")}</option>
      </select>
      {!compact && (
        <small>
          {t(
            "语言保存在当前设备，不翻译或改写项目名称、笔记、刺激、协议或原始证据。",
          )}
        </small>
      )}
    </label>
  );
}
