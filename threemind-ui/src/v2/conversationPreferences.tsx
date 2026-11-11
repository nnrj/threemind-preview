import { t } from "./i18n";
import {
  updatePreferences,
  usePreferences,
  type Preferences,
} from "./preferences";

export default function ConversationPreferences({
  interaction = false,
  chat = false,
}: {
  interaction?: boolean;
  chat?: boolean;
}) {
  const p = usePreferences();
  const options: [keyof Preferences, string, string][] = [
    [
      "showEnvironmentStimuli",
      "显示环境刺激",
      "包括环境、遥测、实时设备及 AI 来源的输入接收记录。",
    ],
    [
      "showTriggeringStimuli",
      "保留关联读出的环境刺激",
      "读出可见且明确引用该输入编号时，保留该刺激；不根据相近时间猜测。",
    ],
    [
      "showBackgroundReadouts",
      "显示背景读出",
      "包括环境响应与未关联特定输入的被动结构观察。",
    ],
  ];
  if (interaction)
    options.push([
      "enterSend",
      "Enter 发送，Shift＋Enter 换行",
      "用于文本载体输入框；中文输入法确认候选时不会发送。",
    ]);
  return (
    <div className="conversation-preferences">
      {options
        .filter(([key]) => !chat || key !== "showBackgroundReadouts")
        .map(([key, label, detail]) => (
          <label className="preference-option" key={key}>
            <input
              type="checkbox"
              checked={p[key] === true}
              onChange={(e) => updatePreferences({ [key]: e.target.checked })}
            />
            <span>
              <strong>{t(label)}</strong>
              <small>{t(detail)}</small>
            </span>
          </label>
        ))}
      <p className="footnote">
        {t(
          "保存在当前浏览器。仅影响显示和交互，不修改意识参数、原始刺激、读出采集或证据导出。",
        )}
      </p>
    </div>
  );
}
