"""
Testes Peça B — calc_concentracao_setorial.

Sem DB, sem API, sem cache. Dados 100% sintéticos.
"""

import pytest
from carteira_clean_web.backend.engine.aderencia_ips import calc_concentracao_setorial


def _pos(bloco, setor, valor, composite="Gerida"):
    return {"composite": composite, "bloco_ips": bloco, "setor": setor, "valor_atual": valor}


# ── A ─────────────────────────────────────────────────────────────────────────

def test_A_concentracao_bloco_correto():
    """Pesos calculados refletem valores reais; estrutura de saída completa."""
    posicoes = [
        _pos("SWING_TRADE", "Energia Elétrica", 3000),
        _pos("GROWTH",      "Bens de Capital",  2000),
        _pos("DEFENSIVOS",  "Commodities (Ouro)", 2000),
        _pos("RENDA_FIXA",  "Governo Federal",  3000),
    ]
    resultado = calc_concentracao_setorial(posicoes)

    # 4 blocos retornados
    assert len(resultado) == 4

    by_bloco = {r["bloco_ips"]: r for r in resultado}

    # ST = 3000/10000 = 30% → no alvo
    st = by_bloco["SWING_TRADE"]
    assert st["w_real_pct"] == 30.0
    assert st["w_alvo_pct"] == 30.0
    assert st["desvio_pp"] == 0.0
    assert st["status"] == "dentro"
    assert st["banda_inf_pct"] == 20.0
    assert st["banda_sup_pct"] == 40.0

    # GROWTH = 2000/10000 = 20% → no alvo
    gr = by_bloco["GROWTH"]
    assert gr["w_real_pct"] == 20.0
    assert gr["desvio_pp"] == 0.0
    assert gr["status"] == "dentro"

    # Cada bloco tem lista de setores com campos obrigatórios
    for r in resultado:
        assert "setores" in r
        for s in r["setores"]:
            assert "setor" in s
            assert "valor" in s
            assert "w_bloco_pct" in s
            assert "w_carteira_pct" in s
            assert "indice_referencia" in s


# ── B ─────────────────────────────────────────────────────────────────────────

def test_B_status_dentro_banda():
    """Bloco acima do alvo mas dentro da banda → status 'dentro'."""
    # ST = 3500/10000 = 35% (alvo 30%, banda 20–40%)
    posicoes = [
        _pos("SWING_TRADE", "Varejo",           3500),
        _pos("GROWTH",      "Bens de Capital",  2000),
        _pos("DEFENSIVOS",  "Commodities (Ouro)", 2000),
        _pos("RENDA_FIXA",  "Governo Federal",  2500),
    ]
    resultado = calc_concentracao_setorial(posicoes)
    by_bloco = {r["bloco_ips"]: r for r in resultado}

    st = by_bloco["SWING_TRADE"]
    assert st["w_real_pct"] == 35.0
    assert st["desvio_pp"] == 5.0
    assert st["status"] == "dentro"


# ── C ─────────────────────────────────────────────────────────────────────────

def test_C_status_fora_banda():
    """Bloco 6pp acima da banda superior → status 'fora_superior'."""
    # GROWTH = 3600/10000 = 36% > banda_sup 30%
    posicoes = [
        _pos("SWING_TRADE", "Energia Elétrica",   2600),
        _pos("GROWTH",      "Aeroespacial e Defesa", 3600),
        _pos("DEFENSIVOS",  "Commodities (Ouro)",  2000),
        _pos("RENDA_FIXA",  "Governo Federal",     1800),
    ]
    resultado = calc_concentracao_setorial(posicoes)
    by_bloco = {r["bloco_ips"]: r for r in resultado}

    gr = by_bloco["GROWTH"]
    assert gr["w_real_pct"] == 36.0
    assert gr["desvio_pp"] == 16.0     # 36 - 20 = 16pp acima do alvo
    assert gr["status"] == "fora_superior"

    # Deve ser o primeiro (maior desvio absoluto)
    assert resultado[0]["bloco_ips"] == "GROWTH"


# ── D ─────────────────────────────────────────────────────────────────────────

def test_D_setor_sem_indice():
    """Setores sem mapeamento B3 retornam indice_referencia: None."""
    posicoes = [
        _pos("SWING_TRADE", "Saúde",    1500),
        _pos("SWING_TRADE", "Educação", 1500),
        _pos("GROWTH",      "Bens de Capital",    2000),
        _pos("DEFENSIVOS",  "Commodities (Ouro)", 2000),
        _pos("RENDA_FIXA",  "Governo Federal",    3000),
    ]
    resultado = calc_concentracao_setorial(posicoes)
    by_bloco = {r["bloco_ips"]: r for r in resultado}

    st_setores = {s["setor"]: s for s in by_bloco["SWING_TRADE"]["setores"]}
    assert st_setores["Saúde"]["indice_referencia"] is None
    assert st_setores["Educação"]["indice_referencia"] is None

    # Setores com mapeamento retornam string não-nula
    bk_setores = {s["setor"]: s for s in by_bloco["GROWTH"]["setores"]}
    assert bk_setores["Bens de Capital"]["indice_referencia"] == "IDX_INDX"

    # Posições FUNCEF são ignoradas
    posicoes_com_funcef = posicoes + [_pos("SWING_TRADE", "Bancos Tradicionais", 9999, composite="FUNCEF")]
    resultado2 = calc_concentracao_setorial(posicoes_com_funcef)
    by_bloco2 = {r["bloco_ips"]: r for r in resultado2}
    # ST ainda 30% (FUNCEF não entra)
    assert by_bloco2["SWING_TRADE"]["w_real_pct"] == 30.0
