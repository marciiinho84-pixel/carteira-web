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
  patrimonio: Ponto[];
  twr: Ponto[];
  cdi: Ponto[];
  ibov: Ponto[];
}

// Papel & Tinta — tokens lidos de globals.css (lightweight-charts não aceita
// var(), precisa do valor literal).
const BG_CARD = "#FBF6EC";
const BORDER = "#DDD2BF";
const BORDER_SOFT = "#E5DBC8";
const TEXT_MUTED = "#7A7160";
const ACCENT = "#C15F3C";
const WARNING = "#C9862B";

function LegendItem({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <div
        style={
          dashed
            ? { width: 14, height: 0, borderTop: `1.5px dashed ${color}` }
            : { width: 14, height: 2, borderRadius: 1, background: color }
        }
      />
      <span>{label}</span>
    </div>
  );
}

export default function PatrimonioChart({ patrimonio, twr, cdi, ibov }: Props) {
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
      height: 260,
      rightPriceScale: { borderColor: BORDER, scaleMargins: { top: 0.05, bottom: 0.05 } },
    });

    const areaSeries = chartTop.addAreaSeries({
      lineColor: ACCENT,
      topColor: "rgba(193,95,60,0.20)",
      bottomColor: "rgba(193,95,60,0.00)",
      lineWidth: 2,
      priceFormat: {
        type: "custom",
        minMove: 0.01,
        formatter: (v: number) => "R$ " + (v / 1_000_000).toFixed(2).replace(".", ",") + "M",
      },
    });
    areaSeries.setData(patrimonio as { time: Time; value: number }[]);

    const chartBot: IChartApi = createChart(botRef.current, {
      ...SHARED_OPTS,
      width: botRef.current.clientWidth,
      height: 200,
      // top maior que o padrão — dá espaço pras etiquetas de último valor
      // (IBOV/CDI/TWR, empilhadas) não colidirem com o rótulo do grid mais alto.
      rightPriceScale: { borderColor: BORDER, scaleMargins: { top: 0.16, bottom: 0.05 } },
    });

    const pctFmt = {
      type: "custom" as const,
      minMove: 0.01,
      formatter: (v: number) => (v >= 0 ? "+" : "") + v.toFixed(2).replace(".", ",") + "%",
    };

    const twrLine = chartBot.addLineSeries({ color: ACCENT, lineWidth: 2, priceFormat: pctFmt, title: "TWR" });
    twrLine.setData(twr as { time: Time; value: number }[]);

    const cdiLine = chartBot.addLineSeries({
      color: TEXT_MUTED, lineWidth: 1, lineStyle: LineStyle.Dashed, priceFormat: pctFmt, title: "CDI",
    });
    cdiLine.setData(cdi as { time: Time; value: number }[]);

    const ibovLine = chartBot.addLineSeries({ color: WARNING, lineWidth: 2, priceFormat: pctFmt, title: "IBOV" });
    ibovLine.setData(ibov as { time: Time; value: number }[]);

    chartBot
      .addLineSeries({
        color: "rgba(122,113,96,0.25)",
        lineWidth: 1,
        lineStyle: LineStyle.Solid,
        priceFormat: pctFmt,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      })
      .setData(twr.map((d) => ({ time: d.time as Time, value: 0 })));

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

    syncCharts(chartTop, chartBot, twrLine, twr);
    syncCharts(chartBot, chartTop, areaSeries, patrimonio);

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
  }, [patrimonio, twr, cdi, ibov]);

  return (
    <div ref={wrapperRef}>
      <div className="flex items-center gap-4 mb-2 text-[11px]" style={{ color: "var(--text-muted)" }}>
        <LegendItem color={ACCENT} label="TWR Gerida" />
        <LegendItem color={TEXT_MUTED} label="CDI" dashed />
        <LegendItem color={WARNING} label="IBOV" />
      </div>
      <div ref={topRef} />
      <div style={{ height: 1, background: "var(--border-soft)", margin: "4px 0" }} />
      <div ref={botRef} />
    </div>
  );
}
