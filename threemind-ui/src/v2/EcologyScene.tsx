import { lazy, Suspense, useMemo, useState } from "react";
import { t } from "./i18n";
import { Field, Loading } from "./ui";
const WorldScene = lazy(() => import("./WorldScene"));
const rotation = [1, 0, 0, 0, 1, 0, 0, 0, 1];

export default function EcologyScene({ protocol, observation, onSelect }: any) {
  const [selected, setSelected] = useState("shared");
  const worlds = observation?.worlds ?? {},
    keys = Object.keys(worlds);
  const key = keys.includes(selected) ? selected : keys[0],
    world = worlds[key];
  const names = (world?.geometries ?? []).map((g: any) => g.name).join("|");
  const model = useMemo(() => {
    const originals = protocol.base.world_protocol.geometries;
    const geoms = names
      .split("|")
      .filter(Boolean)
      .map((name: string) => {
        const rawId = name.replace(/^p[0-9]+_/, "").replace(/^g_/, "");
        const g = originals.find((s: any) => s.id === rawId);
        return g ? { ...g, id: name } : null;
      })
      .filter(Boolean);
    for (const type of ["patches", "hazards"])
      for (const area of protocol.ecology.rules[type]) {
        geoms.push({
          id: "ecology_" + type + "_" + area.id,
          shape: "sphere",
          size: [area.radius],
          body_id: null,
          observer_overlay: true,
          rgba:
            type === "patches"
              ? [0.15, 0.6, 0.42, 0.13]
              : [0.85, 0.22, 0.2, 0.12],
        });
      }
    return { geometries: geoms, sensors: [] };
  }, [protocol, names]);
  const state = useMemo(() => {
    const geometries = (world?.geometries ?? []).map((g: any) => ({
      ...g,
      id: g.name,
    }));
    for (const type of ["patches", "hazards"])
      for (const area of protocol.ecology.rules[type]) {
        geometries.push({
          id: "ecology_" + type + "_" + area.id,
          position: area.position,
          rotation_matrix: rotation,
        });
      }
    return { geometries };
  }, [world, protocol]);
  if (!world) return <p>{t("当前没有活动躯体，意识和历史记录仍保留。")}</p>;
  return (
    <section>
      {keys.length > 1 && (
        <Field label={t("查看栖息环境")}>
          <select value={key} onChange={(e) => setSelected(e.target.value)}>
            {keys.map((k) => (
              <option key={k}>{k}</option>
            ))}
          </select>
        </Field>
      )}
      <Suspense fallback={<Loading />}>
        <WorldScene
          protocol={model}
          observation={state}
          onSelect={(id) => {
            const member = world.members.find((m: any) =>
              id.startsWith(m.prefix),
            );
            if (member) onSelect?.(member.id);
          }}
        />
      </Suspense>
      <p className="footnote">
        {t(
          "绿色区域表示资源采集范围，红色区域表示损伤范围；半透明区域仅用于观察，不是碰撞物体。点击躯体可定位个体。",
        )}
      </p>
    </section>
  );
}
