import { t, locale } from "./i18n";
import { lazy, Suspense, useEffect } from "react";
import { SlidersHorizontal, Monitor, Cpu, BookOpen } from "lucide-react";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import {
  usePreferences,
  updatePreferences,
  effectivePreferences,
  type Preferences,
} from "./preferences";
import { PageTitle, Field, Loading, useWorkspace, Workspace } from "./ui";
import { AccessBoundary, useAccess } from "./access";
import { SystemDefaults, ConfigurationTemplates } from "./systemConfiguration";
import AccountSettings from "./accountSettings";
import { HostStorage } from "./DataManagement";

import ConversationPreferences from "./conversationPreferences";
import { CapturePreferences } from "./stateCaptures";
import LanguagePicker from "./LanguagePicker";
const DeviceCapabilities = lazy(() => import("./adapterCatalogue"));
const AIProviders = lazy(() => import("./aiProviders"));
const Notifications = lazy(() => import("./notificationSettings"));
const HostMaintenance = lazy(() => import("./hostMaintenance"));
const ExecutionResources = lazy(() => import("./executionResources"));
const ExternalTools = lazy(() => import("./externalTools"));

const options = [
  ["auto", "自动", "根据浏览器提供的设备信息选择显示预算。"],
  ["light", "轻量", "较少显示节点、较低像素密度，适合长时间观察。"],
  ["standard", "标准", "10,000 个可见节点，兼顾清晰度与交互。"],
  ["high", "高性能", "更高显示上限和帧率。任何设备均可手动选择。"],
  ["custom", "自定义", "独立调整显示预算、帧率与更新频率。"],
] as const;
export default function Settings() {
  const workspace = useWorkspace();
  return (
    <Workspace.Provider value={{ ...workspace, project: null }}>
      <SettingsContent />
    </Workspace.Provider>
  );
}
function SettingsContent() {
  const allowed = useAccess();
  const [query, setQuery] = useSearchParams();
  const section = [
    "display",
    "defaults",
    "devices",
    "providers",
    "notifications",
    "execution",
    "storage",
    "tools",
    "templates",
    "account",
  ].includes(query.get("section") ?? "")
    ? query.get("section")!
    : "display";
  const setSection = (value: string) => setQuery({ section: value });

  const p = usePreferences(),
    effective = effectivePreferences(p);
  useEffect(() => {
    document.documentElement.dataset.theme = p.theme;
  }, [p.theme]);
  return (
    <>
      <PageTitle
        eyebrow="WORKSPACE SETTINGS"
        title={t("系统设置")}
        description={t(
          "个人显示偏好、宿主服务与新建意识默认值分别管理。项目预设在研究项目中查看，已有意识在工作台调整。",
        )}
      />
      <div className="tabs page-tabs settings-tabs" aria-label={t("设置分类")}>
        <button
          className={section === "display" ? "active" : ""}
          onClick={() => setSection("display")}
        >
          {t("显示与交互")}
        </button>
        <button
          className={section === "defaults" ? "active" : ""}
          onClick={() => setSection("defaults")}
        >
          {t("新建意识默认值")}
        </button>
        <button
          className={section === "devices" ? "active" : ""}
          onClick={() => setSection("devices")}
        >
          {t("设备与适配器")}
        </button>
        <button
          className={section === "providers" ? "active" : ""}
          onClick={() => setSection("providers")}
        >
          {t("AI 供应商")}
        </button>
        <button
          className={section === "notifications" ? "active" : ""}
          onClick={() => setSection("notifications")}
        >
          {t("通知与邮件")}
        </button>
        {allowed("execution.read") && (
          <button
            className={section === "execution" ? "active" : ""}
            onClick={() => setSection("execution")}
          >
            {t("执行队列与额度")}
          </button>
        )}
        <button
          className={section === "storage" ? "active" : ""}
          onClick={() => setSection("storage")}
        >
          {t("存储与迁移")}
        </button>
        <button
          className={section === "tools" ? "active" : ""}
          onClick={() => setSection("tools")}
        >
          {t("计算工具与 Agent 接口")}
        </button>
        <button
          className={section === "templates" ? "active" : ""}
          onClick={() => setSection("templates")}
        >
          {t("配置模板")}
        </button>
        <button
          className={section === "account" ? "active" : ""}
          onClick={() => setSection("account")}
        >
          {t("我的账号")}
        </button>
      </div>
      {section === "account" ? (
        <AccountSettings />
      ) : section === "templates" ? (
        <AccessBoundary action="system.read">
          <ConfigurationTemplates />
        </AccessBoundary>
      ) : section === "tools" ? (
        <AccessBoundary action="tools.read">
          <Suspense fallback={<Loading />}>
            <ExternalTools />
          </Suspense>
        </AccessBoundary>
      ) : section === "storage" ? (
        <AccessBoundary action="system.read">
          <Suspense fallback={<Loading />}>
            <HostStorage />
          </Suspense>
        </AccessBoundary>
      ) : section === "execution" ? (
        <AccessBoundary action="execution.read">
          <Suspense fallback={<Loading />}>
            <ExecutionResources manage />
            <HostMaintenance />
          </Suspense>
        </AccessBoundary>
      ) : section === "notifications" ? (
        <Suspense fallback={<Loading />}>
          <Notifications />
        </Suspense>
      ) : section === "providers" ? (
        <AccessBoundary action="services.read">
          <Suspense fallback={<Loading />}>
            <AIProviders />
          </Suspense>
        </AccessBoundary>
      ) : section === "devices" ? (
        <Suspense fallback={<Loading />}>
          <DeviceCapabilities />
        </Suspense>
      ) : section === "defaults" ? (
        <AccessBoundary action="system.read">
          <SystemDefaults />
        </AccessBoundary>
      ) : (
        <>
          <p className="notice">
            {t(
              "这些显示偏好仅保存在本浏览器，并按登录账号分别保存。不会改变意识动力学。",
            )}
          </p>
          <section className="panel settings-panel">
            <LanguagePicker />
          </section>
          <section className="panel settings-panel">
            <div className="panel-heading">
              <div>
                <h2>{t("显示性能档位")}</h2>
                <p>{t("手动档位始终可选，不会因硬件配置被锁定或静默降低。")}</p>
              </div>
              <Monitor size={23} />
            </div>
            <div className="preset-grid">
              {options.map(([value, title, description]) => (
                <button
                  key={value}
                  className={`preset-card ${p.preset === value ? "selected" : ""}`}
                  onClick={() => updatePreferences({ preset: value })}
                >
                  <span className="radio-dot" />
                  <strong>{t(title)}</strong>
                  <p>{t(description)}</p>
                </button>
              ))}
            </div>
            <div className="effective-budget">
              <span>{t("当前显示预算")}</span>
              <strong>
                {effective.nodes.toLocaleString(locale())}
                {t(" 节点")}
              </strong>
              <strong>
                {effective.edges.toLocaleString(locale())}
                {t(" 连接")}
              </strong>
              <strong>
                {effective.fps}
                {t(" FPS 上限")}
              </strong>
              <strong>
                {effective.dpr}
                {t("× 像素密度")}
              </strong>
              <strong>
                {effective.pollMs}
                {t(" ms 查询间隔")}
              </strong>
            </div>
            {p.preset === "custom" && (
              <div className="form-grid">
                <Field label={t("显示连接上限")}>
                  <input
                    aria-label={t("显示连接上限")}
                    type="number"
                    min="0"
                    max="1000000"
                    value={p.edges}
                    onChange={(e) =>
                      updatePreferences({ edges: Number(e.target.value) })
                    }
                  />
                </Field>
                <Field label={t("持续布局更新上限（次 / 秒）")}>
                  <input
                    aria-label={t("持续布局更新上限（次 / 秒）")}
                    type="number"
                    min="1"
                    max="60"
                    value={p.layoutFps}
                    onChange={(e) =>
                      updatePreferences({ layoutFps: Number(e.target.value) })
                    }
                  />
                </Field>
                <Field label={t("显示节点上限")}>
                  <input
                    type="number"
                    min="1"
                    max="100000"
                    value={p.nodes}
                    onChange={(e) =>
                      updatePreferences({
                        nodes: Math.max(
                          1,
                          Math.min(100000, Number(e.target.value)),
                        ),
                      })
                    }
                  />
                </Field>
                <Field label={t("帧率上限")}>
                  <input
                    type="number"
                    min="1"
                    max="144"
                    value={p.fps}
                    onChange={(e) =>
                      updatePreferences({
                        fps: Math.max(1, Math.min(144, Number(e.target.value))),
                      })
                    }
                  />
                </Field>
                <Field label={t("像素密度上限")}>
                  <input
                    type="number"
                    min=".5"
                    max="3"
                    step=".25"
                    value={p.dpr}
                    onChange={(e) =>
                      updatePreferences({
                        dpr: Math.max(0.5, Math.min(3, Number(e.target.value))),
                      })
                    }
                  />
                </Field>
                <Field label={t("查询间隔（毫秒）")}>
                  <input
                    type="number"
                    min="100"
                    max="10000"
                    step="100"
                    value={p.pollMs}
                    onChange={(e) =>
                      updatePreferences({
                        pollMs: Math.max(
                          100,
                          Math.min(10000, Number(e.target.value)),
                        ),
                      })
                    }
                  />
                </Field>
              </div>
            )}
            <p className="footnote">
              {t(
                "显示上限只影响画面。完整模型和研究证据仍按实验协议保存，模型导出也不受可见节点数影响。",
              )}
            </p>
          </section>
          <section className="panel settings-panel">
            <div className="panel-heading">
              <h2>{t("观察方式")}</h2>
            </div>
            <div className="form-grid">
              <Field label={t("默认维度")}>
                <select
                  value={p.mode}
                  onChange={(e) =>
                    updatePreferences({ mode: e.target.value as "2d" | "3d" })
                  }
                >
                  <option value="3d">{t("3D 空间观察")}</option>
                  <option value="2d">{t("2D 平面观察")}</option>
                </select>
              </Field>
              <Field label={t("节点形状")}>
                <select
                  value={p.shape}
                  onChange={(e) =>
                    updatePreferences({
                      shape: e.target.value as Preferences["shape"],
                    })
                  }
                >
                  <option value="glow">{t("光点")}</option>
                  <option value="circle">{t("圆点")}</option>
                  <option value="square">{t("方点")}</option>
                  <option value="sphere">{t("球体")}</option>
                  <option value="cube">{t("立方体")}</option>
                </select>
              </Field>
              <Field label={t("界面主题")}>
                <select
                  value={p.theme}
                  onChange={(e) =>
                    updatePreferences({
                      theme: e.target.value as "light" | "dark",
                    })
                  }
                >
                  <option value="light">{t("浅色 · 纸面")}</option>
                  <option value="dark">{t("深色 · 夜间")}</option>
                </select>
              </Field>
              <Field label={t("图形风格")}>
                <select
                  aria-label={t("图形风格")}
                  value={p.visualStyle}
                  onChange={(e) =>
                    updatePreferences({
                      visualStyle: e.target.value as Preferences["visualStyle"],
                    })
                  }
                >
                  <option value="organic">{t("柔和 · 有机")}</option>
                  <option value="minimal">{t("清晰 · 简洁")}</option>
                </select>
              </Field>
              <Field label={t("图中标签")}>
                <select
                  aria-label={t("图中标签")}
                  value={p.graphLabels}
                  onChange={(e) =>
                    updatePreferences({
                      graphLabels: e.target.value as Preferences["graphLabels"],
                    })
                  }
                >
                  <option value="none">{t("不显示标签")}</option>
                  <option value="ids">{t("匿名节点编号")}</option>
                  <option value="external">{t("外部字符注记与编号")}</option>
                </select>
              </Field>
            </div>
            <label className="check">
              <input
                type="checkbox"
                checked={p.continuousMotion}
                onChange={(e) =>
                  updatePreferences({ continuousMotion: e.target.checked })
                }
              />
              {t("持续整理观察布局")}
            </label>
            <p className="footnote">
              {t(
                "布局力只作用于画面，不创造连接；“空间基底”中的实际因果坐标保持固定。字符注记来自已递送载体的感官通道，同一通道可能对应多个字符，不代表内核理解了字符意义。",
              )}
            </p>
            <details className="ai-advanced">
              <summary>{t("高级显示与诊断")}</summary>
              <div className="form-grid">
                <Field label={t("可见标签上限")}>
                  <input
                    aria-label={t("可见标签上限")}
                    type="number"
                    min="1"
                    max="500"
                    value={p.maxLabels}
                    onChange={(e) =>
                      updatePreferences({ maxLabels: Number(e.target.value) })
                    }
                  />
                </Field>
                <Field label={t("标签字号")}>
                  <input
                    aria-label={t("标签字号")}
                    type="number"
                    min="9"
                    max="24"
                    value={p.labelFont}
                    onChange={(e) =>
                      updatePreferences({ labelFont: Number(e.target.value) })
                    }
                  />
                </Field>
                <Field label={t("节点显示大小")}>
                  <input
                    aria-label={t("节点显示大小")}
                    type="number"
                    min=".25"
                    max="4"
                    step="any"
                    value={p.nodeScale}
                    onChange={(e) =>
                      updatePreferences({ nodeScale: Number(e.target.value) })
                    }
                  />
                </Field>
                <Field label={t("连线不透明度")}>
                  <input
                    aria-label={t("连线不透明度")}
                    type="number"
                    min="0"
                    max="1"
                    step="any"
                    value={p.edgeOpacity}
                    onChange={(e) =>
                      updatePreferences({ edgeOpacity: Number(e.target.value) })
                    }
                  />
                </Field>
              </div>
              <label className="check">
                <input
                  type="checkbox"
                  checked={p.showGraphStats}
                  onChange={(e) =>
                    updatePreferences({ showGraphStats: e.target.checked })
                  }
                />
                {t("显示图形性能诊断")}
              </label>
            </details>
          </section>
          <section className="panel settings-panel">
            <div className="panel-heading">
              <h2>{t("刺激与读出显示")}</h2>
            </div>
            <ConversationPreferences interaction />
          </section>
          <section className="panel settings-panel" id="capture-preferences">
            <div className="panel-heading">
              <h2>{t("存档与命名")}</h2>
            </div>
            <CapturePreferences />
          </section>
          <section className="settings-explainer">
            <Cpu size={23} />
            <div>
              <h3>{t("模拟速度属于运行协议")}</h3>
              <p>
                {t(
                  "实时、指定倍率、尽速训练会控制 Runtime 的调度。显示档位不会修改时间步长、传播延迟、可塑性或科学采集精度。",
                )}
              </p>
              <Link className="text-link" to="/docs?doc=docs/zh/v2-kernel.md">
                <BookOpen size={15} />
                {t("了解时间与内核")}
              </Link>
            </div>
          </section>
        </>
      )}
    </>
  );
}
