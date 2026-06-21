"use client";

import { useState } from "react";
import { auth } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("marciiinho84@gmail.com");
  const [status, setStatus] = useState<"idle" | "loading" | "sent" | "error">("idle");
  const [message, setMessage] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    try {
      const res = await auth.requestLink(email);
      setMessage(res.message);
      setStatus("sent");
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : "Erro ao solicitar link.");
      setStatus("error");
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-[#0F1117]">
      <div className="w-full max-w-sm rounded-2xl border border-zinc-800 bg-zinc-900 p-8 shadow-xl">
        <h1 className="mb-1 text-xl font-semibold text-zinc-100">App Minha Carteira</h1>
        <p className="mb-6 text-sm text-zinc-400">
          Informe seu e-mail para receber o link de acesso.
        </p>

        {status === "sent" ? (
          <div className="rounded-lg border border-teal-700 bg-teal-900/30 p-4 text-sm text-teal-300">
            <p className="font-medium">Link gerado com sucesso.</p>
            <p className="mt-1 text-teal-400">
              Copie o link dos logs do servidor e cole no browser para entrar.
            </p>
            <p className="mt-2 text-xs text-zinc-500">
              (docker logs carteira-web-backend-1 | grep MAGIC)
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-400">
                E-mail
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2
                           text-sm text-zinc-100 placeholder:text-zinc-500
                           focus:border-teal-500 focus:outline-none"
              />
            </div>

            {status === "error" && (
              <p className="rounded-lg border border-red-800 bg-red-900/30 px-3 py-2
                            text-xs text-red-300">
                {message}
              </p>
            )}

            <button
              type="submit"
              disabled={status === "loading"}
              className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium
                         text-white transition hover:bg-teal-500
                         disabled:cursor-not-allowed disabled:opacity-50"
            >
              {status === "loading" ? "Aguarde..." : "Enviar link de acesso"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
