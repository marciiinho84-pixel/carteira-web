"""
tests/test_brinson.py — Brinson-Fachler decomposition (Etapa 4).

Casos:
  A) Cálculo sintético 4 blocos: efeito_alocacao e efeito_selecao vs valor manual.
  B) Identidade: sum(A+S) = excesso de retorno (tolerância 0.05pp) — sem FORA_IPS.
  C) Endpoint: DataFrame retorna colunas e tipos corretos; filtros funcionam.
  D) Bloco com w_real=0: efeito_alocacao = -w_alvo*(R_bench-R_bench_total), selecao=0.
  E) FORA_IPS excluído: não aparece como linha de bloco no df_bf.

Rodar:
    pytest tests/test_brinson.py -v -s
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine.brinson import calc_brinson_fachler, _IPS_ALVOS
from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO
from carteira_clean_web.backend.engine.utils import bdate_range

_FAM = next(iter(COTIZADO_PUBLICO))

# ── Fixture auxiliar: monta um df_atrib sintético ───────────────────────────

def _make_df_atrib(rows: list) -> pd.DataFrame:
    """Cria um df_atrib no mesmo formato que calc_atribuicao_mensal retorna."""
    return pd.DataFrame(rows)


def _atrib_row(mes, ativo, bloco, w, contrib, composite="Gerida"):
    """Linha individual de ativo."""
    return {
        "mes": mes,
        "composite": composite,
        "ativo": ativo,
        "retorno_ativo": contrib / w if w > 0 else 0.0,
        "peso_medio": w,
        "contribuicao": contrib,
        "benchmark": "IBOV",
        "bloco_ips": bloco,
    }


def _total_row(mes, composite, contrib):
    return {
        "mes": mes,
        "composite": composite,
        "ativo": "TOTAL",
        "retorno_ativo": contrib,
        "peso_medio": 1.0,
        "contribuicao": contrib,
        "benchmark": "30%IBOV+20%NasdaqBRL+20%OuroBRL+30%CDI",
        "bloco_ips": None,
    }


# ── Mock: calc_brinson_fachler sem bater na tabela benchmarks ────────────────
#
# Monkey-patch _retornos_mensais para retornar valores sintéticos controlados.

_BENCH_SINTETICO = {
    "CDI":        0.010,   # +1.0% no mês
    "IBOV":       0.050,   # +5.0%
    "NASDAQ_BRL": 0.080,   # +8.0%
    "OURO_BRL":   0.030,   # +3.0%
}

# R_bench_total = 0.30×0.05 + 0.20×0.08 + 0.20×0.03 + 0.30×0.01
# = 0.015 + 0.016 + 0.006 + 0.003 = 0.040
_R_BENCH_TOTAL_ESPERADO = (
    _IPS_ALVOS["SWING_TRADE"] * _BENCH_SINTETICO["IBOV"]
    + _IPS_ALVOS["GROWTH"]      * _BENCH_SINTETICO["NASDAQ_BRL"]
    + _IPS_ALVOS["DEFENSIVOS"]  * _BENCH_SINTETICO["OURO_BRL"]
    + _IPS_ALVOS["RENDA_FIXA"]  * _BENCH_SINTETICO["CDI"]
)


@pytest.fixture(autouse=True)
def patch_retornos(monkeypatch):
    """Substitui a leitura da tabela benchmarks por valores sintéticos."""
    import carteira_clean_web.backend.engine.brinson as _mod

    def _mock_retornos(benchmarks, mes_str, datas_uteis, idx_map):
        return dict(_BENCH_SINTETICO)

    monkeypatch.setattr(_mod, "_retornos_mensais", _mock_retornos)
    monkeypatch.setattr(_mod, "carregar_benchmarks_da_tabela", lambda: {})


# ── Dados sintéticos comuns ──────────────────────────────────────────────────
MES = "2026-05"

# Pesos e contribuições por bloco (sem FORA_IPS)
# SWING_TRADE: w_real=0.32, R_real=0.06  → contrib=0.32×0.06=0.0192
# GROWTH:      w_real=0.18, R_real=0.10  → contrib=0.18×0.10=0.0180
# DEFENSIVOS:  w_real=0.22, R_real=0.02  → contrib=0.22×0.02=0.0044
# RENDA_FIXA:  w_real=0.28, R_real=0.012 → contrib=0.28×0.012=0.00336

_BLOCOS = {
    "SWING_TRADE": {"w": 0.32, "R": 0.060},
    "GROWTH":      {"w": 0.18, "R": 0.100},
    "DEFENSIVOS":  {"w": 0.22, "R": 0.020},
    "RENDA_FIXA":  {"w": 0.28, "R": 0.012},
}

_R_REAL_GERIDA = sum(b["w"] * b["R"] for b in _BLOCOS.values())


def _make_df_sintetico(incluir_fora_ips=False):
    rows = []
    for bloco, v in _BLOCOS.items():
        rows.append(_atrib_row(MES, f"ATIVO_{bloco}", bloco, v["w"], v["w"] * v["R"]))

    if incluir_fora_ips:
        rows.append(_atrib_row(MES, "CAIXA", "FORA_IPS", 0.05, 0.05 * 0.008))

    contrib_total = sum(r["contribuicao"] for r in rows if r["composite"] == "Gerida")
    rows.append(_total_row(MES, "Gerida", contrib_total))
    rows.append(_total_row(MES, "TOTAL_CARTEIRA", contrib_total))
    return _make_df_atrib(rows)


# ── Teste A: cálculo vs manual ───────────────────────────────────────────────

def test_A_calculo_manual():
    """Efeito alocação e seleção de cada bloco devem bater com cálculo manual."""
    df_atrib = _make_df_sintetico()
    df = calc_brinson_fachler(df_atrib, data_fim=date(2026, 5, 29))

    blocos_df = df[df["bloco_ips"] != "TOTAL"]
    assert len(blocos_df) == 4, f"Esperado 4 blocos, encontrado {len(blocos_df)}"

    R_bt = _R_BENCH_TOTAL_ESPERADO

    for bloco, v in _BLOCOS.items():
        w_real = v["w"]
        w_alvo = _IPS_ALVOS[bloco]
        R_real = v["R"]
        R_bench_b = {
            "SWING_TRADE": _BENCH_SINTETICO["IBOV"],
            "GROWTH":      _BENCH_SINTETICO["NASDAQ_BRL"],
            "DEFENSIVOS":  _BENCH_SINTETICO["OURO_BRL"],
            "RENDA_FIXA":  _BENCH_SINTETICO["CDI"],
        }[bloco]

        A_esperado = (w_real - w_alvo) * (R_bench_b - R_bt)
        S_esperado = w_real * (R_real - R_bench_b)

        row = blocos_df[blocos_df["bloco_ips"] == bloco].iloc[0]
        assert abs(row["efeito_alocacao"] - A_esperado) < 1e-9, (
            f"{bloco}: A={row['efeito_alocacao']:.6f} esperado={A_esperado:.6f}"
        )
        assert abs(row["efeito_selecao"] - S_esperado) < 1e-9, (
            f"{bloco}: S={row['efeito_selecao']:.6f} esperado={S_esperado:.6f}"
        )

    print(f"\n[A] R_bench_total={R_bt*100:.3f}%  R_real_gerida={_R_REAL_GERIDA*100:.3f}%")
    print(blocos_df[["bloco_ips", "efeito_alocacao", "efeito_selecao"]].to_string(index=False))


# ── Teste B: identidade sum(A+S) = excesso ───────────────────────────────────

def test_B_identidade_excesso():
    """Sem FORA_IPS, sum(A+S) = R_real - R_bench_total (tolerância 0.05pp)."""
    df_atrib = _make_df_sintetico(incluir_fora_ips=False)
    df = calc_brinson_fachler(df_atrib, data_fim=date(2026, 5, 29))

    tot = df[(df["bloco_ips"] == "TOTAL") & (df["mes"] == MES)].iloc[0]
    soma_bf = tot["efeito_alocacao"] + tot["efeito_selecao"]

    excesso_esperado = _R_REAL_GERIDA - _R_BENCH_TOTAL_ESPERADO
    diff = abs(soma_bf - excesso_esperado)

    print(f"\n[B] soma_BF={soma_bf*100:+.4f}pp  excesso={excesso_esperado*100:+.4f}pp  diff={diff*100:.6f}pp")
    assert diff < 0.0005, (
        f"Identidade violada: soma_BF={soma_bf:.6f} excesso={excesso_esperado:.6f} diff={diff:.6f}"
    )


# ── Teste C: estrutura do DataFrame e filtros ─────────────────────────────────

def test_C_estrutura_e_filtros():
    """Colunas obrigatórias presentes; filtros por mes e bloco_ips funcionam."""
    df_atrib = _make_df_sintetico()
    df = calc_brinson_fachler(df_atrib, data_fim=date(2026, 5, 29))

    colunas_obrig = {
        "mes", "bloco_ips", "w_real", "w_alvo",
        "R_real_bloco", "R_bench_bloco", "R_bench_total",
        "efeito_alocacao", "efeito_selecao",
    }
    assert colunas_obrig.issubset(set(df.columns)), (
        f"Colunas ausentes: {colunas_obrig - set(df.columns)}"
    )

    # Filtro por mes
    df_maio = df[df["mes"] == MES]
    assert not df_maio.empty, "Filtro por mes falhou"
    assert set(df_maio["bloco_ips"].unique()) == {"SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA", "TOTAL"}

    # Filtro por bloco
    df_growth = df[df["bloco_ips"] == "GROWTH"]
    assert len(df_growth) == 1, f"Filtro por bloco retornou {len(df_growth)} linhas (esperado 1)"

    # Tipos numéricos
    for col in ["w_real", "w_alvo", "efeito_alocacao", "efeito_selecao"]:
        assert pd.api.types.is_float_dtype(df[col]), f"{col} deve ser float"

    print(f"\n[C] colunas: {list(df.columns)}  n_rows={len(df)}")


# ── Teste D: bloco com w_real=0 ──────────────────────────────────────────────

def test_D_bloco_sem_posicao():
    """Bloco com peso real zero: A = -w_alvo*(R_bench-R_bench_total), S = 0."""
    # Remove SWING_TRADE (peso=0)
    blocos_parcial = {k: v for k, v in _BLOCOS.items() if k != "SWING_TRADE"}
    rows = [
        _atrib_row(MES, f"ATIVO_{bloco}", bloco, v["w"], v["w"] * v["R"])
        for bloco, v in blocos_parcial.items()
    ]
    contrib_total = sum(r["contribuicao"] for r in rows)
    rows.append(_total_row(MES, "Gerida", contrib_total))
    rows.append(_total_row(MES, "TOTAL_CARTEIRA", contrib_total))
    df_atrib = _make_df_atrib(rows)

    df = calc_brinson_fachler(df_atrib, data_fim=date(2026, 5, 29))

    swing_row = df[df["bloco_ips"] == "SWING_TRADE"].iloc[0]
    w_alvo_swing = _IPS_ALVOS["SWING_TRADE"]
    R_bench_ibov  = _BENCH_SINTETICO["IBOV"]
    R_bench_total = _R_BENCH_TOTAL_ESPERADO

    A_esperado = (0 - w_alvo_swing) * (R_bench_ibov - R_bench_total)
    S_esperado = 0.0

    assert abs(swing_row["w_real"] - 0.0) < 1e-9, "w_real deve ser 0"
    assert abs(swing_row["efeito_alocacao"] - A_esperado) < 1e-9, (
        f"A={swing_row['efeito_alocacao']:.6f} esperado={A_esperado:.6f}"
    )
    assert abs(swing_row["efeito_selecao"] - S_esperado) < 1e-9, "S deve ser 0 quando w_real=0"

    print(f"\n[D] SWING_TRADE (w=0): A={swing_row['efeito_alocacao']*100:+.4f}pp  S={swing_row['efeito_selecao']*100:+.4f}pp")


# ── Teste E: FORA_IPS excluído das linhas de bloco ──────────────────────────

def test_E_fora_ips_excluido():
    """Ativos FORA_IPS não aparecem como linha de bloco no df_bf."""
    df_atrib = _make_df_sintetico(incluir_fora_ips=True)
    df = calc_brinson_fachler(df_atrib, data_fim=date(2026, 5, 29))

    assert "FORA_IPS" not in df["bloco_ips"].values, (
        "FORA_IPS não deve aparecer como linha de bloco no Brinson-Fachler"
    )

    blocos_ips = df[df["bloco_ips"] != "TOTAL"]["bloco_ips"].unique().tolist()
    assert set(blocos_ips) == {"SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA"}, (
        f"Blocos inesperados: {blocos_ips}"
    )

    print(f"\n[E] blocos presentes: {blocos_ips}  (FORA_IPS ausente — correto)")
