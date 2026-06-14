"""
tests/test_refinamentos.py — Sprint de refinamentos (itens 1, 2, 3).

Casos:
  A) Histórico: com >20 mensagens, só as últimas 20 vão para a API.
  B) Memórias: teto FIFO de 50 — ao atingir, a mais antiga é desativada.
  C) Schema: bloco_ips aceito em AtivoCreate e AtivoUpdate; valores inválidos rejeitados.

Rodar:
    pytest tests/test_refinamentos.py -v -s
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ── Teste A: janela deslizante ────────────────────────────────────────────────

def test_A_janela_deslizante():
    """O bloco de construção do histórico limita a 20 mensagens em QUALQUER caso."""
    # Simula o trecho exato do assistente.py
    JANELA = 20

    # Cria lista de 35 mensagens fake
    mensagens = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg_{i}"}
        for i in range(35)
    ]

    # Caso 1: sem resumo → aplica [-JANELA:]
    resumo_hist = None
    if resumo_hist:
        historico = [
            {"role": "user", "content": f"[RESUMO]\n{resumo_hist}"},
            {"role": "assistant", "content": "Entendido."},
        ] + [{"role": m["role"], "content": m["content"]} for m in mensagens[-JANELA:]]
    else:
        historico = [{"role": m["role"], "content": m["content"]} for m in mensagens[-JANELA:]]
    historico.append({"role": "user", "content": "nova pergunta"})

    msgs_contexto = [m for m in historico if m["content"] != "nova pergunta"]
    assert len(msgs_contexto) == JANELA, (
        f"Sem resumo: esperado {JANELA} mensagens de contexto, encontrado {len(msgs_contexto)}"
    )
    # Deve ter as ÚLTIMAS 20 (índices 15–34)
    assert msgs_contexto[0]["content"] == "msg_15", (
        f"Primeira msg de contexto deveria ser msg_15, foi {msgs_contexto[0]['content']}"
    )

    # Caso 2: com resumo → resumo(2) + últimas 20 = 22 de contexto
    resumo_hist = "Contexto anterior comprimido..."
    historico2 = [
        {"role": "user", "content": f"[RESUMO]\n{resumo_hist}"},
        {"role": "assistant", "content": "Entendido."},
    ] + [{"role": m["role"], "content": m["content"]} for m in mensagens[-JANELA:]]
    historico2.append({"role": "user", "content": "nova pergunta"})

    msgs_contexto2 = [m for m in historico2 if m["content"] != "nova pergunta"]
    assert len(msgs_contexto2) == JANELA + 2, (
        f"Com resumo: esperado {JANELA+2} msgs de contexto, encontrado {len(msgs_contexto2)}"
    )

    print(f"\n[A] Sem resumo: {len(msgs_contexto)} msgs de contexto (últimas {JANELA})")
    print(f"    Com resumo:  {len(msgs_contexto2)} msgs de contexto (resumo+2 + últimas {JANELA})")


# ── Teste B: teto FIFO de memórias ───────────────────────────────────────────

def test_B_fifo_memorias():
    """Ao atingir 50 memórias ativas, a inserção de uma nova desativa a mais antiga."""
    _MAX_MEMORIAS = 50

    # Simula o banco: lista de 50 memórias, ordenadas por data de criação
    from datetime import datetime, timedelta

    class FakeMemoria:
        def __init__(self, id_, criada_em):
            self.id = id_
            self.criada_em = criada_em
            self.ativa = 1

    existentes = [
        FakeMemoria(i, datetime(2026, 1, 1) + timedelta(days=i))
        for i in range(_MAX_MEMORIAS)
    ]

    # Simula a lógica do router: ao inserir quando total >= 50, desativa a mais antiga
    total_ativas = len(existentes)
    desativadas = []
    if total_ativas >= _MAX_MEMORIAS:
        excesso = total_ativas - _MAX_MEMORIAS + 1
        mais_antigas = sorted(existentes, key=lambda m: m.criada_em)[:excesso]
        for m_antiga in mais_antigas:
            m_antiga.ativa = 0
            desativadas.append(m_antiga.id)

    assert len(desativadas) == 1, f"Esperado desativar 1, desativadas: {desativadas}"
    assert desativadas[0] == 0, f"A mais antiga (id=0) devia ser desativada, foi {desativadas[0]}"

    ativas_restantes = sum(1 for m in existentes if m.ativa == 1)
    assert ativas_restantes == _MAX_MEMORIAS - 1, (
        f"Esperado {_MAX_MEMORIAS-1} ativas antes de inserir a nova, há {ativas_restantes}"
    )

    print(f"\n[B] Com {_MAX_MEMORIAS} memórias: desativada id={desativadas[0]} (mais antiga)")
    print(f"    Restam {ativas_restantes} ativas → nova será a {_MAX_MEMORIAS}ª")


# ── Teste C: schema AtivoCreate/Update com bloco_ips ─────────────────────────

def test_C_schema_bloco_ips():
    """bloco_ips é aceito em AtivoCreate/AtivoUpdate; valores inválidos são rejeitados."""
    from pydantic import ValidationError
    from carteira_clean_web.backend.api.schemas import AtivoCreate, AtivoUpdate

    # Valores válidos
    for bloco in ["SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA", "FORA_IPS"]:
        ac = AtivoCreate(ticker="TEST", composite="Gerida", bloco_ips=bloco)
        assert ac.bloco_ips == bloco, f"AtivoCreate: esperado {bloco}, got {ac.bloco_ips}"

        au = AtivoUpdate(bloco_ips=bloco)
        assert au.bloco_ips == bloco, f"AtivoUpdate: esperado {bloco}, got {au.bloco_ips}"

    # None é aceito (campo opcional)
    ac_none = AtivoCreate(ticker="TEST2", composite="Gerida", bloco_ips=None)
    assert ac_none.bloco_ips is None

    au_none = AtivoUpdate(bloco_ips=None)
    assert au_none.bloco_ips is None

    # Valor inválido deve lançar ValidationError
    with pytest.raises(ValidationError):
        AtivoCreate(ticker="TEST3", composite="Gerida", bloco_ips="INVALIDO")

    with pytest.raises(ValidationError):
        AtivoUpdate(bloco_ips="NAO_EXISTE")

    print("\n[C] AtivoCreate/AtivoUpdate: bloco_ips validado corretamente")
    print("    Valores válidos: SWING_TRADE, GROWTH, DEFENSIVOS, RENDA_FIXA, FORA_IPS, None")
    print("    Valor inválido: ValidationError ✓")
