const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "https://minhacarteira.duckdns.org/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("carteira_token");
}

export function setToken(token: string) {
  localStorage.setItem("carteira_token", token);
}

export function clearToken() {
  localStorage.removeItem("carteira_token");
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? "Erro na API");
  }
  return res.json() as Promise<T>;
}

export const auth = {
  me: () => apiFetch<{ email: string }>("/auth/me"),
};

export const apiStatus = () =>
  apiFetch<{ status: string; version: string }>("/health");

export type KPIs = {
  engine_ok: boolean;
  patrimonio_total?: number;
  patrimonio_gerida?: number;
  patrimonio_funcef?: number;
  twr_ytd?: number;
  twr_total_ytd?: number;
  cdi_ytd?: number;
  ibov_ytd?: number;
  excesso_cdi?: number;
  twr_anualizado?: number;
  var_dia_pct?: number | null;
  nivel_automacao?: string;
  calculado_em?: string;
  data_referencia?: string;
};

export type Tese = {
  id: number;
  ticker: string;
  bloco_ips?: string;
  racional?: string;
  criterio_invalidacao?: string;
  nivel_invalidacao: "VERDE" | "AMARELO" | "VERMELHO";
  status: string;
  dias_desde_criacao?: number;
};

export type Vies = {
  nome_vies: string;
  detectado: boolean;
  severidade: "INFO" | "ATENCAO" | "CRITICO";
  fato_mensuravel: string;
};

export type BlocoIPS = {
  bloco: string;
  pct_real: number;
  pct_alvo: number;
  banda_min: number;
  banda_max: number;
  status: "OK" | "ABAIXO" | "ACIMA";
};

export type Comportamental = {
  indice_coerencia: number;
  vieses: Vies[];
  blocos: BlocoIPS[];
};

export type CategoriaObservacao =
  | "ALERTA"
  | "TESE"
  | "IPS"
  | "TECNICO"
  | "FUNDAMENTALISTA"
  | "NOTICIA"
  | "MACRO";

export type Observacao = {
  id: number;
  categoria: CategoriaObservacao;
  ativo?: string | null;
  ativos_relacionados: string[];
  conteudo: string;
  url?: string | null;
  criado_em?: string;
};

export type Meta = {
  engine_ok?: boolean;
  patrimonio_atual?: number;
  meta?: number;
  pct_atingido?: number;
  twr_anualizado?: number;
  aporte_anual?: number;
  projecao_ano_meta?: number | null;
  ritmo_mensal_atual?: number;
  ritmo_mensal_necessario?: number;
};

export type SalaDeComandoData = {
  kpis: KPIs;
  teses: Tese[];
  comportamental: Comportamental;
  observacoes: Observacao[];
  meta: Meta;
};

export const salaDeComando = () =>
  apiFetch<SalaDeComandoData>("/sala-de-comando");

export const marcarObservacaoVisualizada = (id: number) =>
  apiFetch<{ ok: boolean; id: number }>(`/sala-de-comando/observacoes/${id}/visualizar`, {
    method: "POST",
  });
