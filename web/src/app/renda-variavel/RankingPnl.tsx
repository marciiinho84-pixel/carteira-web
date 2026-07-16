"use client";

import Link from "next/link";

interface Item {
  ticker: string;
  pl_total_pct: number;
  pl_total_rs: number;
}

function brl(v: number): string {
  const abs = Math.abs(v);
  const s = "R$ " + abs.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (v < 0 ? "-" : "+") + s;
}

export default function RankingPnl({ posicoes, topN = 5 }: { posicoes: Item[]; topN?: number }) {
  const ordenado = [...posicoes].sort((a, b) => a.pl_total_pct - b.pl_total_pct);
  const n = Math.min(topN, Math.floor(posicoes.length / 2) || 1);
  const losers = ordenado.slice(0, n);
  const winners = [...ordenado.slice(-n)].reverse();
  const maxAbs = Math.max(5, ...posicoes.map((p) => Math.abs(p.pl_total_pct * 100)));

  function Barra({ p }: { p: Item }) {
    const pctVal = p.pl_total_pct * 100;
    const w = Math.min(100, (Math.abs(pctVal) / maxAbs) * 100);
    const cor = pctVal >= 0 ? "var(--positive)" : "var(--negative)";
    return (
      <div className="flex items-center gap-2 mb-1.5" title={brl(p.pl_total_rs)}>
        <Link href={`/ativos/${p.ticker}`} className="w-16 shrink-0 text-xs font-semibold hover:underline" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>
          {p.ticker}
        </Link>
        <div className="flex-1 h-4 rounded overflow-hidden" style={{ background: "var(--border-soft)" }}>
          <div className="h-full rounded" style={{ width: `${w}%`, background: cor, marginLeft: pctVal >= 0 ? "0" : `${100 - w}%` }} />
        </div>
        <span className="w-16 text-right text-xs font-semibold shrink-0" style={{ color: cor, fontFamily: "var(--font-plex-mono)" }}>
          {pctVal >= 0 ? "+" : ""}{pctVal.toFixed(1)}%
        </span>
      </div>
    );
  }

  if (posicoes.length === 0) {
    return <p className="text-xs" style={{ color: "var(--text-faint)" }}>Sem posições para ranquear.</p>;
  }

  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: "var(--text-muted)" }}>Perdedores</p>
      {losers.map((p) => <Barra key={p.ticker} p={p} />)}
      <p className="text-[10px] uppercase tracking-wider mb-1.5 mt-3" style={{ color: "var(--text-muted)" }}>Ganhadores</p>
      {winners.map((p) => <Barra key={p.ticker} p={p} />)}
    </div>
  );
}
