"use client";

import React from "react";

interface FundamentoTicker {
  ticker: string;
  pl?: number | null;
  pvp?: number | null;
  roe?: number | null;
  dy?: number | null;
  margem_ebitda?: number | null;
  div_liq_ebitda?: number | null;
  [key: string]: unknown;
}

interface TabelaFundamentosProps {
  dados: FundamentoTicker[];
}

function fmt(v: unknown, digits = 1): string {
  if (v == null || v === undefined) return "—";
  const n = Number(v);
  if (isNaN(n)) return "—";
  return n.toFixed(digits);
}

function fmtPct(v: unknown): string {
  const s = fmt(v, 1);
  if (s === "—") return s;
  return s + "%";
}

export default function TabelaFundamentos({ dados }: TabelaFundamentosProps) {
  if (!dados || dados.length === 0) {
    return (
      <p className="text-[#6b7280] text-sm">Sem dados de fundamentos disponíveis.</p>
    );
  }

  const cols = [
    { key: "ticker",       label: "Ticker",       render: (d: FundamentoTicker) => d.ticker },
    { key: "pl",           label: "P/L",           render: (d: FundamentoTicker) => fmt(d.pl) },
    { key: "pvp",          label: "P/VP",          render: (d: FundamentoTicker) => fmt(d.pvp) },
    { key: "roe",          label: "ROE",           render: (d: FundamentoTicker) => fmtPct(d.roe) },
    { key: "dy",           label: "Div. Yield",    render: (d: FundamentoTicker) => fmtPct(d.dy) },
    { key: "div_liq_ebitda", label: "Dív/EBITDA", render: (d: FundamentoTicker) => fmt(d.div_liq_ebitda) },
  ];

  return (
    <div className="rounded-lg border border-[#2A2D3A] overflow-hidden my-2">
      <div className="px-3 py-2 border-b border-[#2A2D3A] bg-[#1A1D27]">
        <span className="text-xs font-medium text-[#D1D4DC]">Múltiplos Fundamentalistas</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[#2A2D3A]">
              {cols.map((c) => (
                <th
                  key={c.key}
                  className="px-3 py-2 text-left font-medium text-[#6b7280] bg-[#0F1117] whitespace-nowrap"
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dados.map((row, i) => (
              <tr
                key={row.ticker}
                className={`border-b border-[#2A2D3A] hover:bg-[#1A1D27] transition-colors ${
                  i % 2 === 0 ? "bg-[#0F1117]" : "bg-[#111318]"
                }`}
              >
                {cols.map((c) => (
                  <td
                    key={c.key}
                    className={`px-3 py-2 font-mono ${
                      c.key === "ticker" ? "text-[#26A69A] font-medium" : "text-[#D1D4DC]"
                    }`}
                  >
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
