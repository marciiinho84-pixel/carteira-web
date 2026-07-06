"""
engine/run.py — Ponto de entrada do engine refatorado.

Lê dados do PostgreSQL via DATABASE_URL. Retorna um dict com todos os resultados.

Uso:
    python -m backend.engine.run
    python -m backend.engine.run --no-api
    python -m backend.engine.run --verbose
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine.io import carregar_dados
from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO
from carteira_clean_web.backend.engine.precos import (
    baixar_precos_publicos, baixar_benchmarks, baixar_indices_setoriais,
    baixar_precos_tesouro, baixar_precos_cvm, calcular_saldo_lci,
    carregar_precos_da_tabela,
)
from carteira_clean_web.backend.engine.posicoes import calc_posicoes_e_vendas
from carteira_clean_web.backend.engine.inferencia import inferir_fluxos_externos_retroativos
from carteira_clean_web.backend.engine.twr import calc_evolucao_diaria, calc_twr_e_benchmarks
from carteira_clean_web.backend.engine.atribuicao import calc_atribuicao_mensal
from carteira_clean_web.backend.engine.brinson import calc_brinson_fachler
from carteira_clean_web.backend.engine.validacao import validar, validar_reconciliacao_caixa


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S",
    )


log = logging.getLogger("engine")


def run(
    no_api: bool = False,
    verbose: bool = False,
) -> dict:
    """Executa o engine completo e retorna resultados.

    Returns dict com chaves:
      ativos, eventos, precos_manuais, posicoes, vendas_rv, vendas_rf,
      proventos, aportes_inferidos, saldo_residual, df_evo, df_atrib, alertas
    """
    setup_logging(verbose)
    log.info("=" * 65)
    log.info("Carteira Clean — engine PostgreSQL")
    log.info("=" * 65)

    log.info("\n[1/6] Lendo banco PostgreSQL...")
    ativos, eventos, precos_manuais = carregar_dados()
    log.info(f"  • {len(ativos)} ativos")
    log.info(f"  • {len(eventos)} eventos")
    log.info(f"  • {sum(len(v) for v in precos_manuais.values())} pontos de preço manual")

    log.info("\n[2/6] Baixando preços externos...")
    hoje = date.today()
    from carteira_clean_web.backend.engine.constantes import DATA_INICIO
    tickers_pub = [t for t, info in ativos.items() if info.get("familia") in COTIZADO_PUBLICO]

    # Fase B: cotações e benchmarks vêm da tabela; downloads inserem lá (no_api respeita flag)
    baixar_precos_publicos(tickers_pub, DATA_INICIO, hoje, no_api)
    baixar_benchmarks(DATA_INICIO, hoje, no_api)        # insere na tabela; retorno descartado
    baixar_indices_setoriais(DATA_INICIO, hoje, no_api) # índices setoriais B3; mesmo padrão

    # Fase B: precos_publicos vem da tabela cotacoes (fonte única de verdade)
    precos_publicos = carregar_precos_da_tabela()
    n_pts = sum(len(v) for v in precos_publicos.values())
    log.info(f"  • {n_pts} pontos de preço público (tabela cotacoes)")

    # Injeta PUs do Tesouro Direto em precos_manuais (sem alterar o banco)
    precos_td = baixar_precos_tesouro(ativos, no_api)
    if precos_td:
        for tkr, serie in precos_td.items():
            if tkr not in precos_manuais:
                precos_manuais[tkr] = {}
            precos_manuais[tkr].update(serie)

    # Injeta cotas CVM (fundos com cnpj_cvm preenchido) — CVM preenche, manual tem prioridade
    cnpj_map = {t: info["cnpj_cvm"] for t, info in ativos.items() if info.get("cnpj_cvm")}
    if cnpj_map and not no_api:
        precos_cvm = baixar_precos_cvm(cnpj_map, DATA_INICIO, hoje, no_api)
        for tkr, serie in precos_cvm.items():
            if tkr not in precos_manuais:
                precos_manuais[tkr] = {}
            for dt, v in serie.items():
                precos_manuais[tkr].setdefault(dt, v)  # manual tem prioridade

    # Calcula saldo diário de LCIs/LCAs com taxa CDI em eventos COMPRA
    import re as _re_lci
    from carteira_clean_web.backend.engine.constantes import AGREGADO_PRIVADO
    _CDI_RE = _re_lci.compile(r"CDI[:\s]+([\d]+)[,\.](\d+)")
    lci_tickers = {
        ev["ativo"]
        for ev in eventos
        if ev.get("tipo") == "COMPRA"
        and (
            str(ev.get("ativo", "")).upper().startswith(("LCI-", "LCA-"))
            or ativos.get(ev["ativo"], {}).get("familia") in AGREGADO_PRIVADO
        )
        and _CDI_RE.search(str(ev.get("obs") or ""))
    }
    if lci_tickers and not no_api:
        for tkr in lci_tickers:
            saldos = calcular_saldo_lci(tkr, eventos, hoje, no_api)
            if saldos:
                if tkr not in precos_manuais:
                    precos_manuais[tkr] = {}
                for dt, v in saldos.items():
                    precos_manuais[tkr].setdefault(dt, v)  # extrato DB tem prioridade

    log.info("\n[3/6] Calculando posições e vendas (PEPS)...")
    posicoes, vendas_rv, vendas_rf, proventos = calc_posicoes_e_vendas(eventos, ativos, precos_manuais)
    pnl_total = sum(v["pnl"] for v in vendas_rv)
    log.info(f"  • {sum(1 for p in posicoes.values() if p.qtd > 0)} posições ativas")
    log.info(f"  • {len(vendas_rv)} vendas de RV | P&L: R$ {pnl_total:+,.2f}")
    log.info(f"  • {len(vendas_rf)} resgates de RF cotizada")
    log.info(f"  • R$ {sum(proventos.values()):,.2f} em proventos")

    log.info("\n[4/6] Reconstruindo evolução diária e TWR...")
    df_evo = calc_evolucao_diaria(eventos, ativos, precos_publicos, precos_manuais, hoje)
    aportes_inferidos, saldo_residual = inferir_fluxos_externos_retroativos(eventos, ativos)
    log.info(f"  • {len(aportes_inferidos)} APORTEs externos inferidos")
    log.info(f"    Total inferido: R$ {sum(a['valor'] for a in aportes_inferidos):,.2f}")
    log.info(f"    Saldo residual: R$ {saldo_residual:,.2f}")
    df_evo = calc_twr_e_benchmarks(df_evo, eventos, aportes_inferidos, ativos)
    if not df_evo.empty:
        ult = df_evo.iloc[-1]
        log.info(f"  • Patrimônio em {ult['data']}: R$ {ult['patrimonio_total']:,.2f}")
        log.info(f"    — Gerida: R$ {ult['patrimonio_gerida']:,.2f}")
        log.info(f"    — FUNCEF: R$ {ult['patrimonio_funcef']:,.2f}")
        log.info(f"  • TWR Gerida: {ult['twr_gerida']*100:+.2f}%  CDI: {ult['cdi_acum']*100:+.2f}%")

    log.info("\n[5/6] Calculando atribuição mensal + Brinson-Fachler...")
    df_atrib = calc_atribuicao_mensal(eventos, ativos, precos_publicos, precos_manuais, hoje)
    log.info(f"  • {len(df_atrib)} linhas (mês × ativo)")
    df_bf = calc_brinson_fachler(df_atrib, data_fim=hoje)
    log.info(f"  • {len(df_bf)} linhas Brinson-Fachler")

    log.info("\n[6/6] Validações ativas...")
    alertas = validar(posicoes, eventos, ativos, df_evo)
    alertas.append(validar_reconciliacao_caixa(saldo_residual))
    erros = sum(1 for a in alertas if a[0] == "ERRO")
    avisos = sum(1 for a in alertas if a[0] == "AVISO")
    infos = sum(1 for a in alertas if a[0] == "INFO")
    log.info(f"  • {erros} ERROs | {avisos} AVISOs | {infos} INFOs")
    for nivel, ativo, msg in alertas[:12]:
        log.info(f"    [{nivel}] {ativo}: {msg}")

    log.info("\n" + "=" * 65)

    return {
        "ativos": ativos,
        "eventos": eventos,
        "precos_manuais": precos_manuais,
        "precos_publicos": precos_publicos,
        "posicoes": posicoes,
        "vendas_rv": vendas_rv,
        "vendas_rf": vendas_rf,
        "proventos": proventos,
        "aportes_inferidos": aportes_inferidos,
        "saldo_residual": saldo_residual,
        "df_evo": df_evo,
        "df_atrib": df_atrib,
        "df_bf": df_bf,
        "alertas": alertas,
        "hoje": hoje,
    }


def main():
    parser = argparse.ArgumentParser(description="Engine Carteira Clean — PostgreSQL")
    parser.add_argument("--no-api", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    resultado = run(no_api=args.no_api, verbose=args.verbose)

    if not resultado["df_evo"].empty:
        ult = resultado["df_evo"].iloc[-1]
        pnl = sum(v["pnl"] for v in resultado["vendas_rv"])
        print(f"\nResumo rápido:")
        print(f"  Patrimônio total : R$ {ult['patrimonio_total']:,.2f}")
        print(f"  TWR Gerida YTD   : {ult['twr_gerida']*100:+.2f}%")
        print(f"  CDI acumulado    : {ult['cdi_acum']*100:+.2f}%")
        print(f"  P&L vendas RV    : R$ {pnl:+,.2f}")


if __name__ == "__main__":
    main()
