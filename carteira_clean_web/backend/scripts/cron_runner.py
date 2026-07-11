"""
scripts/cron_runner.py — Agendador dos coletores de ingestão (Fase 6 da
fatia "Ingestão de dados"). Roda como serviço dedicado `cron` no
docker-compose — não existia nenhum cron real no repo antes desta fatia
(cotações/benchmarks só eram atualizados por clique manual em "Recalcular").

Uso:
    python3 -m carteira_clean_web.backend.scripts.cron_runner --serve
        Roda o loop de agendamento (usado pelo serviço `cron`).
    python3 -m carteira_clean_web.backend.scripts.cron_runner --job <nome>
        Roda 1 job manualmente e sai — usado no backfill inicial e em debug.
        Jobs: cotacoes, taxonomia, fundamentos_peers, eventos_ipe, noticias

Agenda (todos os horários em UTC):
    cotacoes           21:30 diário
    taxonomia          domingo 09:00  (fundamentos_peers depende dela — roda antes)
    fundamentos_peers  domingo 10:00
    eventos_ipe        domingo 11:00
    noticias           12:00 e 22:30 diário
    observacoes_feed   12:30 diário (pré-abertura B3, pregão abre 13:00 UTC)
"""
import argparse

import requests

from carteira_clean_web.backend.engine.ingestao_utils import get_logger

log = get_logger("cron_runner")

_BACKEND_URL = "http://backend:8000"


def _tickers_carteira() -> list[str]:
    from carteira_clean_web.backend.api import cache as engine_cache

    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        log.warning("_tickers_carteira: cache vazio (nenhum cálculo ainda feito)")
        return []
    estado = engine_cache.get_estado()
    return list(estado.get("ativos", {}).keys())


def job_cotacoes():
    """Recálculo diário completo (cotações+benchmarks+índices setoriais+
    preços derivados) + proventos brapi da carteira.

    Chama a API HTTP do próprio backend (não engine_cache.recalcular() direto)
    — recalcular() num processo separado só atualiza o pickle em disco, não
    a memória do processo uvicorn que serve o dashboard; via HTTP o próprio
    backend processa e atualiza seu próprio estado corretamente.
    """
    log.info("job_cotacoes: POST /api/v1/calcular (no_api=False)")
    resp = requests.post(f"{_BACKEND_URL}/api/v1/calcular", params={"no_api": "false"}, timeout=300)
    resp.raise_for_status()
    log.info(f"job_cotacoes: recalculo ok — {resp.json()}")

    from carteira_clean_web.backend.engine.proventos_brapi import coletar_proventos

    tickers = _tickers_carteira()
    if tickers:
        coletar_proventos(tickers)


def job_taxonomia():
    from carteira_clean_web.backend.engine.taxonomia import coletar_taxonomia_setorial
    coletar_taxonomia_setorial()


def job_fundamentos_carteira():
    """Fundamentos dos 38 ativos da carteira via yfinance — fonte primária
    (fatia original). Nunca deve tocar tickers de peer: se colidisse com
    brapi no mesmo ticker, os dois virariam fontes concorrentes do mesmo
    dado e "quem coletou por último" passaria a decidir o valor exibido."""
    from carteira_clean_web.backend.engine.fundamentals_client import salvar_fundamentos_db

    tickers = _tickers_carteira()
    if tickers:
        salvar_fundamentos_db(tickers)


def job_fundamentos_peers():
    """Fundamentos só dos PEERS (não da carteira) via brapi — depende de
    job_taxonomia já ter rodado (domingo 9h, antes das 10h): definir_universo_peers
    usa taxonomia_setorial pra achar o setor de cada ticker da carteira."""
    from carteira_clean_web.backend.engine import peers as peers_mod
    from carteira_clean_web.backend.engine.fundamentos_brapi import coletar_fundamentos_peers

    tickers_carteira = _tickers_carteira()
    if not tickers_carteira:
        log.warning("job_fundamentos_peers: sem tickers da carteira — pulando")
        return
    peers_mod.definir_universo_peers(tickers_carteira)
    apenas_peers = peers_mod.carregar_apenas_peers()
    coletar_fundamentos_peers(apenas_peers)


def job_eventos_ipe():
    """Preenche ativos.cnpj_cvm (via brapi summaryProfile) antes de coletar
    — sem CNPJ cadastrado o join do IPE CVM não casa nada com nenhum ticker."""
    from carteira_clean_web.backend.engine.eventos_cvm import coletar_eventos_ipe, popular_cnpj_ativos

    tickers = _tickers_carteira()
    if tickers:
        popular_cnpj_ativos(tickers)
    coletar_eventos_ipe()


def job_noticias():
    from carteira_clean_web.backend.engine.noticias_rss import coletar_noticias

    tickers = _tickers_carteira()
    if tickers:
        coletar_noticias(tickers)


def job_observacoes_feed():
    """Motor de varredura da Sala de Comando (seção "Orquestra") — roda as 7
    categorias de sinal e grava fatos novos em `observacoes_feed`. Pré-abertura
    de mercado para o feed já estar pronto quando o usuário abre o app."""
    from carteira_clean_web.backend.db.session import get_session
    from carteira_clean_web.backend.engine.varredura_feed import rodar_varredura

    with get_session() as db:
        rodar_varredura(db)


_JOBS = {
    "cotacoes": job_cotacoes,
    "taxonomia": job_taxonomia,
    "fundamentos_carteira": job_fundamentos_carteira,
    "fundamentos_peers": job_fundamentos_peers,
    "eventos_ipe": job_eventos_ipe,
    "noticias": job_noticias,
    "observacoes_feed": job_observacoes_feed,
}


def serve():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(job_cotacoes, CronTrigger(hour=21, minute=30), id="cotacoes_diario", misfire_grace_time=3600)
    sched.add_job(job_taxonomia, CronTrigger(day_of_week="sun", hour=9), id="taxonomia_semanal", misfire_grace_time=3600)
    sched.add_job(job_fundamentos_carteira, CronTrigger(day_of_week="sun", hour=8), id="fundamentos_carteira_semanal", misfire_grace_time=3600)
    sched.add_job(job_fundamentos_peers, CronTrigger(day_of_week="sun", hour=10), id="fundamentos_peers_semanal", misfire_grace_time=3600)
    sched.add_job(job_eventos_ipe, CronTrigger(day_of_week="sun", hour=11), id="eventos_ipe_semanal", misfire_grace_time=3600)
    sched.add_job(job_noticias, CronTrigger(hour=12), id="noticias_meio_dia", misfire_grace_time=1800)
    sched.add_job(job_noticias, CronTrigger(hour=22, minute=30), id="noticias_noite", misfire_grace_time=1800)
    sched.add_job(job_observacoes_feed, CronTrigger(hour=12, minute=30), id="observacoes_feed_diario", misfire_grace_time=1800)
    log.info(
        "cron_runner: agendado (UTC) — cotacoes 21:30 diário | taxonomia dom 9h | "
        "fundamentos_carteira dom 8h | fundamentos_peers dom 10h | eventos_ipe dom 11h | "
        "noticias 12h e 22:30 diário | observacoes_feed 12:30 diário"
    )
    sched.start()


def main():
    parser = argparse.ArgumentParser()
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--serve", action="store_true", help="Roda o loop de agendamento")
    grupo.add_argument("--job", choices=list(_JOBS.keys()), help="Roda 1 job manualmente e sai")
    args = parser.parse_args()

    if args.serve:
        serve()
    else:
        _JOBS[args.job]()


if __name__ == "__main__":
    main()
