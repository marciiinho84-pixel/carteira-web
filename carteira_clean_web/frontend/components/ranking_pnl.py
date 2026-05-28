"""
Ranking P&L total — ECharts barra horizontal (top winners + bottom losers).
"""

import json


def ranking_pnl_html(posicoes: list, top_n: int = 5) -> str:
    sorted_pos = sorted(posicoes, key=lambda p: p.get("pl_total_pct", 0))

    losers  = sorted_pos[:top_n]
    winners = list(reversed(sorted_pos[-top_n:]))

    tickers = [p["ticker"] for p in losers] + [""] + [p["ticker"] for p in winners]
    values  = [round(p.get("pl_total_pct", 0) * 100, 2) for p in losers] + [None] + \
              [round(p.get("pl_total_pct", 0) * 100, 2) for p in winners]
    rs_vals = [round(p.get("pl_total_rs", 0), 2) for p in losers] + [0] + \
              [round(p.get("pl_total_rs", 0), 2) for p in winners]

    data_items = []
    for v, r in zip(values, rs_vals):
        if v is None:
            data_items.append({"value": None, "rs": 0, "itemStyle": {"color": "transparent"}})
        elif v >= 0:
            data_items.append({
                "value": v, "rs": r,
                "itemStyle": {
                    "color": {
                        "type": "linear", "x": 0, "y": 0, "x2": 1, "y2": 0,
                        "colorStops": [
                            {"offset": 0, "color": "rgba(38,166,154,0.55)"},
                            {"offset": 1, "color": "#26A69A"},
                        ],
                    }
                }
            })
        else:
            data_items.append({
                "value": v, "rs": r,
                "itemStyle": {
                    "color": {
                        "type": "linear", "x": 0, "y": 0, "x2": 1, "y2": 0,
                        "colorStops": [
                            {"offset": 0, "color": "#EF5350"},
                            {"offset": 1, "color": "rgba(239,83,80,0.55)"},
                        ],
                    }
                }
            })

    data_json    = json.dumps(data_items, ensure_ascii=False)
    tickers_json = json.dumps(tickers,   ensure_ascii=False)
    height       = (len(tickers) * 30) + 24

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:transparent; overflow:hidden; }}
  #chart {{ width:100%; height:{height}px; }}
</style>
</head>
<body>
<div id="chart"></div>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script>
(function() {{
  const chart = echarts.init(document.getElementById('chart'), null, {{ renderer: 'canvas' }});
  const tickers = {tickers_json};
  const data    = {data_json};

  function fmtBRL(v) {{
    const abs = Math.abs(v);
    const s = 'R$ ' + abs.toLocaleString('pt-BR', {{minimumFractionDigits:2, maximumFractionDigits:2}});
    return (v < 0 ? '-' : '+') + s;
  }}

  chart.setOption({{
    backgroundColor: 'transparent',
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut',
    grid: {{ left: 76, right: 64, top: 4, bottom: 4, containLabel: false }},
    tooltip: {{
      trigger: 'item',
      backgroundColor: '#1C2333',
      borderColor: '#252D3D',
      borderWidth: 1,
      padding: [8, 12],
      textStyle: {{ color: '#D1D4DC', fontSize: 12, fontFamily: 'Inter, sans-serif' }},
      formatter: function(params) {{
        const d = params.data;
        if (d.value === null) return '';
        const sinal = d.value >= 0 ? '+' : '';
        return '<b style="font-size:13px">' + params.name + '</b><br/>' +
               'P&L: <span style="color:' + (d.value>=0?'#26A69A':'#EF5350') +
               ';font-weight:600">' + sinal + d.value.toFixed(2).replace('.',',') +
               '%</span><br/>' + fmtBRL(d.rs);
      }},
    }},
    xAxis: {{
      type: 'value',
      show: false,
      min: function(v) {{ return Math.min(v.min * 1.15, -5); }},
      max: function(v) {{ return Math.max(v.max * 1.15,  5); }},
    }},
    yAxis: {{
      type: 'category',
      data: tickers,
      axisLabel: {{
        color: '#9CA3AF',
        fontSize: 11,
        fontFamily: 'Inter, -apple-system, sans-serif',
        fontWeight: 500,
        formatter: v => v || '',
      }},
      axisTick: {{ show: false }},
      axisLine: {{ lineStyle: {{ color: '#1C2333' }} }},
    }},
    series: [{{
      type: 'bar',
      data: data,
      barMaxWidth: 18,
      barMinHeight: 3,
      label: {{
        show: true,
        position: function(params) {{ return params.data.value >= 0 ? 'right' : 'left'; }},
        color: '#D1D4DC',
        fontSize: 11,
        fontFamily: 'Inter, -apple-system, sans-serif',
        fontWeight: 600,
        formatter: function(params) {{
          if (params.data.value === null) return '';
          const sinal = params.data.value >= 0 ? '+' : '';
          return sinal + params.data.value.toFixed(1).replace('.',',') + '%';
        }},
      }},
      itemStyle: {{ borderRadius: [0, 3, 3, 0] }},
    }}],
  }});

  window.addEventListener('resize', () => chart.resize());
}})();
</script>
</body>
</html>"""
