"""
Script de coleta de indicadores macro e eventos corporativos.

Uso:
    python3 -m carteira_clean_web.backend.scripts.coletar_macro
    python3 -m carteira_clean_web.backend.scripts.coletar_macro --so-macro
    python3 -m carteira_clean_web.backend.scripts.coletar_macro --so-eventos
"""

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main(so_macro: bool = False, so_eventos: bool = False):
    from carteira_clean_web.backend.engine.macro_client import (
        coletar_macro,
        coletar_eventos_corporativos,
    )

    if not so_eventos:
        print("Coletando indicadores macro (BCB SGS + Focus)...")
        res_macro = coletar_macro(janela_dias=90)
        print(
            f"  Macro: {res_macro['linhas_inseridas']} linhas inseridas | "
            f"{res_macro['por_indicador']}"
        )

    if not so_macro:
        print("Coletando eventos corporativos (yfinance)...")
        res_ev = coletar_eventos_corporativos()
        print(
            f"  Eventos: {res_ev['linhas_inseridas']} linhas | "
            f"{res_ev['tickers_processados']} tickers processados"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--so-macro", action="store_true", help="Só coleta macro")
    parser.add_argument("--so-eventos", action="store_true", help="Só coleta eventos")
    args = parser.parse_args()
    main(so_macro=args.so_macro, so_eventos=args.so_eventos)
    sys.exit(0)
