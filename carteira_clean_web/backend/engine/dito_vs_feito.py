"""
engine/dito_vs_feito.py — Cruzamento dito-vs-feito (Fatia 9).

Cruza declarações (IPS, teses, diário de decisão) com comportamento real
(Fatia 8) e retorna divergências como fatos — sem juízo, sem recomendações.

Cada divergência tem: descricao, fonte_dito, fonte_feito, severidade.
Severidade: INFO | ATENCAO | CRITICO.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import mean

from carteira_clean_web.backend.engine.aderencia_ips import _IPS

_HORIZONTE_BLOCO: dict[str, dict] = {
    "SWING_TRADE": {"label": "semanas a meses",   "min": 7,   "max": 180},
    "GROWTH":      {"label": "multi-ano",          "min": 365, "max": None},
    "DEFENSIVOS":  {"label": "médio-longo prazo",  "min": 180, "max": None},
    "RENDA_FIXA":  {"label": "até vencimento",     "min": 0,   "max": None},
}

Divergencia = dict  # descricao, fonte_dito, fonte_feito, severidade, tipo


def _div(tipo: str, desc: str, dito: str, feito: str, sev: str) -> Divergencia:
    return {"tipo": tipo, "descricao": desc,
            "fonte_dito": dito, "fonte_feito": feito, "severidade": sev}


# ─── Cruzamento 1: horizonte declarado vs holding period real ────────────────

def cruzar_horizonte_holding(holding_por_bloco: dict) -> list[Divergencia]:
    """
    Compara o horizonte declarado no IPS (min/max dias) com o holding period
    real calculado pela Fatia 8.
    """
    divs: list[Divergencia] = []
    for bloco, dados in holding_por_bloco.items():
        media = dados.get("media_dias")
        if media is None:
            continue
        h = _HORIZONTE_BLOCO.get(bloco, {})
        min_d = h.get("min", 0)
        max_d = h.get("max")
        label = h.get("label", "—")

        n_ab = dados.get("n_abertas", 0)
        n_enc = dados.get("n_encerradas", 0)

        if max_d and media > max_d:
            sev = "ATENCAO"
            desc = (f"Bloco {bloco}: holding period médio = {int(media)} dias, "
                    f"acima do máximo declarado ({max_d} dias / horizonte: {label}).")
        elif min_d > 30 and media < min_d:
            if n_enc == 0:
                # Posições abertas recentes, sem venda — pode ser acumulação, não giro.
                sev = "INFO"
                desc = (f"Bloco {bloco}: holding period médio = {int(media)} dias "
                        f"({n_ab} posições abertas, nenhuma encerrada). "
                        f"Horizonte declarado: {label} ({min_d}+ dias). "
                        f"Nenhum ativo foi vendido ainda — monitorar à medida que o tempo passa.")
            else:
                sev = "CRITICO" if bloco == "GROWTH" and media < 90 else "ATENCAO"
                desc = (f"Bloco {bloco}: holding period médio = {int(media)} dias "
                        f"({n_enc} posições encerradas), abaixo do mínimo declarado "
                        f"({min_d} dias / horizonte: {label}).")
        else:
            continue

        divs.append(_div(
            "horizonte", desc,
            dito=f"IPS — bloco {bloco}: {label}",
            feito=f"event log — {n_ab} posições abertas, {n_enc} encerradas",
            sev=sev,
        ))
    return divs


# ─── Cruzamento 2: alocação declarada vs concentração real ──────────────────

def cruzar_alocacao_ips(blocos_ips: list[dict]) -> list[Divergencia]:
    """
    Usa o resultado de calc_concentracao_setorial (Fatia 1 / aderencia_ips.py).
    Reporta blocos fora da banda IPS.
    """
    divs: list[Divergencia] = []
    for b in blocos_ips:
        if b["status"] == "dentro":
            continue
        bloco = b["bloco_ips"]
        w_real = b["w_real_pct"]
        w_alvo = b["w_alvo_pct"]
        desvio = b["desvio_pp"]
        b_inf = b["banda_inf_pct"]
        b_sup = b["banda_sup_pct"]
        direcao = "acima" if b["status"] == "fora_superior" else "abaixo"
        sev = "CRITICO" if abs(desvio) > 10 else "ATENCAO"
        desc = (f"Bloco {bloco}: alocação real {w_real}% — {direcao} da banda IPS "
                f"({b_inf}%–{b_sup}%). Alvo: {w_alvo}%. Desvio: {desvio:+.1f}pp.")
        divs.append(_div(
            "alocacao", desc,
            dito=f"IPS — alvo {w_alvo}%, banda {b_inf}%–{b_sup}%",
            feito=f"posições atuais — {w_real}% do patrimônio Gerida",
            sev=sev,
        ))
    return divs


# ─── Cruzamento 3: convicção declarada vs resultado real ────────────────────

def cruzar_conviccao_resultado(
    decisoes: list[dict],
    preco_atual: dict[str, float],
) -> list[Divergencia]:
    """
    Compara convicção registrada no diário com o resultado % real
    (preço_atual / preco_entrada − 1).
    Só avalia COMPRA e AUMENTO com preco_entrada preenchido.
    """
    grupos: dict[str, list[float]] = {"alta": [], "media": [], "baixa": []}
    sem_preco = 0

    for d in decisoes:
        if d.get("acao") not in ("COMPRA", "AUMENTO"):
            continue
        pe = d.get("preco_entrada")
        ticker = d.get("ticker")
        conv = d.get("conviccao", 3)
        if not pe or not ticker:
            continue
        pa = preco_atual.get(ticker)
        if not pa:
            sem_preco += 1
            continue
        ret = (pa / pe - 1) * 100
        if conv >= 4:
            grupos["alta"].append(ret)
        elif conv == 3:
            grupos["media"].append(ret)
        else:
            grupos["baixa"].append(ret)

    resumo = {
        g: {"n": len(rs), "resultado_medio_pct": round(mean(rs), 1)}
        for g, rs in grupos.items() if rs
    }

    divs: list[Divergencia] = []

    if "alta" in resumo and "baixa" in resumo:
        alta_med = resumo["alta"]["resultado_medio_pct"]
        baixa_med = resumo["baixa"]["resultado_medio_pct"]
        if baixa_med > alta_med + 5:
            desc = (f"Operações com convicção baixa (1-2): resultado médio {baixa_med:+.1f}% "
                    f"({resumo['baixa']['n']} ops). Convicção alta (4-5): {alta_med:+.1f}% "
                    f"({resumo['alta']['n']} ops). Diferença: {baixa_med - alta_med:.1f}pp.")
            divs.append(_div(
                "conviccao", desc,
                dito="diário de decisões — campo convicção 1-5",
                feito="preço atual vs preço de entrada registrado",
                sev="ATENCAO",
            ))

    if resumo:
        partes = "; ".join(
            f"conv {g}: {d['resultado_medio_pct']:+.1f}% ({d['n']} ops)"
            for g, d in resumo.items()
        )
        desc_info = f"Resultado médio por convicção — {partes}."
        if sem_preco:
            desc_info += f" ({sem_preco} decisões sem preço de entrada ignoradas.)"
        if not divs:
            divs.append(_div(
                "conviccao", desc_info,
                dito="diário de decisões — campo convicção",
                feito="preço atual vs preço de entrada (cotações em cache)",
                sev="INFO",
            ))

    return divs


# ─── Cruzamento 4: critério de invalidação vs estado atual das teses ─────────

def cruzar_invalidacao_teses(teses: list[dict], hoje: date | None = None) -> list[Divergencia]:
    """
    Identifica teses ATIVAS com nível de invalidação elevado ou sem revisão recente.
    Não avalia automaticamente o conteúdo do critério (tarefa do maestro).
    """
    if hoje is None:
        hoje = date.today()
    divs: list[Divergencia] = []

    for t in teses:
        if t.get("status") != "ATIVA":
            continue
        nivel = t.get("nivel_invalidacao", "VERDE")
        criterio = (t.get("criterio_invalidacao") or "").strip()
        ticker = t.get("ticker", "?")
        tese_id = t.get("id", "?")
        dt_criacao = t.get("data_criacao")
        dt_upd = t.get("data_atualizacao") or dt_criacao

        if nivel == "VERMELHO":
            divs.append(_div(
                "invalidacao",
                f"Tese #{tese_id} de {ticker} em nível VERMELHO. Critério: \"{criterio}\".",
                dito=f"teses — id {tese_id}, criada {dt_criacao}",
                feito="nível_invalidacao = VERMELHO (atualizado manualmente)",
                sev="CRITICO",
            ))
        elif nivel == "AMARELO":
            divs.append(_div(
                "invalidacao",
                f"Tese #{tese_id} de {ticker} em nível AMARELO. Critério: \"{criterio}\".",
                dito=f"teses — id {tese_id}",
                feito="nível_invalidacao = AMARELO",
                sev="ATENCAO",
            ))
        elif criterio:
            try:
                dt = date.fromisoformat(str(dt_upd))
                dias = (hoje - dt).days
                if dias > 90:
                    divs.append(_div(
                        "invalidacao",
                        (f"Tese #{tese_id} de {ticker} não revisada há {dias} dias. "
                         f"Critério: \"{criterio}\"."),
                        dito=f"teses — id {tese_id}, última atualização: {dt_upd}",
                        feito=f"data atual: {hoje}",
                        sev="INFO",
                    ))
            except (ValueError, TypeError):
                pass

    return divs
