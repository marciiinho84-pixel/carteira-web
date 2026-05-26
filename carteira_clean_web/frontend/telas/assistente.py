"""
Página: Assistente IA — Chat conectado à carteira real via tool use.

Arquitetura:
  - Ferramentas definidas no Anthropic tools API (executadas localmente)
  - MCP server (porta 8001) está disponível para uso futuro com URL pública
"""

import json
import os
from pathlib import Path

import streamlit as st

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

MODEL = "claude-sonnet-4-6"

# Custo Sonnet 4.6: $3/1M input, $15/1M output
_CUSTO_IN = 3.0 / 1_000_000
_CUSTO_OUT = 15.0 / 1_000_000
_USD_BRL = 5.7

SYSTEM_PROMPT = """Você é o assistente financeiro pessoal do Marcio de Almeida Souza, \
integrado à sua ferramenta Carteira Clean.

Você tem acesso a ferramentas que consultam dados reais do portfólio. \
Use-as sempre que o usuário perguntar sobre sua carteira. \
NUNCA invente ou estime números financeiros.

DIRETRIZES:
- Responda em português brasileiro
- Seja preciso com números (use R$ com formatação brasileira: R$ 1.234.567,89)
- Contextualize os dados — não apenas repita números
- Ao detectar concentração elevada, mencione proativamente
- Perguntas fora do escopo financeiro: responda brevemente \
e redirecione para o portfólio"""

# Definição do tool para a Anthropic API
TOOLS = [
    {
        "name": "obter_posicoes",
        "description": (
            "Retorna todas as posições ativas da carteira com valor atual, "
            "custo médio, P&L, alocação percentual por ativo e por classe, "
            "e alertas automáticos de concentração. "
            "Use quando o usuário perguntar sobre: posições, portfólio, "
            "o que tenho, quanto vale, alocação, diversificação, concentração, "
            "maior posição, P&L, patrimônio."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    }
]


def _executar_tool(nome: str, _entrada: dict) -> str:
    if nome == "obter_posicoes":
        from carteira_clean_web.backend.mcp.tools.portfolio import fn_obter_posicoes
        resultado = fn_obter_posicoes()
        return json.dumps(resultado, ensure_ascii=False, default=str)
    return json.dumps({"erro": f"Tool desconhecida: {nome}"})


def _get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        env_path = Path(__file__).resolve().parents[3] / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    return anthropic.Anthropic(api_key=api_key) if api_key else None


def _enviar_mensagem(client, mensagens_api: list) -> tuple[str, list[str], object]:
    """
    Loop de tool use: envia mensagem, executa tools se necessário, retorna resposta final.
    Retorna: (texto_resposta, tools_usadas, usage)
    """
    tools_usadas = []
    msgs = list(mensagens_api)

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=msgs,
            tools=TOOLS,
        )

        if response.stop_reason == "end_turn":
            texto = ""
            for block in response.content:
                if hasattr(block, "text"):
                    texto += block.text
            return texto, tools_usadas, response.usage

        if response.stop_reason == "tool_use":
            # Adicionar resposta do assistente ao histórico temporário
            msgs.append({"role": "assistant", "content": response.content})

            # Executar cada tool call e coletar resultados
            resultados = []
            for block in response.content:
                if not hasattr(block, "type") or block.type != "tool_use":
                    continue
                tools_usadas.append(block.name)
                saida = _executar_tool(block.name, getattr(block, "input", {}))
                resultados.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": saida,
                })

            msgs.append({"role": "user", "content": resultados})
            continue

        # Outro stop_reason inesperado — retornar o que tiver
        texto = ""
        for block in response.content:
            if hasattr(block, "text"):
                texto += block.text
        return texto, tools_usadas, response.usage


def render():
    st.title("🤖 Assistente — Carteira Clean")

    if not HAS_ANTHROPIC:
        st.error("Pacote `anthropic` não instalado. Execute `pip install anthropic`.")
        return

    # ── Estado da sessão ──────────────────────────────────────────
    if "mensagens" not in st.session_state:
        st.session_state["mensagens"] = []
    if "tokens_total_in" not in st.session_state:
        st.session_state["tokens_total_in"] = 0
    if "tokens_total_out" not in st.session_state:
        st.session_state["tokens_total_out"] = 0

    # ── Sidebar ────────────────────────────────────────────────────
    with st.sidebar:
        st.subheader("🤖 Assistente")
        if st.button("🗑️ Nova conversa", use_container_width=True):
            st.session_state["mensagens"] = []
            st.session_state["tokens_total_in"] = 0
            st.session_state["tokens_total_out"] = 0
            st.rerun()
        st.divider()
        n_in = st.session_state["tokens_total_in"]
        n_out = st.session_state["tokens_total_out"]
        custo_brl = (n_in * _CUSTO_IN + n_out * _CUSTO_OUT) * _USD_BRL
        st.caption(f"Tokens entrada: {n_in:,}")
        st.caption(f"Tokens saída: {n_out:,}")
        st.caption(f"Custo sessão: ~R$ {custo_brl:.4f}")

    # ── Histórico de mensagens ────────────────────────────────────
    for msg in st.session_state["mensagens"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["display"])

    # ── Input do usuário ──────────────────────────────────────────
    prompt = st.chat_input("Pergunte sobre sua carteira...")
    if not prompt:
        return

    with st.chat_message("user"):
        st.markdown(prompt)

    # Adicionar ao histórico
    st.session_state["mensagens"].append({
        "role": "user",
        "content": prompt,
        "display": prompt,
    })

    # ── Chamar API ────────────────────────────────────────────────
    client = _get_client()
    if not client:
        st.error("❌ ANTHROPIC_API_KEY não configurada. Adicione ao arquivo .env na raiz do projeto.")
        return

    # Mensagens API: apenas role + content (sem campo display)
    msgs_api = [{"role": m["role"], "content": m["content"]} for m in st.session_state["mensagens"]]

    with st.chat_message("assistant"):
        status = st.empty()
        status.caption("🔄 Consultando...")
        try:
            texto, tools_usadas, usage = _enviar_mensagem(client, msgs_api)
            status.empty()
            for t in tools_usadas:
                st.caption(f"🔧 Consultou: `{t}`")
            st.markdown(texto or "(sem resposta)")
        except anthropic.AuthenticationError:
            status.empty()
            st.error("❌ API key inválida.")
            return
        except anthropic.APIConnectionError:
            status.empty()
            st.error("❌ Sem conexão com a API Anthropic.")
            return
        except Exception as e:
            status.empty()
            st.error(f"❌ Erro: {e}")
            return

    # Salvar no histórico
    st.session_state["mensagens"].append({
        "role": "assistant",
        "content": texto,
        "display": texto,
    })

    # Atualizar tokens
    if usage:
        st.session_state["tokens_total_in"] += getattr(usage, "input_tokens", 0)
        st.session_state["tokens_total_out"] += getattr(usage, "output_tokens", 0)
