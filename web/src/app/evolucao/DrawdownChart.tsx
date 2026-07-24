"use client";

import { useEffect, useRef } from "react";
import { createChart, type IChartApi, type Time } from "lightweight-charts";

interface Ponto {
  time: string;
  value: number;
}

interface Props {
  drawdown: Ponto[];
}

const BG_CARD = "#FBF6EC";
const BORDER = "#DDD2BF";
const BORDER_SOFT = "#E5DBC8";
const TEXT_MUTED = "#7A7160";
const NEGATIVE = "#B4442C";

export default function DrawdownChart({ drawdown }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;

    const chart: IChartApi = createChart(ref.current, {
      layout: { background: { color: BG_CARD }, textColor: TEXT_MUTED, fontSize: 11 },
      grid: { vertLines: { color: BORDER_SOFT }, horzLines: { color: BORDER_SOFT } },
      rightPriceScale: { borderColor: BORDER, scaleMargins: { top: 0.1, bottom: 0.05 } },
      timeScale: { borderColor: BORDER, timeVisible: true, secondsVisible: false },
      crosshair: { mode: 1 as const },
      handleScroll: true,
      handleScale: true,
      width: ref.current.clientWidth,
      height: 180,
    });

    const pctFmt = {
      type: "custom" as const,
      minMove: 0.01,
      formatter: (v: number) => (v >= 0 ? "+" : "") + v.toFixed(2).replace(".", ",") + "%",
    };

    const series = chart.addBaselineSeries({
      baseValue: { type: "price", price: 0 },
      topLineColor: "rgba(74,124,89,0.6)",
      topFillColor1: "rgba(74,124,89,0.20)",
      topFillColor2: "rgba(74,124,89,0.02)",
      bottomLineColor: NEGATIVE,
      bottomFillColor1: "rgba(180,68,44,0.05)",
      bottomFillColor2: "rgba(180,68,44,0.28)",
      lineWidth: 2,
      priceFormat: pctFmt,
    });
    series.setData(drawdown as { time: Time; value: number }[]);

    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (!wrapperRef.current) return;
      chart.applyOptions({ width: wrapperRef.current.clientWidth });
    });
    ro.observe(wrapperRef.current!);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [drawdown]);

  return (
    <div ref={wrapperRef}>
      <div ref={ref} />
    </div>
  );
}
