"use client";

import { useEffect, useRef } from "react";
import { ThreeMindGraphDomain, type ThreeMindNodeShape, type ThreeMindViewMode, type ThreeMindVisualStyle } from "./threeMindGraphDomain";
import type { GraphProjectionStore } from "./graphProjectionStore";

export default function ThreeJsonGraphViewport({
  store,
  mode,
  shape,
  style,
  continuousMotion,
}: {
  store: GraphProjectionStore;
  mode: ThreeMindViewMode;
  shape: ThreeMindNodeShape;
  style: ThreeMindVisualStyle;
  continuousMotion: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const domainRef = useRef<ThreeMindGraphDomain | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const domain = new ThreeMindGraphDomain({ canvas, mode, shape, style, continuousMotion });
    domainRef.current = domain;
    const unsubscribe = store.subscribe((change) => domain.apply(change));
    const snapshot = store.snapshot();
    if (snapshot) domain.apply({ type: "replace", graph: snapshot });
    const resize = () => {
      const box = canvas.getBoundingClientRect();
      domain.resize(Math.round(box.width), Math.round(box.height));
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();
    const onKeyDown = (event: KeyboardEvent) => {
      if (!domain.moveCameraBy(event.key)) return;
      event.preventDefault();
    };
    canvas.addEventListener("keydown", onKeyDown);
    return () => {
      canvas.removeEventListener("keydown", onKeyDown);
      observer.disconnect();
      unsubscribe();
      domain.dispose();
      domainRef.current = null;
    };
  }, [continuousMotion, mode, shape, store, style]);

  return <canvas ref={canvasRef} className="graph-viewport graph-viewport-threejson" tabIndex={0} aria-label="Navigable ThreeJSON consciousness graph" />;
}
