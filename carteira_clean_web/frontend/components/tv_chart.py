"""
Gráfico dual TradingView Lightweight Charts.
Retorna HTML puro para uso via st.components.v1.html().
CDN: https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js
"""

import json


def tv_dual_chart_html(
    patrimonio_series: list,
    twr_series: list,
    cdi_series: list,
    ibov_series: list,
) -> str:
    pat_json  = json.dumps(patrimonio_series)
    twr_json  = json.dumps(twr_series)
    cdi_json  = json.dumps(cdi_series)
    ibov_json = json.dumps(ibov_series)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #0F1117;
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
    overflow: hidden;
  }}
  #wrapper {{
    background: #0F1117;
    border: 1px solid #1C2333;
    border-radius: 10px;
    padding: 14px 14px 6px;
  }}
  #header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }}
  #header-title {{
    color: #6B7280;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 500;
  }}
  #legend {{
    display: flex;
    gap: 14px;
    align-items: center;
  }}
  .leg-item {{
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.65rem;
    color: #9CA3AF;
    white-space: nowrap;
  }}
  .leg-dot {{
    width: 8px; height: 2px; border-radius: 1px;
  }}
  #chart-patrimonio {{ width: 100%; height: 260px; }}
  #divider {{
    height: 1px;
    background: #1C2333;
    margin: 4px 0;
  }}
  #chart-rentabilidade {{ width: 100%; height: 200px; }}
</style>
</head>
<body>
<div id="wrapper">
  <div id="header">
    <span id="header-title">Patrimônio &amp; Rentabilidade</span>
    <div id="legend">
      <div class="leg-item">
        <div class="leg-dot" style="background:#6366F1;height:2px"></div>
        <span>TWR Gerida</span>
      </div>
      <div class="leg-item">
        <div class="leg-dot" style="background:#787B86;height:1px;border-top:1px dashed #787B86"></div>
        <span>CDI</span>
      </div>
      <div class="leg-item">
        <div class="leg-dot" style="background:#F59E0B"></div>
        <span>IBOV</span>
      </div>
    </div>
  </div>

  <div id="chart-patrimonio"></div>
  <div id="divider"></div>
  <div id="chart-rentabilidade"></div>
</div>

<script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
<script>
(function() {{
  const SHARED_OPTS = {{
    layout: {{
      background: {{ color: '#0F1117' }},
      textColor: '#9CA3AF',
      fontSize: 11,
    }},
    grid: {{
      vertLines: {{ color: '#1a2030' }},
      horzLines: {{ color: '#1a2030' }},
    }},
    rightPriceScale: {{
      borderColor: '#1C2333',
      scaleMargins: {{ top: 0.05, bottom: 0.05 }},
    }},
    timeScale: {{
      borderColor: '#1C2333',
      timeVisible: true,
      secondsVisible: false,
    }},
    crosshair: {{ mode: 1 }},
    handleScroll: true,
    handleScale: true,
  }};

  // ─── Gráfico superior — Patrimônio ───────────────────────────
  const chartTop = LightweightCharts.createChart(
    document.getElementById('chart-patrimonio'),
    Object.assign({{}}, SHARED_OPTS, {{
      width:  document.getElementById('chart-patrimonio').clientWidth,
      height: 260,
      rightPriceScale: Object.assign({{}}, SHARED_OPTS.rightPriceScale, {{
        priceFormatter: v => 'R$ ' + (v / 1_000_000).toFixed(2).replace('.', ',') + 'M',
      }}),
    }})
  );

  const areaSeries = chartTop.addAreaSeries({{
    lineColor:   '#6366F1',
    topColor:    'rgba(99,102,241,0.20)',
    bottomColor: 'rgba(99,102,241,0.00)',
    lineWidth:   2,
    priceFormat: {{ type: 'custom', formatter: v => 'R$ ' + (v/1_000_000).toFixed(2).replace('.', ',') + 'M' }},
  }});
  areaSeries.setData({pat_json});

  // ─── Gráfico inferior — Rentabilidade ────────────────────────
  const chartBot = LightweightCharts.createChart(
    document.getElementById('chart-rentabilidade'),
    Object.assign({{}}, SHARED_OPTS, {{
      width:  document.getElementById('chart-rentabilidade').clientWidth,
      height: 200,
    }})
  );

  const pctFmt = {{ type: 'custom', formatter: v => (v >= 0 ? '+' : '') + v.toFixed(2).replace('.', ',') + '%' }};

  const twrLine = chartBot.addLineSeries({{
    color:       '#6366F1',
    lineWidth:   2,
    priceFormat: pctFmt,
    title:       'TWR',
  }});
  twrLine.setData({twr_json});

  const cdiLine = chartBot.addLineSeries({{
    color:       '#787B86',
    lineWidth:   1,
    lineStyle:   LightweightCharts.LineStyle.Dashed,
    priceFormat: pctFmt,
    title:       'CDI',
  }});
  cdiLine.setData({cdi_json});

  const ibovLine = chartBot.addLineSeries({{
    color:       '#F59E0B',
    lineWidth:   1.5,
    priceFormat: pctFmt,
    title:       'IBOV',
  }});
  ibovLine.setData({ibov_json});

  // ─── Linha zero de referência ─────────────────────────────────
  chartBot.addLineSeries({{
    color:       'rgba(150,150,150,0.25)',
    lineWidth:   1,
    lineStyle:   LightweightCharts.LineStyle.Solid,
    priceFormat: pctFmt,
    lastValueVisible: false,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
  }}).setData({twr_json}.map(d => ({{ time: d.time, value: 0 }})));

  // ─── Sincronização scroll + crosshair ────────────────────────
  function syncCharts(src, dst, dstSeries) {{
    src.timeScale().subscribeVisibleLogicalRangeChange(range => {{
      if (range) dst.timeScale().setVisibleLogicalRange(range);
    }});
    src.subscribeCrosshairMove(param => {{
      if (!param.time) return;
      const val = param.seriesData.get(dstSeries);
      if (val !== undefined) {{
        dst.setCrosshairPosition(val.value, param.time, dstSeries);
      }}
    }});
  }}

  syncCharts(chartTop, chartBot, twrLine);
  syncCharts(chartBot, chartTop, areaSeries);

  // ─── Fit inicial ─────────────────────────────────────────────
  chartTop.timeScale().fitContent();
  chartBot.timeScale().fitContent();

  // ─── Responsividade ──────────────────────────────────────────
  const ro = new ResizeObserver(() => {{
    const w = document.getElementById('wrapper').clientWidth - 28;
    chartTop.resize(w, 260);
    chartBot.resize(w, 200);
  }});
  ro.observe(document.getElementById('wrapper'));
}})();
</script>
</body>
</html>"""
