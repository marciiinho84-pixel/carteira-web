"""
Ranking P&L total — ECharts barra horizontal (top winners + bottom losers).
CDN: https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js
"""

import json


def ranking_pnl_html(posicoes: list, top_n: int = 5) -> str:
    """
    posicoes: lista de dicts com ticker, pl_total_pct, pl_total_rs.
    Mostra top_n winners + top_n losers em barras horizontais.
    """
    sorted_pos = sorted(posicoes, key=lambda p: p.get("pl_total_pct", 0))

    losers = sorted_pos[:top_n]
    winners = list(reversed(sorted_pos[-top_n:]))

    tickers = [p["ticker"] for p in losers] + [""] + [p["ticker"] for p in winners]
    values = [round(p.get("pl_total_pct", 0) * 100, 2) for p in losers] + [None] + \
             [round(p.get("pl_total_pct", 0) * 100, 2) for p in winners]
    rs_vals = [round(p.get("pl_total_rs", 0), 2) for p in losers] + [0] + \
              [round(p.get("pl_total_rs", 0), 2) for p in winners]

    colors = ["#EF5350" if v is not None and v < 0 else "#26A69A" if v is not None and v >= 0 else "transparent"
              for v in values]

    data_items = [
        {"value": v, "rs": r, "itemStyle": {"color": c}}
        for v, r, c in zip(values, rs_vals, colors)
    ]

    data_json = json.dumps(data_items, ensure_ascii=False)
    tickers_json = json.dumps(tickers, ensure_ascii=False)

    height = (len(tickers) * 28) + 20

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: transparent; overflow: hidden; }}
  #chart {{ width: 100%; height: {height}px; }}
</style>
</head>
<body>
<div id="chart"></div>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script>
(function() {{
  const chart = echarts.init(document.getElementById('chart'), null, {{ renderer: 'canvas' }});

  const tickers = {tickers_json};
  const data = {data_json};

  function fmtBRL(v) {{
    const abs = Math.abs(v);
    const s = 'R$ ' + abs.toLocaleString('pt-BR', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
    return (v < 0 ? '-' : '+') + s;
  }}

  chart.setOption({{
    backgroundColor: 'transparent',
    grid: {{ left: 72, right: 70, top: 4, bottom: 4, containLabel: false }},
    tooltip: {{
      trigger: 'item',
      backgroundColor: '#1C2333',
      borderColor: '#252D3D',
      textStyle: {{ color: '#D1D4DC', fontSize: 12 }},
      formatter: function(params) {{
        const d = params.data;
        if (d.value === null) return '';
        const sinal = d.value >= 0 ? '+' : '';
        return '<b>' + params.name + '</b><br/>P&L: ' + sinal + d.value.toFixed(2) + '%<br/>' + fmtBRL(d.rs);
      }},
    }},
    xAxis: {{
      type: 'value',
      show: false,
      min: function(v) {{ return Math.min(v.min * 1.1, -5); }},
      max: function(v) {{ return Math.max(v.max * 1.1, 5); }},
    }},
    yAxis: {{
      type: 'category',
      data: tickers,
      axisLabel: {{
        color: '#9CA3AF',
        fontSize: 11,
        fontFamily: '-apple-system, Inter, sans-serif',
        formatter: v => v || '',
      }},
      axisTick: {{ show: false }},
      axisLine: {{ lineStyle: {{ color: '#1C2333' }} }},
    }},
    series: [{{
      type: 'bar',
      data: data,
      barMaxWidth: 20,
      label: {{
        show: true,
        position: function(params) {{ return params.data.value >= 0 ? 'right' : 'left'; }},
        color: '#D1D4DC',
        fontSize: 10,
        fontFamily: '-apple-system, Inter, sans-serif',
        formatter: function(params) {{
          if (params.data.value === null) return '';
          const sinal = params.data.value >= 0 ? '+' : '';
          return sinal + params.data.value.toFixed(1) + '%';
        }},
      }},
    }}],
  }});

  window.addEventListener('resize', () => chart.resize());
}})();
</script>
</body>
</html>"""
