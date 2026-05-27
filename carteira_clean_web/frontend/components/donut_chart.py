"""
Donut de alocação — ECharts via CDN.
Retorna HTML puro para uso via st.components.v1.html().
CDN: https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js
"""

import json


def donut_alocacao_html(classes: dict, total: float) -> str:
    """
    classes: {"Renda Variável": 72450.63, "Renda Fixa": 45417.42, ...}
    total:   soma dos valores
    """
    cores = ["#6366F1", "#26A69A", "#F59E0B", "#EF5350", "#8B5CF6"]

    data = []
    for i, (nome, valor) in enumerate(classes.items()):
        data.append({
            "name": nome,
            "value": round(valor, 2),
            "itemStyle": {"color": cores[i % len(cores)]},
        })

    # Formatar total para anotação central
    if total >= 1_000_000:
        total_fmt = f"R$ {total/1_000_000:.2f}M".replace(".", ",")
    elif total >= 1_000:
        total_fmt = f"R$ {total/1_000:.1f}k".replace(".", ",")
    else:
        total_fmt = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    data_json = json.dumps(data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0F1117; overflow: hidden; }}
  #chart {{ width: 100%; height: 100vh; }}
</style>
</head>
<body>
<div id="chart"></div>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script>
(function() {{
  const chart = echarts.init(document.getElementById('chart'), null, {{
    backgroundColor: '#0F1117',
    renderer: 'canvas',
  }});

  const data = {data_json};
  const total = {total:.2f};

  function fmtBRL(v) {{
    return 'R$ ' + v.toLocaleString('pt-BR', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
  }}

  chart.setOption({{
    backgroundColor: '#0F1117',
    tooltip: {{
      trigger: 'item',
      backgroundColor: '#1C2333',
      borderColor: '#252D3D',
      textStyle: {{ color: '#D1D4DC', fontSize: 12 }},
      formatter: params => (
        '<b>' + params.name + '</b><br/>' +
        params.percent.toFixed(1) + '%<br/>' +
        fmtBRL(params.value)
      ),
    }},
    graphic: [{{
      type: 'text',
      left: 'center',
      top: 'middle',
      style: {{
        text: 'Gerida\\n{total_fmt}',
        textAlign: 'center',
        fill: '#D1D4DC',
        fontSize: 11,
        lineHeight: 18,
        fontFamily: '-apple-system, BlinkMacSystemFont, Inter, sans-serif',
      }},
    }}],
    series: [{{
      type: 'pie',
      radius: ['46%', '64%'],
      center: ['50%', '52%'],
      avoidLabelOverlap: true,
      data: data,
      label: {{
        show: true,
        position: 'outside',
        color: '#D1D4DC',
        fontSize: 10,
        fontFamily: '-apple-system, BlinkMacSystemFont, Inter, sans-serif',
        formatter: '{{b}}\\n{{d}}%',
        lineHeight: 15,
        overflow: 'break',
      }},
      labelLine: {{
        length: 6,
        length2: 8,
        lineStyle: {{ color: '#4B5563', width: 1 }},
      }},
      emphasis: {{
        itemStyle: {{
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0,0,0,0.5)',
        }},
      }},
      itemStyle: {{
        borderColor: '#0F1117',
        borderWidth: 2,
        borderRadius: 3,
      }},
    }}],
  }});

  window.addEventListener('resize', () => chart.resize());
}})();
</script>
</body>
</html>"""
