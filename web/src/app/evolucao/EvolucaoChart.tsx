"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";

interface Ponto {
  time: string;
  value: number;
}

interface Props {
  total: Ponto[];
  funcef: Ponto[];
  gerida: Ponto[];
  twrGerida: Ponto[];
  cdi: Ponto[];
  ibov: Ponto[];
}

const BG_CARD = "#FBF6EC";
const BORDER = "#DDD2BF";
const BORDER_SOFT = "#E5DBC8";
const TEXT_MUTED = "#7A7160";
const ACCENT = "#C15F3C";
const WARNING = "#C9862B";
const PURPLE = "#6C63C4";

function LegendItem({ color, label, dashed, dotted }: { color: string; label: string; dashed?: boolean; dotted?: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <div
        style={
          dashed
            ? { width: 14, height: 0, borderTop: `1.5px dashed ${color}` }
            : dotted
            ? { width: 14, height: 0, borderTop: `1.5px dotted ${color}` }
            : { width: 14, height: 2, borderRadius: 1, background: color }
        }
      />
      <span>{label}</span>
    </div>
  );
}

export default function EvolucaoChart({ total, funcef, gerida, twrGerida, cdi, ibov }: Props) {
  const topRef = useRef<HTMLDivElement>(null);
  const botRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!topRef.current || !botRef.current) return;

    const SHARED_OPTS = {
      layout: { background: { color: BG_CARD }, textColor: TEXT_MUTED, fontSize: 11 },
      grid: {
        vertLines: { color: BORDER_SOFT },
        horzLines: { color: BORDER_SOFT },
      },
      timeScale: { borderColor: BORDER, timeVisible: true, secondsVisible: false },
      crosshair: { mode: 1 as const },
      handleScroll: true,
      handleScale: true,
    };

    const chartTop: IChartApi = createChart(topRef.current, {
      ...SHARED_OPTS,
      width: topRef.current.clientWidth,
      height: 280,
      rightPriceScale: { borderColor: BORDER, scaleMargins: { top: 0.08, bottom: 0.05 } },
      leftPriceScale: { visible: true, borderColor: BORDER },
    });

    const totalFmt = {
      type: "custom" as const,
      minMove: 1,
      formatter: (v: number) => "R$ " + (v / 1_000_000).toFixed(2).replace(".", ",") + "M",
    };
    const geridaFmt = {
      type: "custom" as const,
      minMove: 1,
      formatter: (v: number) => "R$ " + (v / 1000).toFixed(0) + "k",
    };

    const totalArea = chartTop.addAreaSeries({
      lineColor: ACCENT,
      topColor: "rgba(193,95,60,0.20)",
      bottomColor: "rgba(193,95,60,0.00)",
      lineWidth: 2,
      priceFormat: totalFmt,
      title: "Total",
      priceScaleId: "right",
    });
    totalArea.setData(total as { time: Time; value: number }[]);

    chartTop
      .addLineSeries({
        color: WARNING, lineWidth: 1, lineStyle: LineStyle.Dashed, priceFormat: totalFmt,
        title: "FUNCEF", priceScaleId: "right",
      })
      .setData(funcef as { time: Time; value: number }[]);

    chartTop
      .addLineSeries({
        color: PURPLE, lineWidth: 1, lineStyle: LineStyle.Dotted, priceFormat: geridaFmt,
        title: "Gerida", priceScaleId: "left",
      })
      .setData(gerida as { time: Time; value: number }[]);

    const chartBot: IChartApi = createChart(botRef.current, {
      ...SHARED_OPTS,
      width: botRef.current.clientWidth,
      height: 200,
      rightPriceScale: { borderColor: BORDER, scaleMargins: { top: 0.16, bottom: 0.05 } },
    });

    const pctFmt = {
      type: "custom" as const,
      minMove: 0.01,
      formatter: (v: number) => (v >= 0 ? "+" : "") + v.toFixed(2).replace(".", ",") + "%",
    };

    const twrLine = chartBot.addLineSeries({ color: ACCENT, lineWidth: 2, priceFormat: pctFmt, title: "TWR Gerida" });
    twrLine.setData(twrGerida as { time: Time; value: number }[]);

    chartBot
      .addLineSeries({ color: TEXT_MUTED, lineWidth: 1, lineStyle: LineStyle.Dashed, priceFormat: pctFmt, title: "CDI" })
      .setData(cdi as { time: Time; value: number }[]);

    chartBot
      .addLineSeries({ color: WARNING, lineWidth: 2, priceFormat: pctFmt, title: "IBOV" })
      .setData(ibov as { time: Time; value: number }[]);

    // dstSeries pertence ao gráfico DESTINO, não ao que disparou o evento —
    // param.seriesData (do gráfico de origem) nunca teria essa série como
    // chave, então o valor precisa vir dos dados locais pelo mesmo tempo.
    function syncCharts(
      src: IChartApi,
      dst: IChartApi,
      dstSeries: ISeriesApi<"Area"> | ISeriesApi<"Line">,
      dstData: Ponto[],
    ) {
      src.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range) dst.timeScale().setVisibleLogicalRange(range);
      });
      src.subscribeCrosshairMove((param) => {
        if (!param.time) {
          dst.clearCrosshairPosition();
          return;
        }
        const ponto = dstData.find((d) => d.time === param.time);
        if (ponto) {
          dst.setCrosshairPosition(ponto.value, param.time as Time, dstSeries);
        }
      });
    }

    syncCharts(chartTop, chartBot, twrLine, twrGerida);
    syncCharts(chartBot, chartTop, totalArea, total);

    chartTop.timeScale().fitContent();
    chartBot.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (!wrapperRef.current) return;
      const w = wrapperRef.current.clientWidth;
      chartTop.applyOptions({ width: w });
      chartBot.applyOptions({ width: w });
    });
    ro.observe(wrapperRef.current!);

    return () => {
      ro.disconnect();
      chartTop.remove();
      chartBot.remove();
    };
  }, [total, funcef, gerida, twrGerida, cdi, ibov]);

  return (
    <div ref={wrapperRef}>
      <div className="flex items-center gap-4 mb-2 text-xs flex-wrap" style={{ color: "var(--text-muted)" }}>
        <LegendItem color={ACCENT} label="Total" />
        <LegendItem color={WARNING} label="FUNCEF" dashed />
        <LegendItem color={PURPLE} label="Gerida (eixo próprio)" dotted />
      </div>
      <div ref={topRef} />
      <div style={{ height: 1, background: "var(--border-soft)", margin: "4px 0" }} />
      <div className="flex items-center gap-4 mb-2 mt-2 text-xs flex-wrap" style={{ color: "var(--text-muted)" }}>
        <LegendItem color={ACCENT} label="TWR Gerida" />
        <LegendItem color={TEXT_MUTED} label="CDI" dashed />
        <LegendItem color={WARNING} label="IBOV" />
      </div>
      <div ref={botRef} />
    </div>
  );
}
