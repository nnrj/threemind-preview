import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { t } from "./i18n";
import { usePreferences } from "./preferences";
import { ErrorBox, Field, Loading } from "./ui";
import WorldScene from "./WorldScene";
import { worldLabels } from "./WorldEditor";

function Pixels({ sensor, values }: { sensor: any; values: number[] }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!canvas.current || values.length !== sensor.width * sensor.height * 3)
      return;
    const data = new Uint8ClampedArray(sensor.width * sensor.height * 4);
    for (let i = 0; i < values.length / 3; i++) {
      data[i * 4] = values[i * 3];
      data[i * 4 + 1] = values[i * 3 + 1];
      data[i * 4 + 2] = values[i * 3 + 2];
      data[i * 4 + 3] = 255;
    }
    canvas.current
      .getContext("2d")
      ?.putImageData(new ImageData(data, sensor.width, sensor.height), 0, 0);
  }, [sensor, values]);
  return (
    <figure className="world-eye">
      <canvas
        ref={canvas}
        width={sensor.width}
        height={sensor.height}
        aria-label={sensor.label || sensor.id}
      />
      <figcaption>
        {sensor.label || sensor.id} · {sensor.width} × {sensor.height}
      </figcaption>
    </figure>
  );
}

export default function WorldObservation({
  base,
  checkpoint,
}: {
  base: string;
  checkpoint: string;
}) {
  const prefs = usePreferences(),
    [follow, setFollow] = useState(false);
  const observation = useQuery({
    queryKey: ["world-observation", base, follow ? "latest" : checkpoint],
    queryFn: () =>
      api<any>(
        `${base}/world/observation${follow ? "" : `?checkpoint_id=${checkpoint}`}`,
      ),
    refetchInterval: follow ? prefs.pollMs : false,
    gcTime: 0,
  });
  const data = observation.data;
  const protocol = useQuery({
    queryKey: ["world-observation-protocol", base, data?.world_hash],
    queryFn: () => api<any>(`${base}/world/protocol?checkpoint_id=${data.id}`),
    enabled: !!data,
    staleTime: Infinity,
  });
  const spec = protocol.data?.protocol;
  return (
    <section className="world-observation" aria-label={t("虚拟躯体与世界观测")}>
      <div className="panel-heading">
        <h3>{t("虚拟躯体与世界观测")}</h3>
        <Field label={t("跟随最新检查点")}>
          <input
            type="checkbox"
            checked={follow}
            onChange={(e) => setFollow(e.target.checked)}
          />
        </Field>
      </div>
      <ErrorBox error={observation.error ?? protocol.error} />
      {data && spec ? (
        <>
          <p className="notice">
            {t(
              "展示已提交的物理状态快照。物理步进先于其感官事件的递送，因此两种时间可能不同；这里不插值生成未记录的运动。",
            )}
          </p>
          <div className="world-clock">
            <span>
              {t("意识时间")} {data.time_us} μs
            </span>
            <span>
              {t("物理累计时间")} {data.observation.physical_time_us} μs
            </span>
            <span>
              {t("感官递送时间")} {data.observation.delivery_time_us ?? "—"} μs
            </span>
            <span>r{data.revision}</span>
          </div>
          <WorldScene protocol={spec} observation={data.observation} />
          {data.observation.stimulus_unit && (
            <details>
              <summary>{t("共同观测刺激组")}</summary>
              <pre>
                {JSON.stringify(data.observation.stimulus_unit, null, 2)}
              </pre>
            </details>
          )}
          <div className="world-eye-list">
            {data.measurements
              .filter((m: any) => m.kind === "camera_rgb")
              .map((m: any) => (
                <Pixels
                  key={m.id}
                  sensor={spec.sensors.find((s: any) => s.id === m.id)}
                  values={m.values}
                />
              ))}
          </div>
          <details>
            <summary>{t("原始感官与执行器量")}</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("感官端口")}</th>
                    <th>{t("类型")}</th>
                    <th>{t("原始数值")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.measurements
                    .filter((m: any) => m.kind !== "camera_rgb")
                    .map((m: any) => (
                      <tr key={m.id}>
                        <td>
                          {m.id} · {m.port}
                        </td>
                        <td>{t(worldLabels[m.kind] ?? m.kind)}</td>
                        <td>
                          {m.values.join(", ")} {m.unit ?? ""}
                          {m.encoded && (
                            <details>
                              <summary>{t("匿名通道与编码值")}</summary>
                              <p>
                                {m.coordinate_frame} · {t("尺度")}{" "}
                                {m.scale ?? "—"}
                              </p>
                              <pre>{JSON.stringify(m.encoded, null, 2)}</pre>
                            </details>
                          )}
                        </td>
                      </tr>
                    ))}
                  {data.controls.map((m: any) => (
                    <tr key={`motor:${m.id}`}>
                      <td>
                        {m.id} · {m.port}
                      </td>
                      <td>{t("执行器")}</td>
                      <td>{m.control}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <a
              className="text-link"
              download={`world-observation-r${data.revision}.json`}
              href={`/api/v2${base}/world/observation?checkpoint_id=${data.id}`}
            >
              {t("导出当前世界观测")}
            </a>
          </details>
        </>
      ) : (
        <Loading />
      )}
    </section>
  );
}
