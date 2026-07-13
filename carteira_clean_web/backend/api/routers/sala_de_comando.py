"""
GET /api/v1/sala-de-comando — endpoint agregador para a home do app.

Retorna em uma chamada: KPIs, teses ativas, espelho comportamental,
feed de observações do motor de varredura e progress-to-goal.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from carteira_clean_web.backend.api import cache as engine_cache
from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.db.models import Tese, MetricaComportamento, ObservacaoFeed

router = APIRouter(tags=["Sala de Comando"])

# IPS alvos e bandas (Carteira Gerida)
_IPS_BANDS: dict[str, dict] = {
    "SWING_TRADE": {"alvo": 0.30, "min": 0.20, "max": 0.40},
    "GROWTH":      {"alvo": 0.20, "min": 0.10, "max": 0.30},
    "DEFENSIVOS":  {"alvo": 0.20, "min": 0.15, "max": 0.25},
    "RENDA_FIXA":  {"alvo": 0.30, "min": 0.25, "max": 0.35},
    "FORA_IPS":    {"alvo": 0.05, "min": 0.00, "max": 0.10},
}

META_R3M = 3_000_000.0
APORTE_FUNCEF_MES = 6_392.0
APORTE_GERIDA_ANO = 20_000.0   # março + outubro
APORTE_ANUAL = 12 * APORTE_FUNCEF_MES + APORTE_GERIDA_ANO


@router.get("/sala-de-comando")
def sala_de_comando(db: Session = Depends(get_db)):
    kpis = _build_kpis()
    return {
        "kpis":           kpis,
        "teses":          _build_teses(db),
        "comportamental": _build_comportamental(db, kpis),
        "observacoes":    _build_observacoes(db),
        "meta":           _build_meta(kpis),
    }


# ─── KPIs ────────────────────────────────────────────────────────────────────

def _build_kpis() -> dict:
    if not engine_cache.esta_calculado():
        return {"engine_ok": False}

    estado = engine_cache.get_estado()
    df = estado.get("df_evo")
    if df is None or df.empty:
        return {"engine_ok": False}

    import numpy as np
    ult = df.iloc[-1]
    n = len(df)

    twr_gerida = float(ult["twr_gerida"])
    twr_ann = (1 + twr_gerida) ** (252 / n) - 1 if n > 0 else 0.0

    var_dia_pct = None
    if n >= 2:
        pat_hoje = float(ult["patrimonio_total"])
        pat_d1   = float(df.iloc[-2]["patrimonio_total"])
        if pat_d1 > 0:
            var_dia_pct = round((pat_hoje - pat_d1) / pat_d1, 6)

    calc_em = engine_cache.get_calculado_em()
    return {
        "engine_ok":         True,
        "patrimonio_total":  round(float(ult["patrimonio_total"]), 2),
        "patrimonio_gerida": round(float(ult["patrimonio_gerida"]), 2),
        "patrimonio_funcef": round(float(ult["patrimonio_funcef"]), 2),
        "twr_ytd":           round(twr_gerida, 6),
        "twr_total_ytd":     round(float(ult["twr_total"]), 6),
        "cdi_ytd":           round(float(ult["cdi_acum"]), 6),
        "ibov_ytd":          round(float(ult["ibov_acum"]), 6),
        "excesso_cdi":       round(twr_gerida - float(ult["cdi_acum"]), 6),
        "twr_anualizado":    round(twr_ann, 6),
        "var_dia_pct":       var_dia_pct,
        "nivel_automacao":   "L2",
        "calculado_em":      calc_em.isoformat() if calc_em else None,
        "data_referencia":   str(ult["data"]),
    }


# ─── Teses ───────────────────────────────────────────────────────────────────

def _build_teses(db: Session) -> list[dict]:
    teses = (
        db.query(Tese)
        .filter(Tese.status == "ATIVA")
        .order_by(Tese.data_criacao.desc())
        .all()
    )
    today = date.today()
    result = []
    for t in teses:
        dias = (today - t.data_criacao).days if t.data_criacao else None
        racional_curto = (t.racional[:110] + "…") if t.racional and len(t.racional) > 110 else t.racional
        result.append({
            "id":                    t.id,
            "ticker":                t.ticker,
            "bloco_ips":             t.bloco_ips,
            "racional":              racional_curto,
            "criterio_invalidacao":  t.criterio_invalidacao,
            "nivel_invalidacao":     t.nivel_invalidacao,
            "status":                t.status,
            "dias_desde_criacao":    dias,
        })
    return result


# ─── Comportamental ──────────────────────────────────────────────────────────

def _build_comportamental(db: Session, kpis: dict) -> dict:
    # Vieses: último cálculo cacheado na tabela
    vieses: list[dict] = []
    row = (
        db.query(MetricaComportamento)
        .filter(MetricaComportamento.metrica == "vieses_comportamentais")
        .order_by(MetricaComportamento.calculado_em.desc())
        .first()
    )
    if row and row.valor_json:
        try:
            raw = json.loads(row.valor_json)
            if isinstance(raw, list):
                vieses = [
                    {
                        "nome_vies":       v.get("nome_vies", ""),
                        "detectado":       bool(v.get("detectado", False)),
                        "severidade":      v.get("severidade", "INFO"),
                        "fato_mensuravel": v.get("fato_mensuravel", ""),
                    }
                    for v in raw
                ]
        except Exception:
            pass

    # Alocação real vs IPS (Carteira Gerida)
    blocos: list[dict] = []
    if kpis.get("engine_ok"):
        blocos = _calc_blocos_ips(kpis.get("patrimonio_gerida", 0))

    # Índice de coerência: começa em 100, desconta por vieses e desvios de IPS
    score = 100
    for v in vieses:
        if v["detectado"]:
            score -= {"CRITICO": 15, "ATENCAO": 8}.get(v["severidade"], 3)
    for b in blocos:
        if b["status"] != "OK":
            score -= 10
    score = max(0, min(100, score))

    return {
        "indice_coerencia": score,
        "vieses":           vieses,
        "blocos":           blocos,
    }


def _calc_blocos_ips(pat_gerida: float) -> list[dict]:
    if pat_gerida <= 0:
        return []

    try:
        estado    = engine_cache.get_estado()
        posicoes  = estado.get("posicoes", {})
        ativos    = estado.get("ativos", {})
        precos_pub = estado.get("precos_publicos", {})
        precos_man = estado.get("precos_manuais", {})
        hoje       = estado.get("hoje")

        from carteira_clean_web.backend.engine.utils import preco_em
        from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO, AGREGADO_PRIVADO

        bloco_val: dict[str, float] = {}
        for tkr, p in posicoes.items():
            info      = ativos.get(tkr, {})
            familia   = info.get("familia", "")
            composite = info.get("composite", "Gerida")
            bloco     = info.get("bloco_ips") or "FORA_IPS"
            if composite != "Gerida":
                continue

            if familia in COTIZADO_PUBLICO:
                pr = preco_em(precos_pub.get(tkr, {}), hoje)
                if pr is None:
                    pr = preco_em(precos_man.get(tkr, {}), hoje, max_lookback_dias=60)
                valor = p.qtd * pr if pr else p.custo_total
            elif familia in AGREGADO_PRIVADO:
                pr    = preco_em(precos_man.get(tkr, {}), hoje, max_lookback_dias=60)
                valor = pr if pr else p.custo_total
            else:
                valor = p.custo_total

            bloco_val[bloco] = bloco_val.get(bloco, 0.0) + valor

        result = []
        for bloco_name, band in _IPS_BANDS.items():
            val      = bloco_val.get(bloco_name, 0.0)
            pct_real = val / pat_gerida
            if pct_real < band["min"] - 0.01:
                st = "ABAIXO"
            elif pct_real > band["max"] + 0.01:
                st = "ACIMA"
            else:
                st = "OK"
            result.append({
                "bloco":    bloco_name,
                "pct_real": round(pct_real, 4),
                "pct_alvo": band["alvo"],
                "banda_min": band["min"],
                "banda_max": band["max"],
                "status":   st,
            })
        return result
    except Exception:
        return []


# ─── Observações — feed do motor de varredura ───────────────────────────────

def _build_observacoes(db: Session, limit: int = 30) -> list[dict]:
    """Feed de fatos novos e relevantes (engine/varredura_feed.py) ainda não
    vistos. Cada item é rastreável a uma linha real (alerta, tese, banda IPS,
    técnico, fundamentalista, notícia ou evento macro) — nunca texto livre.
    Marcar como visto (POST .../observacoes/{id}/visualizar) remove
    permanentemente (visualizado_em preenchido sai do filtro abaixo)."""
    itens = (
        db.query(ObservacaoFeed)
        .filter(ObservacaoFeed.visualizado_em.is_(None))
        .order_by(ObservacaoFeed.criado_em.desc())
        .limit(limit)
        .all()
    )
    result = []
    for o in itens:
        ativos_relacionados: list[str] = []
        if o.ativo:
            ativos_relacionados.append(o.ativo)
        url = None
        if o.fundamentos_json:
            try:
                extra = json.loads(o.fundamentos_json)
                if o.categoria == "MACRO":
                    for a in extra.get("ativos_carteira_afetados", []):
                        tkr = a.get("ticker")
                        if tkr and tkr not in ativos_relacionados:
                            ativos_relacionados.append(tkr)
                elif o.categoria == "NOTICIA":
                    url = extra.get("url")
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        result.append({
            "id":                  o.id,
            "categoria":           o.categoria,
            "ativo":               o.ativo,
            "ativos_relacionados": ativos_relacionados,
            "conteudo":            o.conteudo,
            "url":                 url,
            "criado_em":           o.criado_em.isoformat() if o.criado_em else None,
        })
    return result


@router.post("/sala-de-comando/observacoes/{obs_id}/visualizar")
def marcar_observacao_visualizada(obs_id: int, db: Session = Depends(get_db)):
    obs = db.get(ObservacaoFeed, obs_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observação não encontrada.")
    obs.visualizado_em = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": obs_id}


# ─── Meta R$3M ───────────────────────────────────────────────────────────────

def _build_meta(kpis: dict) -> dict:
    if not kpis.get("engine_ok"):
        return {"engine_ok": False}

    pat_atual     = kpis["patrimonio_total"]
    twr_anualizado = kpis["twr_anualizado"]

    # Projeção: simula até atingir R$3M
    ano_atual = date.today().year
    pat_proj  = pat_atual
    ano_meta  = None
    for offset in range(1, 31):
        pat_proj = pat_proj * (1 + twr_anualizado) + APORTE_ANUAL
        if pat_proj >= META_R3M:
            ano_meta = ano_atual + offset
            break

    # Ritmo mensal necessário para atingir em 10 anos
    anos_restantes = max(1, 10 - (ano_atual - 2020))  # âncora: início ~2020
    meses_restantes = anos_restantes * 12
    # FV = PV*(1+r)^n + PMT * ((1+r)^n - 1)/r  → resolver PMT
    r = twr_anualizado / 12
    fator = (1 + r) ** meses_restantes
    if r > 0:
        ritmo_mensal = max(0, (META_R3M - pat_atual * fator) * r / (fator - 1))
    else:
        ritmo_mensal = max(0, (META_R3M - pat_atual) / meses_restantes)

    return {
        "patrimonio_atual":    round(pat_atual, 2),
        "meta":                META_R3M,
        "pct_atingido":        round(pat_atual / META_R3M, 4),
        "twr_anualizado":      round(twr_anualizado, 6),
        "aporte_anual":        APORTE_ANUAL,
        "projecao_ano_meta":   ano_meta,
        "ritmo_mensal_atual":  round(APORTE_ANUAL / 12, 2),
        "ritmo_mensal_necessario": round(ritmo_mensal, 2),
    }
