"""
engine/tecnico.py — Análise técnica com sistema de votação (Fatia 12).

Indicadores calculados com pandas puro (sem ta-lib).
Sistema de votação estilo TradingView Technical Ratings.
"""
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path


def _sma(series: list[float], n: int) -> list[float | None]:
    result = [None] * len(series)
    for i in range(n - 1, len(series)):
        result[i] = sum(series[i - n + 1:i + 1]) / n
    return result


def _ema(series: list[float], n: int) -> list[float | None]:
    result: list[float | None] = [None] * len(series)
    k = 2 / (n + 1)
    first = None
    for i, v in enumerate(series):
        if v is None:
            continue
        if first is None:
            first = i
            result[i] = v
        elif result[i - 1] is not None:
            result[i] = v * k + result[i - 1] * (1 - k)
        else:
            result[i] = v
    return result


def _rsi(closes: list[float], n: int = 14) -> list[float | None]:
    result: list[float | None] = [None] * len(closes)
    if len(closes) < n + 1:
        return result
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    for i in range(n, len(closes)):
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100 - 100 / (1 + rs)
        if i < len(gains):
            avg_gain = (avg_gain * (n - 1) + gains[i]) / n
            avg_loss = (avg_loss * (n - 1) + losses[i]) / n
    return result


def _bollinger(closes: list[float], n: int = 20, k: float = 2.0) -> tuple[list, list, list]:
    mid = _sma(closes, n)
    upper, lower = [None] * len(closes), [None] * len(closes)
    for i in range(n - 1, len(closes)):
        window = closes[i - n + 1:i + 1]
        m = sum(window) / n
        variance = sum((x - m) ** 2 for x in window) / n
        sd = math.sqrt(variance)
        upper[i] = m + k * sd
        lower[i] = m - k * sd
    return upper, mid, lower


def _macd(closes: list[float]) -> tuple[list, list, list]:
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = [
        (a - b) if (a is not None and b is not None) else None
        for a, b in zip(ema12, ema26)
    ]
    valid = [v for v in macd_line if v is not None]
    signal_raw = _ema(valid, 9)
    # Realign signal back to original indices
    signal: list[float | None] = [None] * len(closes)
    j = 0
    for i, v in enumerate(macd_line):
        if v is not None:
            signal[i] = signal_raw[j] if j < len(signal_raw) else None
            j += 1
    hist = [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(macd_line, signal)
    ]
    return macd_line, signal, hist


def _suportes_resistencias(closes: list[float], n_pontos: int = 5) -> tuple[list[float], list[float]]:
    """Pivôs simples: mínimos locais = suportes, máximos locais = resistências."""
    suportes, resistencias = [], []
    window = 5
    for i in range(window, len(closes) - window):
        c = closes[i]
        if all(closes[i] <= closes[i - j] for j in range(1, window + 1)) and \
           all(closes[i] <= closes[i + j] for j in range(1, window + 1)):
            suportes.append(c)
        if all(closes[i] >= closes[i - j] for j in range(1, window + 1)) and \
           all(closes[i] >= closes[i + j] for j in range(1, window + 1)):
            resistencias.append(c)
    # Deduplicate (agrupa pontos próximos de 2%)
    def dedup(pts: list[float]) -> list[float]:
        if not pts:
            return []
        pts = sorted(pts)
        out = [pts[0]]
        for p in pts[1:]:
            if abs(p - out[-1]) / out[-1] > 0.02:
                out.append(p)
        return out

    return dedup(suportes)[-n_pontos:], dedup(resistencias)[-n_pontos:]


def _votar_mm(preco: float, mm: float | None) -> int:
    if mm is None:
        return 0
    return 1 if preco > mm else -1


def _votar_rsi(rsi: float | None) -> tuple[int, str]:
    if rsi is None:
        return 0, "sem dados"
    if rsi > 70:
        return -1, f"RSI {rsi:.1f} — sobrecomprado"
    if rsi < 30:
        return 1, f"RSI {rsi:.1f} — sobrevendido"
    return 0, f"RSI {rsi:.1f} — neutro"


def _votar_macd(macd: float | None, signal: float | None) -> tuple[int, str]:
    if macd is None or signal is None:
        return 0, "sem dados"
    if macd > signal:
        return 1, f"MACD {macd:.3f} > sinal {signal:.3f} — momentum de alta"
    return -1, f"MACD {macd:.3f} < sinal {signal:.3f} — momentum de baixa"


def _votar_bollinger(preco: float, upper: float | None, lower: float | None) -> tuple[int, str]:
    if upper is None or lower is None:
        return 0, "sem dados"
    if preco > upper:
        return -1, f"Preço R${preco:.2f} acima banda superior R${upper:.2f} — sobrecomprado"
    if preco < lower:
        return 1, f"Preço R${preco:.2f} abaixo banda inferior R${lower:.2f} — sobrevendido"
    return 0, f"Preço dentro das Bandas de Bollinger ({lower:.2f}–{upper:.2f})"


def calcular_indicadores(
    ticker: str,
    ohlcv: dict,
) -> dict:
    """
    Calcula indicadores técnicos e sistema de votação.

    Args:
        ticker: código do ativo
        ohlcv: {"dates": [...], "open": [...], "high": [...],
                "low": [...], "close": [...], "volume": [...]}
    """
    closes = ohlcv["close"]
    if len(closes) < 30:
        return {"erro": f"Histórico insuficiente ({len(closes)} candles < 30)."}

    preco = closes[-1]

    mm20_s  = _sma(closes, 20)
    mm50_s  = _sma(closes, 50)
    mm200_s = _sma(closes, 200)
    mm20  = mm20_s[-1]
    mm50  = mm50_s[-1]
    mm200 = mm200_s[-1]

    rsi_s = _rsi(closes, 14)
    rsi   = next((v for v in reversed(rsi_s) if v is not None), None)

    macd_s, signal_s, hist_s = _macd(closes)
    macd_v   = next((v for v in reversed(macd_s)  if v is not None), None)
    signal_v = next((v for v in reversed(signal_s) if v is not None), None)

    boll_up_s, _, boll_lo_s = _bollinger(closes, 20, 2)
    boll_up = next((v for v in reversed(boll_up_s) if v is not None), None)
    boll_lo = next((v for v in reversed(boll_lo_s) if v is not None), None)

    suportes, resistencias = _suportes_resistencias(closes)

    # ── Sistema de votação ──────────────────────────────────────────────────
    v_mm20  = _votar_mm(preco, mm20)
    v_mm50  = _votar_mm(preco, mm50)
    v_mm200 = _votar_mm(preco, mm200)

    v_rsi, j_rsi   = _votar_rsi(rsi)
    v_macd, j_macd = _votar_macd(macd_v, signal_v)
    v_boll, j_boll = _votar_bollinger(preco, boll_up, boll_lo)

    votos_mm = [v_mm20, v_mm50, v_mm200]
    votos_osc = [v_rsi, v_macd, v_boll]
    rating_mm  = sum(votos_mm) / len(votos_mm)
    rating_osc = sum(votos_osc) / len(votos_osc)
    rating_geral = (rating_mm + rating_osc) / 2

    def tendencia_texto(r: float) -> str:
        if r > 0.5:   return "compra"
        if r < -0.5:  return "venda"
        return "neutro"

    # Tendência principal
    if mm200 and preco > mm200:
        tendencia = "alta"
    elif mm200 and preco < mm200:
        tendencia = "baixa"
    else:
        tendencia = "lateral"

    # Sinais ativos
    sinais = []
    if mm20 and mm50:
        if preco > mm20 > mm50:
            sinais.append("MM20 acima da MM50 — tendência de curto prazo positiva")
        elif preco < mm20 < mm50:
            sinais.append("MM20 abaixo da MM50 — tendência de curto prazo negativa")
    if rsi and rsi > 70:
        sinais.append(f"RSI sobrecomprado ({rsi:.1f})")
    if rsi and rsi < 30:
        sinais.append(f"RSI sobrevendido ({rsi:.1f})")
    if macd_v and signal_v:
        if macd_v > signal_v and (hist_s[-2] or 0) < 0:
            sinais.append("Cruzamento MACD de baixa para alta (sinal recente)")

    # Entrada/alvo/stop
    entrada = suportes[-1] if suportes and suportes[-1] < preco else preco * 0.97
    alvo    = resistencias[-1] if resistencias and resistencias[-1] > preco else preco * 1.05
    stop    = suportes[-2] if len(suportes) >= 2 else preco * 0.93

    return {
        "ticker":  ticker,
        "preco":   round(preco, 2),
        "tendencia": tendencia,
        "sinais":  sinais,
        "indicadores": {
            "MM20":  round(mm20,  2) if mm20  else None,
            "MM50":  round(mm50,  2) if mm50  else None,
            "MM200": round(mm200, 2) if mm200 else None,
            "RSI14": round(rsi,   1) if rsi   else None,
            "MACD":  round(macd_v, 4) if macd_v else None,
            "MACD_sinal": round(signal_v, 4) if signal_v else None,
            "Bollinger_sup": round(boll_up, 2) if boll_up else None,
            "Bollinger_inf": round(boll_lo, 2) if boll_lo else None,
        },
        "votos": {
            "MM20":       {"voto": v_mm20,  "justificativa": f"Preço R${preco:.2f} {'>' if v_mm20 > 0 else '<'} MM20 R${mm20:.2f}" if mm20 else "sem dados"},
            "MM50":       {"voto": v_mm50,  "justificativa": f"Preço R${preco:.2f} {'>' if v_mm50 > 0 else '<'} MM50 R${mm50:.2f}" if mm50 else "sem dados"},
            "MM200":      {"voto": v_mm200, "justificativa": f"Preço R${preco:.2f} {'>' if v_mm200 > 0 else '<'} MM200 R${mm200:.2f}" if mm200 else "sem dados"},
            "RSI14":      {"voto": v_rsi,   "justificativa": j_rsi},
            "MACD":       {"voto": v_macd,  "justificativa": j_macd},
            "Bollinger":  {"voto": v_boll,  "justificativa": j_boll},
        },
        "rating_medias_moveis": round(rating_mm, 3),
        "rating_osciladores":   round(rating_osc, 3),
        "rating_geral":         round(rating_geral, 3),
        "rating_texto":         tendencia_texto(rating_geral),
        "suportes":     [round(s, 2) for s in suportes],
        "resistencias": [round(r, 2) for r in resistencias],
        "entrada_sugerida": {
            "preco": round(entrada, 2),
            "justificativa": "Suporte técnico mais próximo abaixo do preço atual",
        },
        "alvo": {
            "preco": round(alvo, 2),
            "justificativa": "Resistência técnica mais próxima acima do preço atual",
        },
        "stop_loss": {
            "preco": round(stop, 2),
            "justificativa": "Suporte abaixo do ponto de entrada",
        },
        "n_candles": len(closes),
    }


def gerar_grafico_html(ticker: str, ohlcv: dict, indicadores: dict, n_exibir: int | None = None) -> str:
    """
    Gera gráfico candlestick interativo com Plotly.
    Retorna o caminho do arquivo HTML gerado.

    n_exibir: se fornecido, calcula indicadores no histórico completo mas
              exibe apenas os últimos n_exibir candles (garante MM200 visível).
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    closes_full = ohlcv["close"]

    # Calcula séries de indicadores sobre histórico completo
    mm20_full  = _sma(closes_full, 20)
    mm50_full  = _sma(closes_full, 50)
    mm200_full = _sma(closes_full, 200)
    rsi_full   = _rsi(closes_full, 14)
    boll_up_full, boll_mid_full, boll_lo_full = _bollinger(closes_full, 20, 2)
    macd_full, signal_full, hist_full = _macd(closes_full)

    # Trimma para exibição
    sl = slice(-n_exibir, None) if n_exibir else slice(None)
    dates  = ohlcv["dates"][sl]
    opens  = ohlcv["open"][sl]
    highs  = ohlcv["high"][sl]
    lows   = ohlcv["low"][sl]
    closes = closes_full[sl]
    vols   = ohlcv.get("volume", [0] * len(closes_full))[sl]

    mm20      = mm20_full[sl]
    mm50      = mm50_full[sl]
    mm200     = mm200_full[sl]
    rsi_s     = rsi_full[sl]
    boll_up_s = boll_up_full[sl]
    boll_lo_s = boll_lo_full[sl]
    macd_s    = macd_full[sl]
    signal_s  = signal_full[sl]
    hist_s    = hist_full[sl]

    ind = indicadores.get("indicadores", {})

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.52, 0.16, 0.16, 0.16],
        vertical_spacing=0.03,
        subplot_titles=(ticker, "Volume", "RSI 14", "MACD (12, 26, 9)"),
    )

    # ── Candlestick ──────────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=dates, open=opens, high=highs, low=lows, close=closes,
        name=ticker, increasing_line_color="#26A69A", decreasing_line_color="#EF5350",
    ), row=1, col=1)

    # ── Bollinger ────────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(x=dates, y=boll_up_s, name="Boll Sup",
                             line=dict(color="rgba(100,100,255,0.4)", dash="dot"), showlegend=True), row=1, col=1)
    fig.add_trace(go.Scatter(x=dates, y=boll_lo_s, name="Boll Inf",
                             line=dict(color="rgba(100,100,255,0.4)", dash="dot"),
                             fill="tonexty", fillcolor="rgba(100,100,255,0.06)",
                             showlegend=True), row=1, col=1)

    # ── Médias Móveis ────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(x=dates, y=mm20,  name="MM20",  line=dict(color="#F59E0B", width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=dates, y=mm50,  name="MM50",  line=dict(color="#3B82F6", width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=dates, y=mm200, name="MM200", line=dict(color="#EF4444", width=1.5)), row=1, col=1)

    # ── Suportes e resistências ──────────────────────────────────────────────
    for s in indicadores.get("suportes", []):
        fig.add_hline(y=s, line_color="green", line_dash="dot", line_width=1,
                      annotation_text=f"S {s:.2f}", annotation_position="right",
                      row=1, col=1)
    for r in indicadores.get("resistencias", []):
        fig.add_hline(y=r, line_color="red", line_dash="dot", line_width=1,
                      annotation_text=f"R {r:.2f}", annotation_position="right",
                      row=1, col=1)

    # ── Entrada/Alvo/Stop ────────────────────────────────────────────────────
    entrada = indicadores.get("entrada_sugerida", {}).get("preco")
    alvo    = indicadores.get("alvo", {}).get("preco")
    stop    = indicadores.get("stop_loss", {}).get("preco")
    if entrada:
        fig.add_hline(y=entrada, line_color="#10B981", line_dash="solid", line_width=2,
                      annotation_text=f"Entrada {entrada:.2f}", row=1, col=1)
    if alvo:
        fig.add_hline(y=alvo, line_color="#6366F1", line_dash="solid", line_width=2,
                      annotation_text=f"Alvo {alvo:.2f}", row=1, col=1)
    if stop:
        fig.add_hline(y=stop, line_color="#F97316", line_dash="solid", line_width=2,
                      annotation_text=f"Stop {stop:.2f}", row=1, col=1)

    # ── Volume ────────────────────────────────────────────────────────────────
    colors = ["#26A69A" if c >= o else "#EF5350" for c, o in zip(closes, opens)]
    fig.add_trace(go.Bar(x=dates, y=vols, name="Volume",
                         marker_color=colors, showlegend=False), row=2, col=1)

    # ── RSI ──────────────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(x=dates, y=rsi_s, name="RSI 14",
                             line=dict(color="#A78BFA", width=1.5)), row=3, col=1)
    fig.add_hline(y=70, line_color="red",   line_dash="dot", line_width=1, row=3, col=1)
    fig.add_hline(y=30, line_color="green", line_dash="dot", line_width=1, row=3, col=1)

    # ── MACD ─────────────────────────────────────────────────────────────────
    hist_colors = [
        "#26A69A" if (v or 0) >= 0 else "#EF5350" for v in hist_s
    ]
    fig.add_trace(go.Bar(x=dates, y=hist_s, name="Histograma",
                         marker_color=hist_colors, showlegend=False), row=4, col=1)
    fig.add_trace(go.Scatter(x=dates, y=macd_s, name="MACD",
                             line=dict(color="#3B82F6", width=1.5)), row=4, col=1)
    fig.add_trace(go.Scatter(x=dates, y=signal_s, name="Sinal",
                             line=dict(color="#F97316", width=1.5)), row=4, col=1)
    fig.add_hline(y=0, line_color="rgba(255,255,255,0.2)", line_width=1, row=4, col=1)

    rating = indicadores.get("rating_geral", 0)
    rating_txt = indicadores.get("rating_texto", "neutro")
    fig.update_layout(
        title=dict(
            text=f"{ticker} — Rating: {rating:+.2f} ({rating_txt.upper()}) | "
                 f"Tendência: {indicadores.get('tendencia', '?').upper()}",
            font=dict(size=16),
        ),
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        height=900,
        paper_bgcolor="#0F1117",
        plot_bgcolor="#0F1117",
        font=dict(color="#C0C4D0"),
        legend=dict(orientation="h", y=1.02, x=0),
    )

    charts_dir = Path("/data/charts")
    charts_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    path = charts_dir / f"{ticker}_{ts}.html"
    fig.write_html(str(path), include_plotlyjs="cdn")
    return str(path)
