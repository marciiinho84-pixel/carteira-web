"""
KPI Card — estilo Investidor10.
Retorna HTML puro para uso via st.components.v1.html().
"""


def kpi_card_html(
    label: str,
    value: str,
    badge_text: str = None,
    badge_positive: bool = True,
    badge_neutral: bool = False,
    subtitle: str = None,
) -> str:
    if badge_text:
        if badge_neutral:
            bg_badge = "rgba(99,102,241,0.18)"
            cor_badge = "#6366F1"
        elif badge_positive:
            bg_badge = "rgba(38,166,154,0.18)"
            cor_badge = "#26A69A"
        else:
            bg_badge = "rgba(239,83,80,0.18)"
            cor_badge = "#EF5350"

        badge_html = (
            f'<span style="background:{bg_badge};color:{cor_badge};'
            f'font-size:0.72rem;font-weight:600;padding:2px 8px;'
            f'border-radius:4px;white-space:nowrap">{badge_text}</span>'
        )
    else:
        badge_html = ""

    subtitle_html = (
        f'<span style="color:#6B7280;font-size:0.72rem">{subtitle}</span>'
        if subtitle else ""
    )

    footer_html = ""
    if badge_html or subtitle_html:
        footer_html = (
            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:8px">'
            f'{badge_html}{subtitle_html}'
            f'</div>'
        )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: transparent; overflow: hidden; }}
</style>
</head>
<body>
<div style="
  background: rgba(20,25,35,0.7);
  border: 1px solid rgba(37,45,61,0.5);
  border-radius: 10px;
  padding: 14px 18px;
  font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
  height: 100%;
  box-sizing: border-box;
">
  <div style="
    color: #6B7280;
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 500;
    margin-bottom: 6px;
  ">{label}</div>
  <div style="
    color: #FFFFFF;
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.1;
  ">{value}</div>
  {footer_html}
</div>
</body>
</html>"""
