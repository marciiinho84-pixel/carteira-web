"""
Página: Risco ex-ante — exposição por bloco/classe, liquidez e orientação ao Assistente (Fatia 6).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from carteira_clean_web.frontend.utils import api, fmt

# ─── Classificação canônica IPS (38 ativos, confirmada em produção) ───────────
# Fonte única de verdade para o frontend — não depende do estado do DB local.
_BLOCO_MAP: dict[str, str] = {
    # SWING_TRADE — 20 ativos
    "ALOS3":  "SWING_TRADE", "AURA33": "SWING_TRADE", "AXIA3":  "SWING_TRADE",
    "AZZA3":  "SWING_TRADE", "CSMG3":  "SWING_TRADE", "DIVO11": "SWING_TRADE",
    "EMBJ3":  "SWING_TRADE", "INBR32": "SWING_TRADE", "ITUB3":  "SWING_TRADE",
    "MDNE3":  "SWING_TRADE", "PETR4":  "SWING_TRADE", "PLPL3":  "SWING_TRADE",
    "POMO4":  "SWING_TRADE", "PRIO3":  "SWING_TRADE", "RDOR3":  "SWING_TRADE",
    "ROXO34": "SWING_TRADE", "SEER3":  "SWING_TRADE", "SMAL11": "SWING_TRADE",
    "TTEN3":  "SWING_TRADE", "WEGE3":  "SWING_TRADE",
    # GROWTH — 12 ativos
    "ASML34": "GROWTH", "BAER39": "GROWTH", "BOTZ39": "GROWTH",
    "BURA39": "GROWTH", "D1EL34": "GROWTH", "ETHE11": "GROWTH",
    "G1LW34": "GROWTH", "IBMB34": "GROWTH", "M2PM34": "GROWTH",
    "MSFT34": "GROWTH", "NOKI34": "GROWTH", "S2GM34": "GROWTH",
    # DEFENSIVOS — 2 ativos
    "BSLV39":     "DEFENSIVOS", "CAIXA OURO": "DEFENSIVOS",
    # RENDA_FIXA — 2 ativos
    "C6 RENDA+": "RENDA_FIXA", "CAIXA LCI": "RENDA_FIXA",
    # FORA_IPS — 2 ativos (monitorados, não atribuídos à IPS)
    "CAIXA FIC FUNC": "FORA_IPS", "FUNCEF": "FORA_IPS",
}

# ─── IPS v1.0 — políticas por bloco ──────────────────────────────────────────
_IPS = {
    "SWING_TRADE": {"label": "Swing Trade", "alvo": 0.30, "min": 0.20, "max": 0.40, "benchmark": "IBOV"},
    "GROWTH":      {"label": "Growth",      "alvo": 0.20, "min": 0.10, "max": 0.30, "benchmark": "Nasdaq BRL"},
    "DEFENSIVOS":  {"label": "Defensivos",  "alvo": 0.20, "min": 0.15, "max": 0.25, "benchmark": "Ouro BRL"},
    "RENDA_FIXA":  {"label": "Renda Fixa",  "alvo": 0.30, "min": 0.25, "max": 0.35, "benchmark": "CDI"},
}

_ZONA_ATENCAO_PP = 0.03  # < 3pp fora da banda = amarelo


def _semaforo(pct: float, cfg: dict) -> str:
    if cfg["min"] <= pct <= cfg["max"]:
        return "🟢"
    dist = min(abs(pct - cfg["min"]), abs(pct - cfg["max"]))
    return "🟡" if dist < _ZONA_ATENCAO_PP else "🔴"


def _bloco(ticker: str, db_bloco: str | None) -> str | None:
    """Bloco IPS: mapa canônico tem prioridade; DB como fallback para novos ativos."""
    return _BLOCO_MAP.get(ticker, db_bloco)


def render():
    st.title("⚠️ Risco ex-ante")
    st.caption(
        "Análise completa disponível via 🤖 Assistente. "
        "Pergunte: **'análise de risco da carteira'**"
    )

    st.info(
        "Esta tela exibe indicadores básicos de exposição calculados localmente. "
        "Para análise completa de drawdown, stress test e liquidez, use o Assistente."
    )

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira.")
        return

    posicoes = api.get("posicoes") or []

    if not posicoes:
        st.info(
            "Nenhuma posição disponível. Após importar eventos e calcular, "
            "os dados de exposição aparecerão aqui."
        )
        return

    df_total = pd.DataFrame(posicoes)

    # Separar Carteira Gerida da FUNCEF — IPS §1
    df = df_total[df_total["composite"] == "Gerida"].copy()
    df_funcef = df_total[df_total["composite"] == "FUNCEF"]

    total = df["valor_atual"].sum()
    total_funcef = df_funcef["valor_atual"].sum()
    total_tudo = df_total["valor_atual"].sum()

    # Enriquecer bloco_ips: mapa canônico tem prioridade sobre DB
    ativos_lista = api.get("ativos") or []
    db_bloco_map = {a["ticker"]: a.get("bloco_ips") for a in ativos_lista}
    df["bloco_ips"] = df["ticker"].apply(
        lambda t: _bloco(t, db_bloco_map.get(t))
    )

    # ─── KPIs ────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Carteira Gerida", fmt.moeda(total))
    with k2:
        st.metric("FUNCEF (excluída)", fmt.moeda(total_funcef),
                  help="Monitorada separadamente — fora do escopo da IPS.")
    with k3:
        st.metric("Patrimônio Total", fmt.moeda(total_tudo))
    with k4:
        st.metric("Ativos na Gerida", len(df))

    st.divider()

    # ─── Aderência à IPS ─────────────────────────────────────────────────
    st.subheader("Aderência à IPS")
    st.caption(
        "Base: Carteira Gerida excluindo FORA_IPS. "
        "Bandas conforme IPS v1.0 · junho 2026."
    )

    # Base de cálculo: Gerida sem FORA_IPS
    df_ips_base = df[df["bloco_ips"].isin(_IPS.keys())]
    total_ips = df_ips_base["valor_atual"].sum() if not df_ips_base.empty else total

    rows_ips = []
    for bloco_key, cfg in _IPS.items():
        mask = df["bloco_ips"] == bloco_key
        valor_bloco = df.loc[mask, "valor_atual"].sum()
        pct = valor_bloco / total_ips if total_ips > 0 else 0.0
        n_ativos = int(mask.sum())
        status = _semaforo(pct, cfg)

        if pct < cfg["min"]:
            desvio = f"{(pct - cfg['min']) * 100:+.1f} pp"
        elif pct > cfg["max"]:
            desvio = f"{(pct - cfg['max']) * 100:+.1f} pp"
        else:
            desvio = "—"

        rows_ips.append({
            "": status,
            "Bloco": cfg["label"],
            "Benchmark": cfg["benchmark"],
            "Alvo": fmt.pct(cfg["alvo"]),
            "Banda": f"{cfg['min']:.0%} – {cfg['max']:.0%}",
            "Atual": fmt.pct(pct),
            "Valor": fmt.moeda(valor_bloco),
            "N ativos": n_ativos,
            "Desvio": desvio,
        })

    # Linha: FORA_IPS / Caixa (sem alvo, só monitorado)
    df_fora = df[df["bloco_ips"].isin(["FORA_IPS"]) | df["bloco_ips"].isna()]
    if not df_fora.empty:
        valor_fora = df_fora["valor_atual"].sum()
        pct_fora = valor_fora / total if total > 0 else 0.0
        rows_ips.append({
            "": "⚪",
            "Bloco": "Caixa / Fora IPS",
            "Benchmark": "—",
            "Alvo": "—",
            "Banda": "monitorado",
            "Atual": fmt.pct(pct_fora),
            "Valor": fmt.moeda(valor_fora),
            "N ativos": int(len(df_fora)),
            "Desvio": "—",
        })

    st.dataframe(pd.DataFrame(rows_ips), use_container_width=True, hide_index=True)

    st.divider()

    # ─── Exposição por classe de ativo ───────────────────────────────────
    if "classe" in df.columns:
        st.subheader("Exposição por Classe de Ativo")
        df_classe = (
            df.groupby("classe", dropna=False)["valor_atual"]
            .sum()
            .reset_index()
            .sort_values("valor_atual", ascending=False)
        )
        df_classe["pct"] = df_classe["valor_atual"] / total if total > 0 else 0

        fig_classe = go.Figure(go.Pie(
            labels=df_classe["classe"].fillna("Outros"),
            values=df_classe["valor_atual"],
            hole=0.4,
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>%{value:,.2f}<br>%{percent}<extra></extra>",
        ))
        fig_classe.update_layout(
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            showlegend=True,
            legend=dict(orientation="v", x=1.0, y=0.5),
            margin=dict(t=10, b=10, l=10, r=140),
        )
        st.plotly_chart(fig_classe, use_container_width=True, config={"responsive": True})

        rows_classe = []
        for _, r in df_classe.iterrows():
            rows_classe.append({
                "Classe": r["classe"] or "Outros",
                "Valor": fmt.moeda(r["valor_atual"]),
                "% Gerida": fmt.pct(r["pct"]),
            })
        st.dataframe(pd.DataFrame(rows_classe), use_container_width=True, hide_index=True)

    st.divider()

    # ─── Exposição por bloco IPS ─────────────────────────────────────────
    st.subheader("Exposição por Bloco IPS")
    df_bloco = (
        df.groupby(df["bloco_ips"].fillna("—"), dropna=False)["valor_atual"]
        .sum()
        .reset_index()
        .rename(columns={"bloco_ips": "bloco"})
        .sort_values("valor_atual", ascending=False)
    )
    df_bloco["pct"] = df_bloco["valor_atual"] / total if total > 0 else 0

    fig_bloco = go.Figure(go.Bar(
        x=df_bloco["bloco"],
        y=df_bloco["pct"],
        text=[fmt.pct(v) for v in df_bloco["pct"]],
        textposition="outside",
        marker_color="#4a9eff",
        hovertemplate="<b>%{x}</b><br>%{customdata}<br>%{y:.1%}<extra></extra>",
        customdata=[fmt.moeda(v) for v in df_bloco["valor_atual"]],
    ))
    fig_bloco.update_layout(
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,22,36,0.8)",
        font_color="white",
        xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.08)",
            tickformat=".0%",
            title="% Gerida",
        ),
        margin=dict(t=30, b=40, l=60, r=20),
    )
    st.plotly_chart(fig_bloco, use_container_width=True, config={"responsive": True})

    rows_bloco = []
    for _, r in df_bloco.iterrows():
        rows_bloco.append({
            "Bloco IPS": r["bloco"],
            "Valor": fmt.moeda(r["valor_atual"]),
            "% Gerida": fmt.pct(r["pct"]),
        })
    st.dataframe(pd.DataFrame(rows_bloco), use_container_width=True, hide_index=True)

    st.divider()

    # ─── Concentração — top 5 ─────────────────────────────────────────────
    st.subheader("Concentração — Top 5 Ativos (Carteira Gerida)")
    df_sorted = df.sort_values("valor_atual", ascending=False).head(5)
    rows_conc = []
    for _, r in df_sorted.iterrows():
        pct = r["valor_atual"] / total if total > 0 else 0
        rows_conc.append({
            "Ticker": r.get("ticker", "—"),
            "Bloco": r.get("bloco_ips") or "—",
            "Valor": fmt.moeda(r["valor_atual"]),
            "% Gerida": fmt.pct(pct),
        })
    st.dataframe(pd.DataFrame(rows_conc), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(
        "> Para análise completa de **drawdown**, **stress test** e **liquidez**, "
        "acesse o **Assistente** e pergunte: _'análise de risco da carteira'_."
    )
