"""
Heatmap de posições RV — ECharts treemap com 3 modos de visualização.
CDN: https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js
"""

import json


def heatmap_posicoes_html(posicoes: list, mode: str = "dia") -> str:
    """
    posicoes: lista de dicts com ticker, valor_atual, variacao_dia_pct,
              contrib_dia_rs, pl_total_pct, pl_total_rs, pct_rv, setor

    mode:
      "dia"    → cor = variação do dia (−3% a +3%)
      "pnl"    → cor = P&L total acumulado (−50% a +100%)
      "tamanho" → cor = concentração na carteira (0% a 20%)
    """
    data = []
    for p in posicoes:
        dia_pct = float(p.get("variacao_dia_pct") or 0) * 100
        pnl_pct = float(p.get("pl_total_pct") or 0) * 100
        peso_pct = float(p.get("pct_rv") or 0) * 100

        if mode == "dia":
            color_val = round(max(-3.0, min(3.0, dia_pct)), 4)
        elif mode == "pnl":
            color_val = round(max(-50.0, min(100.0, pnl_pct)), 4)
        else:  # tamanho
            color_val = round(max(0.0, min(20.0, peso_pct)), 4)

        data.append({
            "name": p["ticker"],
            "value": [round(float(p["valor_atual"]), 2), color_val],
            "contrib_rs": round(float(p.get("contrib_dia_rs") or 0), 2),
            "pl_pct": round(pnl_pct, 2),
            "pl_rs": round(float(p.get("pl_total_rs") or 0), 2),
            "pct_rv": round(peso_pct, 2),
            "dia_pct_real": round(dia_pct, 2),
            "setor": p.get("setor", "Outros"),
        })

    data_json = json.dumps(data, ensure_ascii=False)

    if mode == "dia":
        vm_min, vm_max = -3, 3
        vm_colors = "['#A32D2D','#F09595','#5F5E5A','#9FE1CB','#0F6E56']"
        label_fn = "sinal + d.dia_pct_real.toFixed(2) + '%'"
        label_color_cond = "d.dia_pct_real >= 0 ? '#9FE1CB' : '#F09595'"
        detail_today = "d.dia_pct_real.toFixed(2) + '% (' + fmtBRL(d.contrib_rs) + ')'"
    elif mode == "pnl":
        vm_min, vm_max = -50, 100
        vm_colors = "['#A32D2D','#F09595','#5F5E5A','#9FE1CB','#0F6E56']"
        label_fn = "sinal + d.pl_pct.toFixed(1) + '%'"
        label_color_cond = "d.pl_pct >= 0 ? '#9FE1CB' : '#F09595'"
        detail_today = "d.dia_pct_real.toFixed(2) + '% hoje'"
    else:
        vm_min, vm_max = 0, 20
        vm_colors = "['#1a1d2e','#3730a3','#6366F1','#818cf8','#c7d2fe']"
        label_fn = "d.pct_rv.toFixed(1) + '% RV'"
        label_color_cond = "'#FFFFFF'"
        detail_today = "d.dia_pct_real.toFixed(2) + '% hoje'"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: transparent; overflow: hidden; }}
  #chart {{ width: 100%; height: 100vh; }}
</style>
</head>
<body>
<div id="chart"></div>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script>
(function() {{
  const chart = echarts.init(document.getElementById('chart'), null, {{ renderer: 'canvas' }});
  const data = {data_json};

  function fmtBRL(v) {{
    const abs = Math.abs(v);
    const s = 'R$ ' + abs.toLocaleString('pt-BR', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
    return (v < 0 ? '-' : '') + s;
  }}

  chart.setOption({{
    backgroundColor: 'transparent',
    visualMap: {{
      type: 'continuous',
      show: false,
      dimension: 1,
      min: {vm_min},
      max: {vm_max},
      inRange: {{ color: {vm_colors} }},
    }},
    tooltip: {{
      trigger: 'item',
      backgroundColor: '#1C2333',
      borderColor: '#252D3D',
      textStyle: {{ color: '#D1D4DC', fontSize: 12, fontFamily: '-apple-system, Inter, sans-serif' }},
      formatter: function(params) {{
        const d = params.data;
        if (!d || !d.name) return '';
        const sinal = d.dia_pct_real >= 0 ? '+' : '';
        const cor_dia = d.dia_pct_real >= 0 ? '#9FE1CB' : '#F09595';
        const cor_pnl = d.pl_pct >= 0 ? '#9FE1CB' : '#F09595';
        return (
          '<b>' + d.name + '</b>' +
          '<br><span style="color:#9CA3AF;font-size:10px">' + d.setor + '</span>' +
          '<br>Valor: ' + fmtBRL(d.value[0]) + ' · ' + d.pct_rv.toFixed(1) + '% RV' +
          '<br>Hoje: <span style="color:' + cor_dia + '">' + sinal + d.dia_pct_real.toFixed(2) + '%</span>' +
          ' (' + fmtBRL(d.contrib_rs) + ')' +
          '<br>P&L total: <span style="color:' + cor_pnl + '">' +
          (d.pl_pct >= 0 ? '+' : '') + d.pl_pct.toFixed(2) + '%</span>' +
          ' (' + fmtBRL(d.pl_rs) + ')'
        );
      }},
    }},
    series: [{{
      type: 'treemap',
      roam: false,
      nodeClick: false,
      breadcrumb: {{ show: false }},
      data: data,
      visualDimension: 1,
      label: {{
        show: true,
        color: '#FFFFFF',
        fontSize: 11,
        fontWeight: 500,
        fontFamily: '-apple-system, BlinkMacSystemFont, Inter, sans-serif',
        formatter: function(params) {{
          const d = params.data;
          const sinal = d.value[1] >= 0 ? '+' : '';
          return params.name + '\\n' + {label_fn};
        }},
      }},
      itemStyle: {{ gapWidth: 3, borderWidth: 0 }},
      levels: [{{ upperLabel: {{ show: false }} }}],
    }}],
  }});

  window.addEventListener('resize', () => chart.resize());
}})();
</script>
</body>
</html>"""
