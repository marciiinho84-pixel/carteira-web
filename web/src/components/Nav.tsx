"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import { clearToken } from "@/lib/api";

const LINKS = [
  { href: "/sala-de-comando", label: "Sala de Comando", icon: "🎼" },
  { href: "/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/posicoes", label: "Posições", icon: "📋" },
  { href: "/renda-variavel", label: "Renda Variável", icon: "📉" },
  { href: "/evolucao", label: "Evolução", icon: "📈" },
  { href: "/meta", label: "Meta R$3M", icon: "🎯" },
  { href: "/teses", label: "Teses", icon: "🔬" },
  { href: "/risco", label: "Risco", icon: "⚖️" },
  { href: "/novo-evento", label: "Novo Evento", icon: "➕" },
  { href: "/maestro", label: "Maestro", icon: "🤖" },
  { href: "/configuracoes", label: "Config.", icon: "⚙️" },
];

export default function Nav() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  function logout() {
    clearToken();
    signOut({ callbackUrl: "/login" });
  }

  return (
    <aside
      className="flex flex-col shrink-0 border-r border-[#2A2D3A] bg-[#1A1D27] transition-all duration-200"
      style={{ width: collapsed ? 52 : 200 }}
    >
      {/* Logo + Toggle */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-[#2A2D3A]">
        {!collapsed && (
          <span className="text-sm font-bold text-[#26A69A] tracking-wide">Carteira</span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="ml-auto rounded p-1 text-[#6b7280] hover:text-[#D1D4DC] hover:bg-[#2A2D3A] transition text-lg leading-none"
          title={collapsed ? "Expandir menu" : "Recolher menu"}
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>

      {/* Nav links */}
      <nav className="flex-1 py-2 space-y-0.5 overflow-hidden">
        {LINKS.map((l) => {
          const active = pathname === l.href || pathname.startsWith(l.href + "/");
          return (
            <Link
              key={l.href}
              href={l.href}
              title={collapsed ? l.label : undefined}
              className={`flex items-center gap-2.5 px-3 py-2 text-sm transition rounded mx-1 ${
                active
                  ? "bg-[#26A69A]/15 text-[#26A69A] font-semibold"
                  : "text-[#D1D4DC] hover:bg-[#2A2D3A] hover:text-white"
              }`}
            >
              <span className="shrink-0 text-base">{l.icon}</span>
              {!collapsed && <span className="truncate">{l.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Logout */}
      <div className="border-t border-[#2A2D3A] p-2">
        <button
          onClick={logout}
          title="Sair"
          className="flex items-center gap-2.5 w-full px-3 py-2 text-sm text-[#6b7280] hover:text-[#EF5350] hover:bg-[#2A2D3A] transition rounded"
        >
          <span className="shrink-0 text-base">🚪</span>
          {!collapsed && <span>Sair</span>}
        </button>
      </div>
    </aside>
  );
}
