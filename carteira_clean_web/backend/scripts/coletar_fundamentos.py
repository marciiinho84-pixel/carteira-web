"""Coleta em lote de indicadores fundamentalistas — persiste na tabela `fundamentos`.

Uso:
    python3 -m carteira_clean_web.backend.scripts.coletar_fundamentos
    python3 -m carteira_clean_web.backend.scripts.coletar_fundamentos WEGE3 PETR4 ITUB3

Sem argumentos: coleta todos os ativos RV com posição ativa na carteira.
Cron sugerido: 1x/dia às 22h UTC (após coleta de cotações).
"""

import logging
import sys

log = logging.getLogger("scripts.coletar_fundamentos")


def main(tickers: list[str] | None = None) -> int:
    """Executa coleta e persistência. Retorna 0 (ok) ou 1 (erro)."""
    from carteira_clean_web.backend.engine.fundamentals_client import salvar_fundamentos_db

    log.info("Iniciando coleta de fundamentos...")
    resultado = salvar_fundamentos_db(tickers)

    if "erro" in resultado:
        log.error(f"Erro fatal: {resultado['erro']}")
        return 1

    total = resultado["total"]
    linhas = resultado["linhas_inseridas"]
    com_erro = resultado.get("com_erro", {})
    ok = total - len(com_erro)

    log.info(
        f"Concluído: {ok}/{total} ativos com dados, "
        f"{linhas} linhas inseridas na tabela fundamentos."
    )
    for ticker, motivo in com_erro.items():
        log.warning(f"  {ticker}: {motivo}")

    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    tickers_arg = sys.argv[1:] if len(sys.argv) > 1 else None
    sys.exit(main(tickers_arg))
