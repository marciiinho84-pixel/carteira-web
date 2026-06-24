"use client";

import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
} from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import AutomacaoSettings from "@/components/maestro/AutomacaoSettings";
import { useAutomacao } from "@/lib/automacao";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "https://minhacarteira.duckdns.org/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("carteira_token");
}

// ── Tipos ────────────────────────────────────────────────────────────────────

interface AGEvent {
  type: string;
  messageId?: string;
  toolCallId?: string;
  toolCallName?: string;
  delta?: string;
  role?: string;
  parentMessageId?: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCallState[];
}

interface ToolCallState {
  id: string;
  name: string;
  args: string;
  done: boolean;
}

// ── Conversa sidebar ─────────────────────────────────────────────────────────

interface Conversa {
  id: number;
  titulo: string;
  criado_em?: string;
  total_msgs?: number;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatTime(iso: string | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

// ── ToolCallIndicator ────────────────────────────────────────────────────────

function ToolCallIndicator({ tool, done }: { tool: ToolCallState; done: boolean }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="flex items-start gap-2 my-1.5 text-xs">
      <span className="mt-0.5 text-[#26A69A]">{done ? "✓" : "⟳"}</span>
      <div className="flex-1">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[#6b7280] hover:text-[#D1D4DC] transition-colors text-left"
        >
          {done ? "chamou" : "chamando"}{" "}
          <span className="font-mono text-[#26A69A]">{tool.name}</span>
          {tool.args && tool.args !== "{}" && (
            <span className="ml-1 text-[#6b7280]">▾</span>
          )}
        </button>
        {expanded && tool.args && (
          <pre className="mt-1 text-[10px] text-[#6b7280] bg-[#0F1117] rounded p-2 overflow-x-auto max-h-32">
            {(() => {
              try {
                return JSON.stringify(JSON.parse(tool.args), null, 2);
              } catch {
                return tool.args;
              }
            })()}
          </pre>
        )}
      </div>
    </div>
  );
}

// ── MessageBubble ─────────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-[#26A69A]/20 border border-[#26A69A]/40 flex items-center justify-center shrink-0 mt-1">
          <span className="text-xs text-[#26A69A]">M</span>
        </div>
      )}
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-[#26A69A]/20 border border-[#26A69A]/30 text-[#D1D4DC]"
            : "bg-[#1A1D27] border border-[#2A2D3A] text-[#D1D4DC]"
        }`}
      >
        {/* Tool calls */}
        {msg.toolCalls && msg.toolCalls.length > 0 && (
          <div className="mb-2 pb-2 border-b border-[#2A2D3A]">
            {msg.toolCalls.map((tc) => (
              <ToolCallIndicator key={tc.id} tool={tc} done={tc.done} />
            ))}
          </div>
        )}

        {/* Content */}
        <div className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</div>
      </div>
      {isUser && (
        <div className="w-7 h-7 rounded-full bg-[#6366F1]/20 border border-[#6366F1]/40 flex items-center justify-center shrink-0 mt-1">
          <span className="text-xs text-[#6366F1]">V</span>
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function MaestroPage() {
  const router = useRouter();
  const { config: automacaoConfig, nivelMaximo } = useAutomacao();

  const [conversas, setConversas] = useState<Conversa[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string>(() =>
    typeof window !== "undefined"
      ? (localStorage.getItem("maestro_thread_id") ?? crypto.randomUUID())
      : crypto.randomUUID()
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Save thread_id
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("maestro_thread_id", activeThreadId);
    }
  }, [activeThreadId]);

  // Check auth
  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
    }
  }, [router]);

  // Load conversas
  const loadConversas = useCallback(async () => {
    try {
      const token = getToken();
      const res = await fetch(`${API_BASE}/conversas`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setConversas(data.conversas ?? data ?? []);
      }
    } catch {
      // silently fail
    }
  }, []);

  useEffect(() => {
    loadConversas();
  }, [loadConversas]);

  // ── Send message ──────────────────────────────────────────────────────────

  const sendMessage = useCallback(
    async (userText: string) => {
      if (!userText.trim() || streaming) return;

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: userText.trim(),
      };

      const assistantMsgId = crypto.randomUUID();
      const assistantMsg: ChatMessage = {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        toolCalls: [],
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setInput("");
      setStreaming(true);

      // Build messages for API (exclude empty placeholders)
      const history = [...messages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const token = getToken();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch(`${API_BASE}/maestro/chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            messages: history,
            thread_id: activeThreadId,
            nivel_automacao: automacaoConfig,
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, content: `Erro: ${err.detail ?? res.statusText}` }
                : m
            )
          );
          return;
        }

        const reader = res.body?.getReader();
        if (!reader) return;

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const json = line.slice(6).trim();
            if (!json) continue;

            let event: AGEvent;
            try {
              event = JSON.parse(json) as AGEvent;
            } catch {
              continue;
            }

            setMessages((prev) => {
              const idx = prev.findIndex((m) => m.id === assistantMsgId);
              if (idx === -1) return prev;
              const msg = { ...prev[idx] };

              switch (event.type) {
                case "TEXT_MESSAGE_CONTENT":
                  msg.content = (msg.content ?? "") + (event.delta ?? "");
                  break;

                case "TOOL_CALL_START":
                  msg.toolCalls = [
                    ...(msg.toolCalls ?? []),
                    {
                      id: event.toolCallId ?? "",
                      name: event.toolCallName ?? "",
                      args: "",
                      done: false,
                    },
                  ];
                  break;

                case "TOOL_CALL_ARGS_DELTA": {
                  const tcs = (msg.toolCalls ?? []).map((tc) =>
                    tc.id === event.toolCallId
                      ? { ...tc, args: tc.args + (event.delta ?? "") }
                      : tc
                  );
                  msg.toolCalls = tcs;
                  break;
                }

                case "TOOL_CALL_END": {
                  const tcs = (msg.toolCalls ?? []).map((tc) =>
                    tc.id === event.toolCallId ? { ...tc, done: true } : tc
                  );
                  msg.toolCalls = tcs;
                  break;
                }
              }

              const next = [...prev];
              next[idx] = msg;
              return next;
            });
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    content: `Erro de conexão: ${(err as Error).message}`,
                  }
                : m
            )
          );
        }
      } finally {
        setStreaming(false);
        abortRef.current = null;
        loadConversas();
      }
    },
    [messages, streaming, activeThreadId, automacaoConfig, loadConversas]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const newConversation = () => {
    const id = crypto.randomUUID();
    setActiveThreadId(id);
    setMessages([]);
  };

  // 9a: carregar mensagens de uma conversa existente do DB
  const openConversation = useCallback(async (convId: number) => {
    setActiveThreadId(String(convId));
    setMessages([]);
    try {
      const token = getToken();
      const res = await fetch(`${API_BASE}/conversas/${convId}/mensagens`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data: { role: string; content: string }[] = await res.json();
        setMessages(data.map((m) => ({
          id: crypto.randomUUID(),
          role: m.role as "user" | "assistant",
          content: m.content,
        })));
      }
    } catch {
      // silently fail — conversa abre vazia
    }
  }, []);

  // 9c: apagar conversa
  const deleteConversation = useCallback(async (convId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const token = getToken();
    await fetch(`${API_BASE}/conversas/${convId}`, {
      method: "DELETE",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (activeThreadId === String(convId)) newConversation();
    loadConversas();
  }, [activeThreadId, loadConversas]);  // eslint-disable-line react-hooks/exhaustive-deps

  const stopStreaming = () => {
    abortRef.current?.abort();
    setStreaming(false);
  };

  const NIVEL_COLOR: Record<string, string> = {
    L1: "#6b7280",
    L2: "#26A69A",
    L3: "#F59E0B",
    L4: "#EF5350",
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{ backgroundColor: "#0F1117", color: "#D1D4DC" }}
    >
      {/* ── Sidebar ── */}
      {sidebarOpen && (
        <aside
          className="w-64 flex flex-col shrink-0 border-r"
          style={{ borderColor: "#2A2D3A", backgroundColor: "#0D0F17" }}
        >
          {/* Sidebar header */}
          <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "#2A2D3A" }}>
            <span className="text-sm font-semibold text-[#D1D4DC]">Maestro</span>
            <button
              onClick={newConversation}
              className="text-xs px-2 py-1 rounded border border-[#2A2D3A] text-[#6b7280] hover:text-[#D1D4DC] hover:border-[#26A69A] transition-colors"
            >
              + Nova
            </button>
          </div>

          {/* Conversations list — 9b: ocultar conversas sem mensagens */}
          <div className="flex-1 overflow-y-auto py-2">
            {conversas.filter((c) => (c.total_msgs ?? 0) > 0).length === 0 ? (
              <p className="text-xs text-[#6b7280] px-4 py-2">Sem conversas ainda</p>
            ) : (
              conversas
                .filter((c) => (c.total_msgs ?? 0) > 0)
                .map((c) => (
                  <div
                    key={c.id}
                    className={`group flex items-center gap-1 pr-2 transition-colors hover:bg-[#1A1D27] ${
                      activeThreadId === String(c.id) ? "bg-[#1A1D27]" : ""
                    }`}
                  >
                    {/* 9a: clicar abre conversa carregando mensagens do backend */}
                    <button
                      onClick={() => openConversation(c.id)}
                      className="flex-1 text-left px-4 py-2.5 text-xs"
                    >
                      <div className={`truncate ${activeThreadId === String(c.id) ? "text-[#D1D4DC]" : "text-[#6b7280]"}`}>
                        {c.titulo || "Conversa"}
                      </div>
                      {c.criado_em && (
                        <div className="text-[10px] text-[#6b7280] mt-0.5">
                          {formatTime(c.criado_em)}
                        </div>
                      )}
                    </button>
                    {/* 9c: botão apagar */}
                    <button
                      onClick={(e) => deleteConversation(c.id, e)}
                      className="opacity-0 group-hover:opacity-100 text-[#6b7280] hover:text-[#EF5350] transition-all p-1 rounded shrink-0"
                      title="Apagar conversa"
                    >
                      ✕
                    </button>
                  </div>
                ))
            )}
          </div>

          {/* Bottom links */}
          <div className="border-t px-4 py-3 space-y-2" style={{ borderColor: "#2A2D3A" }}>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="w-full text-left text-xs text-[#6b7280] hover:text-[#D1D4DC] transition-colors flex items-center gap-2"
            >
              <span>⚙</span>
              Automação
            </button>
            <Link
              href="/sala-de-comando"
              className="block text-xs text-[#6b7280] hover:text-[#D1D4DC] transition-colors"
            >
              ← Sala de Comando
            </Link>
          </div>
        </aside>
      )}

      {/* ── Main area ── */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <header
          className="flex items-center gap-3 px-4 py-3 border-b shrink-0"
          style={{ borderColor: "#2A2D3A", backgroundColor: "#0F1117" }}
        >
          <Link
            href="/sala-de-comando"
            className="text-[#6b7280] hover:text-[#D1D4DC] transition-colors text-xs px-2 py-1 rounded border border-[#2A2D3A] hover:border-[#4A4D5A]"
            title="Voltar ao início"
          >
            ← Home
          </Link>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-[#6b7280] hover:text-[#D1D4DC] transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <div className="flex items-center gap-2 flex-1">
            <div className="w-6 h-6 rounded-full bg-[#26A69A]/20 border border-[#26A69A]/40 flex items-center justify-center">
              <span className="text-xs text-[#26A69A]">M</span>
            </div>
            <span className="text-sm font-medium text-[#D1D4DC]">Maestro</span>
            <span className="text-xs text-[#6b7280]">—</span>
            <span className="text-xs text-[#6b7280]">claude-opus-4-8 · 31 tools</span>
          </div>

          {/* Automação badge */}
          <div
            className="flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-xs"
            style={{
              borderColor: NIVEL_COLOR[nivelMaximo] + "40",
              color: NIVEL_COLOR[nivelMaximo],
              backgroundColor: NIVEL_COLOR[nivelMaximo] + "10",
            }}
          >
            <span>{nivelMaximo}</span>
          </div>

          {streaming && (
            <button
              onClick={stopStreaming}
              className="text-xs text-[#EF5350] hover:text-[#EF5350]/80 transition-colors"
            >
              Parar
            </button>
          )}
        </header>

        {/* Settings panel */}
        {showSettings && (
          <div
            className="border-b px-4 py-4"
            style={{ borderColor: "#2A2D3A", backgroundColor: "#0D0F17" }}
          >
            <AutomacaoSettings />
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center gap-4 py-16">
              <div className="w-16 h-16 rounded-full bg-[#26A69A]/10 border border-[#26A69A]/20 flex items-center justify-center">
                <span className="text-2xl">M</span>
              </div>
              <div>
                <p className="text-[#D1D4DC] font-medium mb-1">Maestro da Carteira</p>
                <p className="text-sm text-[#6b7280] max-w-sm">
                  Consulte posições, performance, análise técnica, fundamentos, perfil comportamental
                  e muito mais — com dados reais da sua carteira.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2 max-w-sm">
                {[
                  "Como está minha aderência ao IPS?",
                  "Analise a performance do mês",
                  "Quais são os vieses comportamentais detectados?",
                  "Qual o regime de mercado atual?",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => sendMessage(suggestion)}
                    className="text-left text-xs p-3 rounded-lg border border-[#2A2D3A] hover:border-[#26A69A]/40 hover:bg-[#1A1D27] transition-colors text-[#6b7280] hover:text-[#D1D4DC]"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}

          {/* Streaming indicator */}
          {streaming && (
            <div className="flex gap-3 justify-start">
              <div className="w-7 h-7 rounded-full bg-[#26A69A]/20 border border-[#26A69A]/40 flex items-center justify-center shrink-0 mt-1">
                <span className="text-xs text-[#26A69A]">M</span>
              </div>
              <div className="bg-[#1A1D27] border border-[#2A2D3A] rounded-2xl px-4 py-3">
                <span className="inline-flex gap-1">
                  {[0, 150, 300].map((delay) => (
                    <span
                      key={delay}
                      className="w-1.5 h-1.5 rounded-full bg-[#26A69A] animate-bounce"
                      style={{ animationDelay: `${delay}ms` }}
                    />
                  ))}
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div
          className="px-4 py-3 border-t shrink-0"
          style={{ borderColor: "#2A2D3A", backgroundColor: "#0F1117" }}
        >
          <div
            className="flex items-end gap-2 rounded-xl border p-2"
            style={{ borderColor: "#2A2D3A", backgroundColor: "#1A1D27" }}
          >
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Pergunte ao Maestro... (Enter para enviar, Shift+Enter para nova linha)"
              rows={1}
              className="flex-1 bg-transparent text-sm text-[#D1D4DC] placeholder-[#6b7280] resize-none focus:outline-none py-1 px-1 min-h-[32px] max-h-[120px]"
              style={{ lineHeight: "1.5" }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = Math.min(el.scrollHeight, 120) + "px";
              }}
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || streaming}
              className="w-8 h-8 rounded-lg flex items-center justify-center transition-all disabled:opacity-40"
              style={{ backgroundColor: "#26A69A" }}
            >
              <svg className="w-4 h-4 text-[#0F1117]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>
          </div>
          <p className="text-[10px] text-[#6b7280] mt-1.5 text-center">
            Instrumento de gestão pessoal — não é consultoria CVM regulamentada.
          </p>
        </div>
      </div>
    </div>
  );
}
