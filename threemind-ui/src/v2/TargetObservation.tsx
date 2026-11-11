import { useState } from "react";
import { Button } from "./ui";
import { t } from "./i18n";
import ResponseObservation from "./ResponseObservation";
import TargetStability from "./TargetStability";

export default function TargetObservation(props: {
  base: string;
  recordId: number;
}) {
  const [stable, setStable] = useState(false);
  return (
    <section className="target-observation">
      <div className="query-controls" role="group" aria-label={t("读出方式")}>
        <Button aria-pressed={!stable} onClick={() => setStable(false)}>
          {t("响应读出")}
        </Button>
        <Button aria-pressed={stable} onClick={() => setStable(true)}>
          {t("持续稳定（旧版）")}
        </Button>
      </div>
      {stable ? (
        <TargetStability {...props} />
      ) : (
        <ResponseObservation {...props} />
      )}
    </section>
  );
}
