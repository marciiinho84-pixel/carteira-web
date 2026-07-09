"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleGoogle() {
    setLoading(true);
    setError("");
    try {
      await signIn("google", { callbackUrl: "/dashboard" });
    } catch {
      setError("Erro ao iniciar login. Tente novamente.");
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-app)" }}>
      <div
        className="w-full max-w-sm rounded-2xl border p-8"
        style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: "0 4px 20px rgba(61,54,41,0.10)" }}
      >
        <div className="mb-6 text-center">
          <h1
            className="text-xl font-semibold"
            style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
          >
            App Minha Carteira
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>Acesso restrito ao investidor</p>
        </div>

        {error && (
          <div
            className="mb-4 rounded-lg border px-3 py-2 text-xs"
            style={{ borderColor: "rgba(180,68,44,0.3)", background: "rgba(180,68,44,0.08)", color: "var(--negative)" }}
          >
            {error}
          </div>
        )}

        <button
          onClick={handleGoogle}
          disabled={loading}
          className="flex w-full items-center justify-center gap-3 rounded-lg border px-4 py-3 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50"
          style={{ borderColor: "var(--border)", background: "var(--bg-card-alt)", color: "var(--text-body)" }}
          onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background = "var(--border-soft)"; }}
          onMouseLeave={(e) => (e.currentTarget.style.background = "var(--bg-card-alt)")}
        >
          {loading ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-t-transparent" style={{ borderColor: "var(--text-faint)", borderTopColor: "transparent" }} />
          ) : (
            <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
          )}
          {loading ? "Redirecionando…" : "Entrar com Google"}
        </button>

        <p className="mt-6 text-center text-xs" style={{ color: "var(--text-faint)" }}>
          Apenas o e-mail autorizado tem acesso.
        </p>
      </div>
    </main>
  );
}
