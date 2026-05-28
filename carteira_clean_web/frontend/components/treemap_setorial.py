"""
Treemap hierárquico setorial — ECharts (setor → ativos).
CDN: https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js
"""

import json

PALETA_SETORES = [
    '#6366F1', '#26A69A', '#F59E0B', '#EC4899',
    '#3B82F6', '#8B5CF6', '#10B981', '#EF4444',
    '#06B6D4', '#84CC16', '#F97316', '#A855F7',
]


def treemap_setorial_html(setores: list, total_rv: float = 0) -> str:
    """
    setores: lista de dicts com nome, valor_total, pct_rv,
             ativos: [{ticker, valor, pct_setor}]
    """
    if total_rv <= 0:
        total_rv = sum(s.get("valor_total", 0) for s in setores) or 1

    data = []
    for i, s in enumerate(setores):
        cor = PALETA_SETORES[i % len(PALETA_SETORES)]
        n_ativos = len(s.get("ativos", []))
        pct_rv_pct = round(s.get("pct_rv", 0) * 100, 1)
        children = [
            {
                "name": a["ticker"],
                "value": round(float(a["valor"]), 2),
                "itemStyle": {"color": cor, "opacity": 0.75},
            }
            for a in s.get("ativos", [])
        ]
        data.append({
            "name": s["nome"],
            "value": round(float(s["valor_total"]), 2),
            "pct_rv": pct_rv_pct,
            "n_ativos": n_ativos,
            "itemStyle": {"color": cor},
            "children": children,
        })

    data_json = json.dumps(data, ensure_ascii=False)

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
  const chart = echarts.init(document.getElementById('chart'), null, {{
    renderer: 'canvas',
  }});

  const data = {data_json};

  function fmtBRL(v) {{
    if (v >= 1000000) return 'R$ ' + (v/1000000).toFixed(2).replace('.', ',') + 'M';
    if (v >= 1000) return 'R$ ' + (v/1000).toFixed(1).replace('.', ',') + 'k';
    return 'R$ ' + v.toLocaleString('pt-BR', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
  }}

  chart.setOption({{
    backgroundColor: 'transparent',
    tooltip: {{
      trigger: 'item',
      backgroundColor: '#1C2333',
      borderColor: '#252D3D',
      textStyle: {{ color: '#D1D4DC', fontSize: 12, fontFamily: '-apple-system, Inter, sans-serif' }},
      formatter: function(params) {{
        const d = params.data;
        if (!d) return '';
        // Setor (nível 0 — tem pct_rv e n_ativos)
        if (d.n_ativos !== undefined) {{
          return (
            '<b>' + d.name + '</b>' +
            '<br/>Valor: ' + fmtBRL(d.value) +
            '<br/>' + d.n_ativos + ' ativo' + (d.n_ativos !== 1 ? 's' : '') +
            ' · ' + d.pct_rv + '% RV'
          );
        }}
        // Ativo (nível 1)
        const parent = params.treePathInfo?.[params.treePathInfo.length - 2];
        const pct_set = parent && parent.value > 0
          ? ((d.value / parent.value) * 100).toFixed(1)
          : '—';
        return (
          '<b>' + d.name + '</b>' +
          '<br/>Valor: ' + fmtBRL(d.value) +
          '<br/>% setor: ' + pct_set + '%'
        );
      }},
    }},
    series: [{{
      type: 'treemap',
      roam: false,
      nodeClick: 'zoomToNode',
      breadcrumb: {{ show: false }},
      data: data,
      label: {{
        show: true,
        color: '#FFFFFF',
        fontSize: 11,
        fontFamily: '-apple-system, BlinkMacSystemFont, Inter, sans-serif',
        formatter: function(params) {{
          return params.name + '\\n' + fmtBRL(params.value);
        }},
      }},
      levels: [
        {{
          upperLabel: {{
            show: true,
            height: 24,
            color: '#FFFFFF',
            fontSize: 12,
            fontWeight: 600,
            fontFamily: '-apple-system, BlinkMacSystemFont, Inter, sans-serif',
            formatter: function(params) {{
              return params.name;
            }},
          }},
          itemStyle: {{ gapWidth: 4, borderWidth: 0 }},
        }},
        {{
          label: {{
            show: true,
            color: '#FFFFFF',
            fontSize: 11,
            fontFamily: '-apple-system, BlinkMacSystemFont, Inter, sans-serif',
          }},
          itemStyle: {{
            gapWidth: 2,
            borderColor: 'rgba(0,0,0,0.15)',
            borderWidth: 1,
          }},
        }},
      ],
    }}],
  }});

  window.addEventListener('resize', () => chart.resize());
}})();
</script>
</body>
</html>"""
