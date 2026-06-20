"""
engine/aderencia_ips.py — Concentração setorial real vs. IPS v1.0 (Peça B, Fatia 1).

Calcula exposição por bloco IPS e desvio das bandas, com quebra por setor
e mapeamento para o índice B3 de referência de cada setor.
"""

from __future__ import annotations

# ── Mapa canonical ticker → bloco IPS (38 ativos, Fatia 1 confirmado em prod) ─
# Fonte única de verdade para comportamento.py, dito_vs_feito.py e risco.py.
_BLOCO_MAP: dict[str, str] = {
    # SWING_TRADE — 20 ativos
    "ALOS3": "SWING_TRADE", "AURA33": "SWING_TRADE", "AXIA3": "SWING_TRADE",
    "AZZA3": "SWING_TRADE", "CSMG3": "SWING_TRADE", "DIVO11": "SWING_TRADE",
    "EMBJ3": "SWING_TRADE", "INBR32": "SWING_TRADE", "ITUB3": "SWING_TRADE",
    "MDNE3": "SWING_TRADE", "PETR4": "SWING_TRADE", "PLPL3": "SWING_TRADE",
    "POMO4": "SWING_TRADE", "PRIO3": "SWING_TRADE", "RDOR3": "SWING_TRADE",
    "ROXO34": "SWING_TRADE", "SEER3": "SWING_TRADE", "SMAL11": "SWING_TRADE",
    "TTEN3": "SWING_TRADE", "WEGE3": "SWING_TRADE",
    # GROWTH — 12 ativos
    "ASML34": "GROWTH", "BAER39": "GROWTH", "BOTZ39": "GROWTH",
    "BURA39": "GROWTH", "D1EL34": "GROWTH", "ETHE11": "GROWTH",
    "G1LW34": "GROWTH", "IBMB34": "GROWTH", "M2PM34": "GROWTH",
    "MSFT34": "GROWTH", "NOKI34": "GROWTH", "S2GM34": "GROWTH",
    # DEFENSIVOS — 2 ativos
    "BSLV39": "DEFENSIVOS", "CAIXA OURO": "DEFENSIVOS",
    # RENDA_FIXA — 2 ativos
    "C6 RENDA+": "RENDA_FIXA", "CAIXA LCI": "RENDA_FIXA",
    # FORA_IPS — 2 ativos
    "CAIXA FIC FUNC": "FORA_IPS", "FUNCEF": "FORA_IPS",
}

# ── IPS v1.0 — Carteira Gerida ────────────────────────────────────────────────
# Fonte: docs/IPS.md — Seção 2. Bandas exatas; não alterar sem revisão da IPS.
_IPS: dict[str, dict] = {
    "SWING_TRADE": {"alvo": 0.30, "inf": 0.20, "sup": 0.40},
    "GROWTH":      {"alvo": 0.20, "inf": 0.10, "sup": 0.30},
    "DEFENSIVOS":  {"alvo": 0.20, "inf": 0.15, "sup": 0.25},
    "RENDA_FIXA":  {"alvo": 0.30, "inf": 0.25, "sup": 0.35},
}

# Setor cadastrado em ativos.setor → índice setorial B3 na tabela benchmarks (prefixo IDX_).
# None = sem índice dedicado na B3 para esse setor.
# IDX_IMAT é proxy de materiais básicos para Commodities/Ouro — não replica ouro puro.
_SETOR_PARA_IDX: dict[str, str | None] = {
    "Energia Elétrica":     "IDX_IEE",
    "Saneamento":           "IDX_UTIL",
    "Varejo":               "IDX_ICON",
    "Bancos Tradicionais":  "IDX_IFNC",
    "Serviços Financeiros": "IDX_IFNC",
    "Construção Civil":     "IDX_IMOB",
    "Imobiliário":          "IDX_IMOB",
    "Shopping Centers":     "IDX_IMOB",
    "Bens de Capital":      "IDX_INDX",
    "Aeroespacial e Defesa":"IDX_INDX",
    "Petróleo & Gás":       "IDX_INDX",
    "Agronegócio":          "IDX_AGFS",
    "Commodities (Ouro)":   "IDX_IMAT",
    "Saúde":                None,
    "Educação":             None,
}


def calc_concentracao_setorial(posicoes: list[dict]) -> list[dict]:
    """Concentração setorial real vs. IPS v1.0 para a Carteira Gerida.

    Parâmetro
    ---------
    posicoes : list[dict]
        Uma entrada por posição com campos obrigatórios:
        ``composite``  ("Gerida" | "FUNCEF")
        ``bloco_ips``  ("SWING_TRADE" | "GROWTH" | "DEFENSIVOS" | "RENDA_FIXA" | "FORA_IPS")
        ``setor``      (string livre, ex: "Energia Elétrica")
        ``valor_atual`` (float, R$)

        Posições FUNCEF e FORA_IPS são excluídas do cálculo de peso IPS.
        O denominador é o patrimônio total da Carteira Gerida (incluindo FORA_IPS),
        de modo que os percentuais somam à fração gerida real.

    Retorna
    -------
    list[dict]  — um dict por bloco IPS, ordenado pelo maior desvio absoluto:
        bloco_ips      : str
        w_real_pct     : float   — peso real (% da Carteira Gerida total)
        w_alvo_pct     : float   — alvo da IPS
        banda_inf_pct  : float   — limite inferior da banda
        banda_sup_pct  : float   — limite superior da banda
        desvio_pp      : float   — w_real − w_alvo em pp (positivo = acima do alvo)
        status         : str     — "dentro" | "fora_superior" | "fora_inferior"
        setores        : list[dict]  — quebra por setor dentro do bloco, ordenada
                         por valor desc. Cada entrada:
                           setor, valor, w_bloco_pct, w_carteira_pct, indice_referencia
    """
    blocos_ips = set(_IPS.keys())

    # Patrimônio total Gerida (denominador) — inclui FORA_IPS
    gerida_all = [
        p for p in posicoes
        if p.get("composite") == "Gerida" and p.get("valor_atual", 0.0) > 0
    ]
    patrimonio_gerida = sum(p["valor_atual"] for p in gerida_all)
    if patrimonio_gerida <= 0:
        return []

    # Acumuladores por bloco
    blocos_valor: dict[str, float] = {b: 0.0 for b in blocos_ips}
    blocos_setores: dict[str, dict[str, float]] = {b: {} for b in blocos_ips}

    for p in gerida_all:
        bloco = p.get("bloco_ips", "")
        if bloco not in blocos_ips:
            continue
        setor = p.get("setor") or "—"
        valor = p["valor_atual"]
        blocos_valor[bloco] += valor
        blocos_setores[bloco][setor] = blocos_setores[bloco].get(setor, 0.0) + valor

    resultado: list[dict] = []
    for bloco, ips in _IPS.items():
        valor_bloco = blocos_valor[bloco]
        w_real = valor_bloco / patrimonio_gerida

        if w_real > ips["sup"]:
            status = "fora_superior"
        elif w_real < ips["inf"]:
            status = "fora_inferior"
        else:
            status = "dentro"

        setores = sorted(
            [
                {
                    "setor": s,
                    "valor": round(v, 2),
                    "w_bloco_pct": round(v / valor_bloco * 100, 1) if valor_bloco > 0 else 0.0,
                    "w_carteira_pct": round(v / patrimonio_gerida * 100, 1),
                    "indice_referencia": _SETOR_PARA_IDX.get(s),
                }
                for s, v in blocos_setores[bloco].items()
            ],
            key=lambda x: -x["valor"],
        )

        resultado.append({
            "bloco_ips":     bloco,
            "w_real_pct":    round(w_real * 100, 1),
            "w_alvo_pct":    round(ips["alvo"] * 100, 1),
            "banda_inf_pct": round(ips["inf"] * 100, 1),
            "banda_sup_pct": round(ips["sup"] * 100, 1),
            "desvio_pp":     round((w_real - ips["alvo"]) * 100, 1),
            "status":        status,
            "setores":       setores,
        })

    resultado.sort(key=lambda x: -abs(x["desvio_pp"]))
    return resultado
