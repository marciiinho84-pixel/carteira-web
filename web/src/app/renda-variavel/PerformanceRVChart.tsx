"use client";

import { useEffect, useRef } from "react";
import { createChart, LineStyle, type IChartApi, type SeriesMarker, type Time } from "lightweight-charts";

interface Ponto {
  time: string;
  value: number;
}

export interface Marcador {
  time: string;
  tipo: "COMPRA" | "VENDA";
  label: string;
}

interface Props {
  twrRv: Ponto[];
  ibov: Ponto[];
  cdi: Ponto[];
  markers: Marcador[];
}

const BG_CARD = "#FBF6EC";
const BORDER = "#DDD2BF";
const BORDER_SOFT = "#E5DBC8";
const TEXT_MUTED = "#7A7160";
const ACCENT = "#C15F3C";
const WARNING = "#C9862B";
const POSITIVE = "#4A7C59";
const NEGATIVE = "#B4442C";

function LegendItem({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <div style={dashed ? { width: 14, height: 0, borderTop: `1.5px dashed ${color}` } : { width: 14, height: 2, borderRadius: 1, background: color }} />
      <span>{label}</span>
    </div>
  );
}

export default function PerformanceRVChart({ twrRv, ibov, cdi, markers }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;

    const chart: IChartApi = createChart(ref.current, {
      layout: { background: { color: BG_CARD }, textColor: TEXT_MUTED, fontSize: 12 },
      grid: { vertLines: { color: BORDER_SOFT }, horzLines: { color: BORDER_SOFT } },
      rightPriceScale: { borderColor: BORDER, scaleMargins: { top: 0.12, bottom: 0.1 } },
      timeScale: { borderColor: BORDER, timeVisible: true, secondsVisible: false, fixLeftEdge: true, fixRightEdge: true },
      crosshair: { mode: 1 as const },
      handleScroll: true,
      handleScale: true,
      width: ref.current.clientWidth,
      height: 300,
    });

    const pctFmt = {
      type: "custom" as const,
      minMove: 0.01,
      formatter: (v: number) => (v >= 0 ? "+" : "") + v.toFixed(2).replace(".", ",") + "%",
    };

    const twrArea = chart.addAreaSeries({
      lineColor: ACCENT,
      topColor: "rgba(193,95,60,0.18)",
      bottomColor: "rgba(193,95,60,0.00)",
      lineWidth: 2,
      priceFormat: pctFmt,
      title: "TWR RV",
    });
    twrArea.setData(twrRv as { time: Time; value: number }[]);

    const markerColor = (tipo: string) => (tipo === "COMPRA" ? POSITIVE : NEGATIVE);
    const lcMarkers: SeriesMarker<Time>[] = markers.map((m) => ({
      time: m.time as Time,
      position: m.tipo === "COMPRA" ? "belowBar" : "aboveBar",
      color: markerColor(m.tipo),
      shape: m.tipo === "COMPRA" ? "arrowUp" : "arrowDown",
      text: (m.tipo === "COMPRA" ? "C " : "V ") + m.label,
      size: 0.9,
    }));
    if (lcMarkers.length > 0) twrArea.setMarkers(lcMarkers);

    chart.addLineSeries({ color: WARNING, lineWidth: 2, priceFormat: pctFmt, title: "IBOV" }).setData(ibov as { time: Time; value: number }[]);
    chart
      .addLineSeries({ color: TEXT_MUTED, lineWidth: 1, lineStyle: LineStyle.Dashed, priceFormat: pctFmt, title: "CDI" })
      .setData(cdi as { time: Time; value: number }[]);

    // Mostra só os últimos ~3 meses por padrão (não comprime o histórico todo) —
    // o usuário arrasta o gráfico lateralmente (handleScroll) pra ver meses anteriores.
    const JANELA_PADRAO = 60;
    if (twrRv.length > JANELA_PADRAO) {
      chart.timeScale().setVisibleLogicalRange({ from: twrRv.length - JANELA_PADRAO, to: twrRv.length - 1 });
    } else {
      chart.timeScale().fitContent();
    }

    const ro = new ResizeObserver(() => {
      if (!wrapperRef.current) return;
      chart.applyOptions({ width: wrapperRef.current.clientWidth });
    });
    ro.observe(wrapperRef.current!);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [twrRv, ibov, cdi, markers]);

  return (
    <div ref={wrapperRef}>
      <div className="flex items-center gap-4 mb-2 text-xs flex-wrap" style={{ color: "var(--text-muted)" }}>
        <LegendItem color={ACCENT} label="TWR RV" />
        <LegendItem color={WARNING} label="IBOV" />
        <LegendItem color={TEXT_MUTED} label="CDI" dashed />
        <span style={{ marginLeft: "auto" }}>
          <span style={{ color: POSITIVE }}>▲ compra</span>{"  "}
          <span style={{ color: NEGATIVE }}>▼ venda</span>
        </span>
      </div>
      <div ref={ref} />
    </div>
  );
}
