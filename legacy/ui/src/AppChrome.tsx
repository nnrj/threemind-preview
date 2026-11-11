import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Locale } from "./i18n";

export type AppPage =
  | "observatory"
  | "management"
  | "detail"
  | "packages"
  | "adapters"
  | "storage"
  | "stimuli"
  | "interpretations"
  | "experiments"
  | "experiment-records"
  | "statistics";

type IconName = "network" | "mind" | "flask" | "system" | "archive" | "settings" | "chevron";

function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };
  if (name === "network") return <svg {...common}><circle cx="5" cy="7" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="18" cy="18" r="2"/><circle cx="6" cy="18" r="2"/><path d="m7 8 10-2M7 17l9-1M6 9v7M18 7v9"/></svg>;
  if (name === "mind") return <svg {...common}><path d="M12 3a5 5 0 0 0-5 5v1.2A3.4 3.4 0 0 0 4.5 12.5 3.5 3.5 0 0 0 8 16h.4A3.7 3.7 0 0 0 12 20a3.7 3.7 0 0 0 3.6-4H16a3.5 3.5 0 0 0 3.5-3.5A3.4 3.4 0 0 0 17 9.2V8a5 5 0 0 0-5-5Z"/><path d="M12 7v10M8 10h4M12 13h4"/></svg>;
  if (name === "flask") return <svg {...common}><path d="M9 3h6M10 3v6l-5.5 9.1A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.9L14 9V3"/><path d="M8 15h8"/></svg>;
  if (name === "system") return <svg {...common}><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h5M8 17h8"/></svg>;
  if (name === "archive") return <svg {...common}><path d="M4 7h16v13H4zM3 4h18v3H3zM10 11h4"/></svg>;
  if (name === "settings") return <svg {...common}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.1 2.1-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.04 1.56v.08h-3v-.08a1.7 1.7 0 0 0-1.04-1.56 1.7 1.7 0 0 0-1.88.34l-.06.06-2.1-2.1.06-.06A1.7 1.7 0 0 0 7.04 15 1.7 1.7 0 0 0 5.48 14H5.4v-3h.08a1.7 1.7 0 0 0 1.56-1.04A1.7 1.7 0 0 0 6.7 8.08l-.06-.06 2.1-2.1.06.06a1.7 1.7 0 0 0 1.88.34 1.7 1.7 0 0 0 1.04-1.56v-.08h3v.08a1.7 1.7 0 0 0 1.04 1.56 1.7 1.7 0 0 0 1.88-.34l.06-.06 2.1 2.1-.06.06a1.7 1.7 0 0 0-.34 1.88A1.7 1.7 0 0 0 20.96 11h.08v3h-.08A1.7 1.7 0 0 0 19.4 15Z"/></svg>;
  return <svg {...common}><path d="m7 10 5 5 5-5"/></svg>;
}

type Labels = {
  observatory: string;
  consciousness: string;
  management: string;
  packages: string;
  archives: string;
  experiments: string;
  stimuli: string;
  interpretations: string;
  system: string;
  adapters: string;
  providers: string;
  storage: string;
  settings: string;
  language: string;
  subtitle: string;
};

function labels(locale: Locale): Labels {
  return locale === "en" ? {
    observatory: "Observatory", consciousness: "Consciousness", management: "Consciousness manager", packages: "Model packages", archives: "Snapshots & portraits",
    experiments: "Experiments", stimuli: "Stimulus records", interpretations: "Readout & interpretations", system: "System", adapters: "Adapter management", providers: "AI providers", storage: "Storage & persistence",
    settings: "Settings", language: "Language", subtitle: "CONTINUOUS ASSOCIATIVE NETWORK",
  } : {
    observatory: "意识图像", consciousness: "意识", management: "意识管理", packages: "模型包", archives: "快照与遗照",
    experiments: "实验", stimuli: "刺激记录", interpretations: "读出与解读", system: "系统", adapters: "适配器管理", providers: "AI 供应商", storage: "存储与持久化",
    settings: "设置", language: "语言", subtitle: "连续可塑联想网络",
  };
}

function Menu({
  label,
  icon,
  active,
  children,
}: {
  label: string;
  icon: IconName;
  active: boolean;
  children: (close: () => void) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const closeOnOutside = (event: MouseEvent) => { if (!rootRef.current?.contains(event.target as Node)) setOpen(false); };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("pointerdown", closeOnOutside); document.removeEventListener("keydown", closeOnEscape); };
  }, []);
  return <div className={`app-menu ${active ? "is-active" : ""} ${open ? "is-open" : ""}`} ref={rootRef}>
    <button className="app-menu-trigger" type="button" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
      <Icon name={icon} size={15}/><span>{label}</span><Icon name="chevron" size={13}/>
    </button>
    {open && <div className="app-menu-popover" role="menu">{children(() => setOpen(false))}</div>}
  </div>;
}

function MenuAction({ icon, title, detail, onClick }: { icon: IconName; title: string; detail: string; onClick: () => void }) {
  return <button type="button" className="app-menu-action" role="menuitem" onClick={onClick}>
    <span className="app-menu-action-icon"><Icon name={icon}/></span><span><strong>{title}</strong><small>{detail}</small></span>
  </button>;
}

export function AppChrome({
  locale,
  onLocaleChange,
  activePage,
  onNavigate,
  onOpenArchives,
  onOpenSettings,
}: {
  locale: Locale;
  onLocaleChange: (value: Locale) => void;
  activePage: AppPage;
  onNavigate: (page: Exclude<AppPage, "detail">) => void;
  onOpenArchives: () => void;
  onOpenSettings: (category?: string) => void;
}) {
  const text = labels(locale);
  const consciousnessActive = ["management", "detail", "packages"].includes(activePage);
  const experimentsActive = ["experiments", "experiment-records", "stimuli", "interpretations"].includes(activePage);
  const systemActive = activePage === "adapters" || activePage === "storage";
  return <header className="app-topbar">
    <button type="button" className="app-brand" onClick={() => onNavigate("observatory")} aria-label="ThreeMind Observatory">
      <span className="app-brand-mark"><Icon name="network" size={19}/></span>
      <span><strong>ThreeMind</strong><small>{text.subtitle}</small></span>
    </button>
    <nav className="app-primary-nav" aria-label={locale === "en" ? "Main navigation" : "主导航"}>
      <button className={`app-nav-link ${activePage === "observatory" ? "is-active" : ""}`} type="button" onClick={() => onNavigate("observatory")}><Icon name="network" size={15}/><span>{text.observatory}</span></button>
      <Menu label={text.consciousness} icon="mind" active={consciousnessActive}>{(close) => <>
        <MenuAction icon="mind" title={text.management} detail={locale === "en" ? "Instances, lineage, snapshots and records" : "实例、谱系、快照与记录"} onClick={() => { close(); onNavigate("management"); }}/>
        <MenuAction icon="archive" title={text.packages} detail={locale === "en" ? "Portable .tmind consciousness packages" : "可导入、导出的 .tmind 意识模型包"} onClick={() => { close(); onNavigate("packages"); }}/>
        <MenuAction icon="archive" title={text.archives} detail={locale === "en" ? "Browse live snapshots and portraits" : "浏览当前意识的快照与遗照"} onClick={() => { close(); onOpenArchives(); }}/>
      </>}</Menu>
      <Menu label={text.experiments} icon="flask" active={experimentsActive}>{(close) => <>
        <MenuAction icon="flask" title={locale === "en" ? "AI experiment & debugging" : "AI 实验与调试"} detail={locale === "en" ? "Manual protocols, validated AI plans and evidence" : "人工协议、受限 AI 计划与实验报告"} onClick={() => { close(); onNavigate("experiments"); }}/>
        <MenuAction icon="archive" title={locale === "en" ? "Experiment records" : "实验记录"} detail={locale === "en" ? "Browse persistent runs, evidence and reports" : "查看持久化的实验运行、证据与报告"} onClick={() => { close(); onNavigate("experiment-records"); }}/>
        <MenuAction icon="network" title={text.stimuli} detail={locale === "en" ? "Chronological sensory carriers" : "按时间查看进入意识的刺激"} onClick={() => { close(); onNavigate("stimuli"); }}/>
        <MenuAction icon="mind" title={text.interpretations} detail={locale === "en" ? "Passive readout and interpretation records" : "被动读出与解读记录"} onClick={() => { close(); onNavigate("interpretations"); }}/>
      </>}</Menu>
      <button className={`app-nav-link ${activePage === "statistics" ? "is-active" : ""}`} type="button" onClick={() => onNavigate("statistics")}><Icon name="archive" size={15}/><span>{locale === "en" ? "Statistics & Evidence" : "统计与证据"}</span></button>
      <Menu label={text.system} icon="system" active={systemActive}>{(close) => <>
        <MenuAction icon="system" title={text.adapters} detail={locale === "en" ? "Attach, configure and inspect sensory/output adapters" : "挂载、配置和检查感官／输出适配器"} onClick={() => { close(); onNavigate("adapters"); }}/>
        <MenuAction icon="flask" title={text.providers} detail={locale === "en" ? "Providers for environment, interpretation and research" : "环境、解读与研究所用 AI 供应商"} onClick={() => { close(); onOpenSettings("ai"); }}/>
        <MenuAction icon="archive" title={text.storage} detail={locale === "en" ? "Scan, classify and safely clean local artifacts" : "扫描、分类并安全清理本地工件"} onClick={() => { close(); onNavigate("storage"); }}/>
      </>}</Menu>
    </nav>
    <div className="app-topbar-tools">
      <label className="app-locale-control"><span className="sr-only">{text.language}</span><select aria-label={text.language} value={locale} onChange={(event) => onLocaleChange(event.target.value as Locale)}><option value="zh-CN">简体中文</option><option value="en">English</option></select></label>
      <button type="button" className="app-settings-button" onClick={() => onOpenSettings("visualization")} aria-label={text.settings}><Icon name="settings" size={17}/><span>{text.settings}</span></button>
    </div>
  </header>;
}
