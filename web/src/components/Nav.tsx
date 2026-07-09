"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { clearToken } from "@/lib/api";

function IconSalaDeComando() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <rect x="2" y="3" width="12" height="10" rx="1.5" />
      <line x1="5" y1="10" x2="5" y2="8" />
      <line x1="8" y1="10" x2="8" y2="6" />
      <line x1="11" y1="10" x2="11" y2="7" />
    </svg>
  );
}
function IconDashboard() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <rect x="2" y="2" width="5" height="5" rx="1" />
      <rect x="9" y="2" width="5" height="5" rx="1" />
      <rect x="2" y="9" width="5" height="5" rx="1" />
      <rect x="9" y="9" width="5" height="5" rx="1" />
    </svg>
  );
}
function IconPosicoes() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <line x1="2" y1="4" x2="14" y2="4" />
      <line x1="2" y1="8" x2="14" y2="8" />
      <line x1="2" y1="12" x2="14" y2="12" />
    </svg>
  );
}
function IconRendaVariavel() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <polyline points="1.5,12 5.5,7 8.5,9.5 14.5,3" />
    </svg>
  );
}
function IconEvolucao() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <polyline points="2,13 2,3" />
      <polyline points="2,13 14,13" />
      <polyline points="4,10 7,6.5 10,8.5 13,4" />
    </svg>
  );
}
function IconMeta() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <circle cx="8" cy="8" r="6" />
      <circle cx="8" cy="8" r="2" />
    </svg>
  );
}
function IconTeses() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <circle cx="8" cy="6" r="4" />
      <line x1="8" y1="10" x2="8" y2="14" />
      <line x1="5.5" y1="13" x2="10.5" y2="13" />
    </svg>
  );
}
function IconAlertas() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path d="M3 11 a5 5 0 0 1 10 0 Z" />
      <line x1="7" y1="13.5" x2="9" y2="13.5" />
    </svg>
  );
}
function IconRisco() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <line x1="8" y1="2" x2="8" y2="14" />
      <line x1="3" y1="5" x2="13" y2="5" />
      <circle cx="3.5" cy="8.5" r="2" />
      <circle cx="12.5" cy="8.5" r="2" />
    </svg>
  );
}
function IconNovoEvento() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <line x1="8" y1="3" x2="8" y2="13" />
      <line x1="3" y1="8" x2="13" y2="8" />
    </svg>
  );
}
function IconMaestro() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <rect x="3" y="4" width="10" height="8" rx="2" />
      <circle cx="6" cy="8" r="0.5" />
      <circle cx="10" cy="8" r="0.5" />
      <line x1="8" y1="2" x2="8" y2="4" />
    </svg>
  );
}
function IconConfig() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <circle cx="8" cy="8" r="2.5" />
      <line x1="8" y1="1.5" x2="8" y2="3.2" />
      <line x1="8" y1="12.8" x2="8" y2="14.5" />
      <line x1="1.5" y1="8" x2="3.2" y2="8" />
      <line x1="12.8" y1="8" x2="14.5" y2="8" />
      <line x1="3.3" y1="3.3" x2="4.5" y2="4.5" />
      <line x1="11.5" y1="11.5" x2="12.7" y2="12.7" />
      <line x1="3.3" y1="12.7" x2="4.5" y2="11.5" />
      <line x1="11.5" y1="4.5" x2="12.7" y2="3.3" />
    </svg>
  );
}
function IconSair() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path d="M6 2.5H3.5a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1H6" />
      <polyline points="9.5,5 13,8 9.5,11" />
      <line x1="13" y1="8" x2="5.5" y2="8" />
    </svg>
  );
}

const LINKS = [
  { href: "/sala-de-comando", label: "Sala de Comando", Icon: IconSalaDeComando },
  { href: "/dashboard", label: "Dashboard", Icon: IconDashboard },
  { href: "/posicoes", label: "Posições", Icon: IconPosicoes },
  { href: "/renda-variavel", label: "Renda Variável", Icon: IconRendaVariavel },
  { href: "/evolucao", label: "Evolução", Icon: IconEvolucao },
  { href: "/meta", label: "Meta R$3M", Icon: IconMeta },
  { href: "/teses", label: "Teses", Icon: IconTeses },
  { href: "/alertas", label: "Alertas", Icon: IconAlertas },
  { href: "/risco", label: "Risco", Icon: IconRisco },
  { href: "/novo-evento", label: "Novo Evento", Icon: IconNovoEvento },
  { href: "/maestro", label: "Maestro", Icon: IconMaestro },
  { href: "/configuracoes", label: "Config.", Icon: IconConfig },
];

export default function Nav() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const { data: session } = useSession();

  function logout() {
    clearToken();
    signOut({ callbackUrl: "/login" });
  }

  return (
    <aside
      className="sticky top-0 h-screen flex flex-col shrink-0 border-r transition-all duration-200 overflow-y-auto"
      style={{
        width: collapsed ? 52 : 216,
        background: "var(--bg-card-alt)",
        borderColor: "var(--border)",
      }}
    >
      {/* Logo + Toggle */}
      <div
        className="flex items-center justify-between px-3 py-3 border-b"
        style={{ borderColor: "var(--border)" }}
      >
        {!collapsed && (
          <span className="flex items-center gap-2.5">
            <span
              className="flex items-center justify-center shrink-0 font-bold"
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: "var(--accent)",
                color: "var(--bg-card)",
                fontFamily: "var(--font-source-serif)",
                fontSize: 15,
              }}
            >
              C
            </span>
            <span
              className="text-[15px] font-bold"
              style={{ color: "var(--text-body)", fontFamily: "var(--font-source-serif)" }}
            >
              Carteira
            </span>
          </span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="ml-auto rounded p-1 transition text-lg leading-none"
          style={{ color: "var(--text-faint)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-faint)")}
          title={collapsed ? "Expandir menu" : "Recolher menu"}
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>

      {/* Nav links */}
      <nav className="flex-1 py-2 space-y-0.5 overflow-hidden px-2.5">
        {LINKS.map((l) => {
          const active = pathname === l.href || pathname.startsWith(l.href + "/");
          return (
            <Link
              key={l.href}
              href={l.href}
              title={collapsed ? l.label : undefined}
              className="flex items-center gap-2.5 px-2.5 py-2 text-[13px] transition rounded-lg"
              style={{
                background: active ? "rgba(193,95,60,0.12)" : "transparent",
                color: active ? "var(--accent-strong)" : "var(--text-muted)",
                fontWeight: active ? 600 : 500,
              }}
            >
              <span className="shrink-0">
                <l.Icon />
              </span>
              {!collapsed && <span className="truncate whitespace-nowrap">{l.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Rodapé — usuário + logout */}
      <div
        className="border-t p-3 flex flex-col gap-2"
        style={{ borderColor: "var(--border)" }}
      >
        {!collapsed && session?.user?.email && (
          <span
            className="truncate"
            style={{ color: "var(--text-faint)", fontSize: 11 }}
            title={session.user.email}
          >
            {session.user.email}
          </span>
        )}
        <button
          onClick={logout}
          title="Sair"
          className="flex items-center gap-2.5 w-full px-1 py-1 text-[13px] transition rounded"
          style={{ color: "var(--text-faint)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--negative)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-faint)")}
        >
          <span className="shrink-0">
            <IconSair />
          </span>
          {!collapsed && <span>Sair</span>}
        </button>
      </div>
    </aside>
  );
}
