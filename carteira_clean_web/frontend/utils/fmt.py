"""
Formatadores de exibição: moeda, percentual, cores, badges, export.
"""

import io
import math
from datetime import date

import pandas as pd
import streamlit as st


def _invalido(v) -> bool:
    """Retorna True para None, NaN ou infinito."""
    return v is None or (isinstance(v, float) and not math.isfinite(v))


def moeda(v: float | None, sinal: bool = False) -> str:
    if _invalido(v):
        return "—"
    prefixo = "+" if sinal and v > 0 else ""
    return f"R$ {prefixo}{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v: float | None, casas: int = 2, sinal: bool = True) -> str:
    if _invalido(v):
        return "—"
    prefixo = "+" if sinal and v > 0 else ""
    return f"{prefixo}{v * 100:.{casas}f}%"


def cor_pnl(v: float) -> str:
    """Retorna 'green' ou 'red' conforme sinal do valor."""
    return "green" if v >= 0 else "red"


def badge_status(status: str) -> str:
    """Converte status de liquidação em emoji + texto."""
    mapa = {
        "LIQUIDADO": "🟢 Liquidado",
        "PENDENTE_ENTRADA": "🟡 Entrando",
        "PENDENTE_SAIDA": "🔴 Saindo",
    }
    return mapa.get(status, status)


def colorir(valor: str, cor: str) -> str:
    """Envolve valor em HTML colorido para uso em markdown."""
    return f'<span style="color:{cor};font-weight:bold">{valor}</span>'


def delta_colored(v: float, fmt_fn=pct) -> str:
    cor = "#2ecc71" if v >= 0 else "#e74c3c"
    return f'<span style="color:{cor}">{fmt_fn(v)}</span>'


def botoes_exportar(df: pd.DataFrame, nome_tabela: str, key: str) -> None:
    """Renderiza botões 📄 CSV e 📊 XLSX lado a lado para download da tabela."""
    hoje = date.today().strftime("%Y-%m-%d")
    nome = f"{nome_tabela}_{hoje}"

    col1, col2 = st.columns(2)

    # CSV com BOM (abre sem erro de acentuação no LibreOffice/Excel BR)
    with col1:
        csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="📄 Exportar CSV",
            data=csv_bytes,
            file_name=f"{nome}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{key}_csv",
        )

    # XLSX com openpyxl
    with col2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Dados")
        st.download_button(
            label="📊 Exportar XLSX",
            data=buf.getvalue(),
            file_name=f"{nome}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"{key}_xlsx",
        )


def card_kpi(titulo: str, valor: str, delta: str = "", cor_delta: str = "gray") -> None:
    """Renderiza um KPI compacto em markdown."""
    delta_html = f'<br><small style="color:{cor_delta}">{delta}</small>' if delta else ""
    st.markdown(
        f"""
        <div style="background:#1e2130;padding:16px 20px;border-radius:10px;
                    border-left:4px solid #4a9eff;margin-bottom:8px">
            <div style="color:#aaa;font-size:0.78rem;text-transform:uppercase;
                        letter-spacing:0.05em">{titulo}</div>
            <div style="font-size:1.5rem;font-weight:700;color:#fff;margin-top:4px">
                {valor}{delta_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
