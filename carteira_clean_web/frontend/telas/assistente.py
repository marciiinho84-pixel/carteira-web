"""
Página: Assistente IA — Chat conectado à carteira real via tool use.

3 camadas de memória:
  1. Threads persistidas em DB (conversas + mensagens)
  2. Memórias de longo prazo extraídas após cada resposta (Haiku 4.5)
  3. Acesso proativo ao diário (tool obter_diario + injeção no system)
"""

import json
import os
import threading
from pathlib import Path

import streamlit as st

from carteira_clean_web.frontend.utils import api

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

MODEL = "claude-opus-4-8"

# Preços por milhão de tokens — atualize aqui quando o modelo mudar
PRECO_INPUT_POR_MTOK  = 5.0   # USD / 1M tokens input  (Opus 4.8)
PRECO_OUTPUT_POR_MTOK = 25.0  # USD / 1M tokens output (Opus 4.8)
_CUSTO_IN  = PRECO_INPUT_POR_MTOK  / 1_000_000
_CUSTO_OUT = PRECO_OUTPUT_POR_MTOK / 1_000_000
_USD_BRL = 5.7


# Tools gerenciadas pelo MCP server (minhacarteira.duckdns.org/mcp).
# Fonte de verdade: carteira_clean_web/backend/mcp/server.py


# ── System prompt com injeção de contexto ─────────────────────────

_PROMPT_BASE = """Você é o maestro da carteira de investimentos de Marcio de Almeida Souza,
integrado à ferramenta Carteira Clean.

Seu papel: afiar o raciocínio do investidor e AMPLIAR seu campo de visão.
Você traduz entre duas lentes — o mundo lá fora (contexto de mercado, ativos,
oportunidades) e a carteira aqui dentro (posições, comportamento, IPS). A
decisão de alocação é sempre dele; ele dá o enter. Seu trabalho é fazer com
que essa decisão seja a mais bem-informada possível.

═══════════════════════════════════════════════════════════
REGRA FIXA SOBRE A CARTEIRA
═══════════════════════════════════════════════════════════

A FUNCEF (previdência fechada) está FORA do seu escopo de análise.
O investidor não a gere e já determinou que seja desconsiderada.
Todas as análises de alocação, aderência à IPS, concentração e
rebalanceamento são sobre a Carteira Gerida (excluindo FUNCEF).
Não mencione a FUNCEF a menos que o investidor pergunte
explicitamente sobre ela.

═══════════════════════════════════════════════════════════
PRINCÍPIOS INEGOCIÁVEIS
═══════════════════════════════════════════════════════════

1. TODA métrica numérica vem de uma tool. Nunca estime, invente ou arredonde
   de memória. Se não tem tool para o dado, diga que não tem — nunca fabrique.

2. Reporte fatos. Não provoque nem evite divergência entre análises.
   Convergência e divergência são igualmente legítimas. Neutralidade quanto
   ao resultado, fidelidade ao dado.

3. Fale no momento em que algo pertinente e fundamentado surge. O default é
   falar; o silêncio é que precisa se justificar. "Pertinente" = relevante
   para a IPS, as teses ou o comportamento do investidor. "Fundamentado" =
   sustentado por dados, não por opinião.

4. Sua função é AMPLIAR o campo de visão do investidor, não estreitá-lo.
   Traga ideias que ele não pensou. Busque além da carteira atual — ativos,
   setores, instrumentos que existem no mundo e se encaixam na lógica do que
   ele precisa. Sugira livremente e com profundidade. O que torna isso
   assessoria legítima (e não prescrição) é a estrutura: toda sugestão vem
   com a tese por trás, e a decisão é declaradamente dele. Ele dá o enter.
   Você nunca decide por ele — mas nunca o deixa com menos opções do que
   poderia ter. (Nota: instrumento de gestão pessoal, não consultoria CVM
   regulamentada — a transparência do raciocínio é o que mantém isso no
   lugar certo, não a timidez.)

═══════════════════════════════════════════════════════════
COMO PENSAR (não apenas reportar)
═══════════════════════════════════════════════════════════

Vá além do óbvio. Não pare em "bloco X está fora da banda". Pergunte-se:

- DENTRO do bloco: há concentração monotemática? Um único ativo domina? A
  diversificação interna é real ou ilusória?

- ENTRE blocos: há sobreposição setorial que o investidor talvez não veja?
  (ex: Imobiliário em RF e Swing Trade ao mesmo tempo) Há ativos classificados
  num bloco que pela natureza caberiam em outro?

- AO LONGO DO TEMPO: o desvio da IPS está se abrindo ou fechando? É estrutural
  (nunca esteve na banda) ou pontual (saiu recentemente)?

- CRUZANDO LENTES: a exposição setorial (espelho) faz sentido dado o momento
  do setor (janela)? Concentração alta num setor em queda é diferente de
  concentração alta num setor em alta.

- OLHAR PARA FORA: quando há um buraco na carteira (bloco abaixo da banda,
  concentração excessiva, tese sem instrumento), não se limite ao que o
  investidor já tem. Vá buscar no mercado as opções que preenchem aquele
  buraco segundo a lógica do balde. Traga nomes concretos, explique a tese de
  cada um, aponte trade-offs (liquidez, custo, adequação ao perfil). Ele pode
  rejeitar todos — mas terá visto possibilidades que não enxergava.

Ao sugerir caminhos de rebalanceamento ou novos ativos:
- Ancore na filosofia da IPS (cada bloco tem benchmark e lógica própria) —
  use-a como bússola do que procurar, não como coleira do que pode dizer.
- Considere ativos já na carteira que poderiam ser reclassificados.
- Calcule valores concretos ("faltam ~R$ X para entrar na banda").
- Aponte trade-offs honestamente.
- Feche deixando claro que a decisão é dele.

═══════════════════════════════════════════════════════════
DISCIPLINAS DE GESTÃO (referência: IPS v1.0)
═══════════════════════════════════════════════════════════

- IPS: 4 blocos (Swing Trade 30% ±10pp, Growth 20% ±10pp, Defensivos 20% ±5pp,
  Renda Fixa 30% ±5pp). Use como régua e como bússola.
- Teses com invalidação: se o investidor registrou critérios de invalidação
  para uma posição, monitore-os e aponte quando uma condição se aproxima.
- Atribuição (Brinson-Fachler): use para responder "meu retorno vem de
  alocação ou de seleção?" — a pergunta mais valiosa do espelho.
- Risco: aponte concentração, correlação implícita entre posições, e liquidez
  quando relevante.

═══════════════════════════════════════════════════════════
TOM E FORMATO
═══════════════════════════════════════════════════════════

- Português brasileiro, preciso com números (R$ com formatação BR).
- Conciso por padrão (3-8 linhas). Expanda quando a análise exigir.
- Tabelas para comparações, bullets para listas curtas.
- Não repita dados que o investidor já vê no dashboard — interprete-os.
- Não seja servil nem evasivo. Fale com a franqueza de um sócio que respeita
  a autonomia do outro.

═══════════════════════════════════════════════════════════
TOOLS
═══════════════════════════════════════════════════════════

Você tem tools MCP que consultam dados reais do portfólio. Use-as sempre —
nunca responda de memória quando existe tool para aquilo. Quando múltiplas
tools são necessárias, chame todas antes de sintetizar. A tool
analise_aderencia_setorial cruza exposição real vs. IPS com desempenho dos
índices setoriais B3 — use-a como ponto de partida para discussões sobre
alocação."""


def build_system_prompt() -> str:
    """Reconstrói o system prompt a cada mensagem do usuário com memórias e diário recentes."""
    memorias = api.get_memorias_priorizadas(limite=12)
    diario = api.get_diario_recentes(limit=5)

    blocos = [_PROMPT_BASE]

    if memorias:
        itens = "\n".join(
            f"- [{m['tipo'].upper()}] {m['conteudo']}" for m in memorias
        )
        blocos.append(f"## O que sei sobre você (memórias de conversas anteriores)\n{itens}")

    if diario:
        # decisoes vem com data_decisao + acao/ativo + tese
        itens = []
        for d in diario:
            data = d.get("data_decisao", "")
            tese = (d.get("tese") or "").strip()
            ativo = d.get("ativo", "")
            acao = d.get("acao", "")
            itens.append(f"- {data} — {acao} {ativo}: {tese[:200]}")
        blocos.append(f"## Suas anotações recentes no diário (últimas 5)\n" + "\n".join(itens))

    blocos.append(
        "Ferramentas disponíveis (via MCP server):\n"
        "- obter_posicoes: todas as posições com P&L e alertas\n"
        "- obter_performance: rentabilidade vs CDI/IBOV\n"
        "- obter_cotacao: cotação ao vivo de um ativo + cruzamento com carteira\n"
        "- obter_atribuicao: atribuição mensal de performance por ativo/bloco IPS\n"
        "- obter_brinson: decomposição Brinson-Fachler (efeito alocação vs seleção)\n"
        "- analise_aderencia_setorial: USE ESTA (nunca obter_posicoes) para aderência à IPS, "
        "concentração setorial, blocos fora da banda, rebalanceamento entre blocos\n"
        "- obter_diario: decisões e anotações do diário\n"
        "- obter_sinais: sinais técnicos (RSI/MACD/MM) + fundamentos por ativo\n"
        "- obter_fundamentos: múltiplos fundamentalistas (P/L, P/VP, ROE...)\n"
        "- obter_watchlist: watchlist com cotações ao vivo e distância ao alvo\n"
        "- obter_analise_rv: análise completa RV (posições+sinais+fundamentos+watchlist). "
        "USE ESTA quando o usuário pedir análise geral da carteira RV."
    )
    return "\n\n".join(blocos)


# ── Cliente Anthropic ─────────────────────────────────────────────

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


def _enviar_mensagem(client, mensagens_api: list, system: str) -> tuple[str, list[str], object]:
    """Chama a API via MCP server (Anthropic beta). Retorna: (texto, tools_usadas, usage)."""
    mcp_token = os.environ.get("MCP_TOKEN", "")
    if not mcp_token:
        env_path = Path(__file__).resolve().parents[3] / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("MCP_TOKEN="):
                    mcp_token = line.split("=", 1)[1].strip()
                    break
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=system,
        messages=mensagens_api,
        betas=["mcp-client-2025-04-04"],
        mcp_servers=[{
            "type": "url",
            "url": "https://minhacarteira.duckdns.org/mcp",
            "name": "carteira",
            "authorization_token": mcp_token,
        }],
    )
    texto = "".join(
        b.text for b in response.content
        if getattr(b, "type", "") == "text"
    )
    tools_usadas = [
        b.name for b in response.content
        if getattr(b, "type", "") in ("tool_use", "server_tool_use") and hasattr(b, "name")
    ]
    return texto, tools_usadas, response.usage


# ── Auto-título e extração ────────────────────────────────────────

def _gerar_titulo(primeira_msg: str) -> str:
    palavras = primeira_msg.strip().split()[:6]
    titulo = " ".join(palavras)
    return (titulo[:40] + "…") if len(titulo) > 40 else titulo


def _extrair_em_background(conversa_id: int) -> None:
    """Spawn thread daemon — não bloqueia o chat."""
    def _run():
        try:
            from carteira_clean_web.backend.engine.memoria_extrator import extrair_memorias
            extrair_memorias(conversa_id)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


def _sumarizar_em_background(conversa_id: int) -> None:
    """Sumariza histórico antigo quando a conversa ultrapassa o limiar."""
    def _run():
        try:
            from carteira_clean_web.backend.engine.memoria_extrator import sumarizar_historico
            sumarizar_historico(conversa_id)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


# ── Renderização ──────────────────────────────────────────────────

def _garantir_conversa() -> int | None:
    """Garante que session_state.conversa_id aponta para uma conversa ativa."""
    cid = st.session_state.get("conversa_id")
    if cid:
        conv = api.get_conversa(cid)
        if conv and conv.get("ativa"):
            return cid
    nova = api.post_conversa()
    if nova:
        st.session_state["conversa_id"] = nova["id"]
        return nova["id"]
    return None


def render():
    st.title("🤖 Assistente — Carteira Clean")

    if not HAS_ANTHROPIC:
        st.error("Pacote `anthropic` não instalado. Execute `pip install anthropic`.")
        return

    st.markdown("""
    <style>
    /* Alinhar texto dos botões de conversa à esquerda */
    div[data-testid="column"] button[kind="secondary"] {
        text-align: left !important;
        justify-content: flex-start !important;
        font-size: 0.82rem !important;
        padding: 4px 8px !important;
    }
    /* Botão ativo: destaque sutil */
    div[data-testid="column"] button[kind="primary"] {
        text-align: left !important;
        justify-content: flex-start !important;
        font-size: 0.82rem !important;
        padding: 4px 8px !important;
    }
    /* Botões de ícone (✏ 🗑): compactos */
    div[class*="conv-icon"] button { padding: 2px 4px !important; }
    </style>
    """, unsafe_allow_html=True)

    col_threads, col_chat = st.columns([1, 3])

    # ── COLUNA ESQUERDA: threads + memórias ──────────────────────
    with col_threads:
        st.markdown("**Conversas**")
        if st.button("＋ Nova conversa", use_container_width=True, key="nova_conv_btn"):
            nova = api.post_conversa()
            if nova:
                st.session_state["conversa_id"] = nova["id"]
                st.rerun()

        conversas = api.get_conversas()
        cid_atual = st.session_state.get("conversa_id")

        for conv in conversas[:30]:
            cid = conv["id"]
            ativo = cid == cid_atual
            renaming = st.session_state.get(f"_renaming_{cid}", False)
            del_confirm = st.session_state.get(f"_del_confirm_{cid}", False)

            if renaming:
                # ── Modo edição de título ─────────────────────
                novo_nome = st.text_input(
                    "", value=conv["titulo"], key=f"_rename_input_{cid}",
                    label_visibility="collapsed", max_chars=60,
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✓ Salvar", key=f"_rename_ok_{cid}",
                                 use_container_width=True, type="primary"):
                        if novo_nome and novo_nome.strip():
                            api.patch_conversa_titulo(cid, novo_nome.strip())
                            st.session_state.pop(f"_titulo_visto_{cid}", None)
                        st.session_state[f"_renaming_{cid}"] = False
                        st.rerun()
                with c2:
                    if st.button("✗ Cancelar", key=f"_rename_cancel_{cid}",
                                 use_container_width=True):
                        st.session_state[f"_renaming_{cid}"] = False
                        st.rerun()

            elif del_confirm:
                # ── Modo confirmação de exclusão ──────────────
                st.markdown(
                    f'<p style="color:#F59E0B;font-size:0.78rem;margin:4px 0">'
                    f'🗑 Excluir <b>"{conv["titulo"][:20]}"</b>?</p>',
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Sim", key=f"_del_ok_{cid}",
                                 use_container_width=True, type="primary"):
                        api.delete_conversa(cid)
                        st.session_state.pop(f"_del_confirm_{cid}", None)
                        if cid == cid_atual:
                            st.session_state.pop("conversa_id", None)
                        st.rerun()
                with c2:
                    if st.button("Não", key=f"_del_no_{cid}",
                                 use_container_width=True):
                        st.session_state[f"_del_confirm_{cid}"] = False
                        st.rerun()

            else:
                # ── Modo normal: título + ícones ──────────────
                c1, c2, c3 = st.columns([7, 1, 1])
                with c1:
                    label = f"{'▶' if ativo else '·'} {conv['titulo'][:22]}"
                    btn_type = "primary" if ativo else "secondary"
                    if st.button(label, key=f"conv_{cid}",
                                 use_container_width=True, type=btn_type):
                        st.session_state["conversa_id"] = cid
                        st.rerun()
                with c2:
                    if st.button("✏", key=f"_rename_btn_{cid}",
                                 use_container_width=True, help="Renomear"):
                        st.session_state[f"_renaming_{cid}"] = True
                        st.rerun()
                with c3:
                    if st.button("🗑", key=f"_del_btn_{cid}",
                                 use_container_width=True, help="Excluir"):
                        st.session_state[f"_del_confirm_{cid}"] = True
                        st.rerun()

        st.divider()

        memorias = api.get_memorias()
        with st.expander(f"🧠 Memórias ({len(memorias)})", expanded=False):
            if not memorias:
                st.caption("_Nenhuma memória ainda — vão aparecer aqui depois de algumas conversas._")
            for m in memorias:
                c1, c2 = st.columns([6, 1])
                with c1:
                    st.caption(f"**[{m['tipo']}]** {m['conteudo']}")
                with c2:
                    if st.button("×", key=f"del_mem_{m['id']}", help="Remover"):
                        api.delete_memoria(m["id"])
                        st.rerun()

    # ── COLUNA DIREITA: chat ──────────────────────────────────────
    with col_chat:
        conversa_id = _garantir_conversa()
        if not conversa_id:
            st.error("❌ Não foi possível criar/recuperar a conversa.")
            return

        conv_atual = api.get_conversa(conversa_id) or {"titulo": "Nova conversa"}
        titulo_db = conv_atual.get("titulo", "Nova conversa")
        # Sincroniza session_state com o DB para que rerun mostre o título atual
        # (auto-título e outras alterações fora do text_input).
        titulo_key = f"titulo_{conversa_id}"
        last_seen_key = f"_titulo_visto_{conversa_id}"
        if st.session_state.get(last_seen_key) != titulo_db:
            st.session_state[titulo_key] = titulo_db
            st.session_state[last_seen_key] = titulo_db

        novo_titulo = st.text_input(
            "Título da conversa",
            value=titulo_db,
            key=titulo_key,
            label_visibility="collapsed",
        )
        if novo_titulo and novo_titulo != titulo_db:
            api.patch_conversa_titulo(conversa_id, novo_titulo)
            st.session_state[last_seen_key] = novo_titulo

        mensagens = api.get_mensagens(conversa_id)
        for msg in mensagens:
            with st.chat_message(msg["role"]):
                tcs = msg.get("tool_calls")
                if tcs:
                    try:
                        nomes = json.loads(tcs)
                        if isinstance(nomes, list):
                            for n in nomes:
                                st.caption(f"🔧 Consultou: `{n}`")
                    except Exception:
                        pass
                st.markdown(msg["content"])

        # ── Rastreamento de sessão (reseta ao trocar de conversa) ────
        _sess_key = f"_sess_{conversa_id}"
        if st.session_state.get("_sess_conv_id") != conversa_id:
            st.session_state["_sess_conv_id"] = conversa_id
            st.session_state[_sess_key] = {"tok_in": 0, "tok_out": 0, "msgs": 0}
        _sess = st.session_state[_sess_key]

        # ── Sidebar de custo ──────────────────────────────────────
        with st.sidebar:
            st.subheader("🤖 Assistente")
            st.caption(f"Modelo: `{MODEL}`")

            # Sessão atual (desde que esta aba foi aberta ou conversa trocada)
            sess_in  = _sess["tok_in"]
            sess_out = _sess["tok_out"]
            sess_tot = sess_in + sess_out
            custo_sess_usd = sess_in * _CUSTO_IN + sess_out * _CUSTO_OUT
            custo_sess_brl = custo_sess_usd * _USD_BRL
            st.caption(f"**Sessão atual**")
            st.caption(f"Mensagens: {_sess['msgs']}")
            st.caption(f"Tokens: {sess_tot:,} (in {sess_in:,} / out {sess_out:,})")
            st.caption(f"Custo sessão: R$ {custo_sess_brl:.4f}")

            st.divider()

            # Acumulado de toda a conversa (gravado no DB)
            tot_t = conv_atual.get("total_tokens", 0)
            custo_usd = conv_atual.get("custo_usd", 0.0)
            custo_brl = custo_usd * _USD_BRL
            st.caption(f"**Conversa total**")
            st.caption(f"Tokens: {tot_t:,}")
            st.caption(f"Custo total: R$ {custo_brl:.4f}")

        # ── Input do usuário ──────────────────────────────────────
        prompt = st.chat_input("Pergunte sobre sua carteira...")
        if not prompt:
            return

        # Mostrar imediatamente
        with st.chat_message("user"):
            st.markdown(prompt)

        # Persistir mensagem do usuário
        api.post_mensagem(conversa_id, role="user", content=prompt)

        # Auto-título se for a 1ª mensagem
        # (não mexer em session_state[titulo_key] aqui — widget já foi instanciado
        # acima neste run; o bloco de sincronização no topo do próximo rerun pega.)
        if len(mensagens) == 0:
            api.patch_conversa_titulo(conversa_id, _gerar_titulo(prompt))

        # Construir histórico com janela deslizante (máx 20 msgs frescas)
        _JANELA = 20
        resumo_hist = conv_atual.get("resumo_historico")
        if resumo_hist:
            historico = [
                {"role": "user",
                 "content": f"[RESUMO DAS MENSAGENS ANTERIORES]\n{resumo_hist}"},
                {"role": "assistant",
                 "content": "Entendido. Continuando a conversa."},
            ] + [{"role": m["role"], "content": m["content"]} for m in mensagens[-_JANELA:]]
        else:
            historico = [{"role": m["role"], "content": m["content"]} for m in mensagens[-_JANELA:]]
        historico.append({"role": "user", "content": prompt})

        client = _get_client()
        if not client:
            st.error("❌ ANTHROPIC_API_KEY não configurada no .env.")
            return

        system = build_system_prompt()
        with st.chat_message("assistant"):
            status = st.empty()
            status.caption("🔄 Consultando...")
            try:
                texto, tools_usadas, usage = _enviar_mensagem(client, historico, system)
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

        # Persistir resposta + custo
        tokens_in = getattr(usage, "input_tokens", 0) if usage else 0
        tokens_out = getattr(usage, "output_tokens", 0) if usage else 0
        custo_msg = tokens_in * _CUSTO_IN + tokens_out * _CUSTO_OUT
        api.post_mensagem(
            conversa_id, role="assistant", content=texto,
            tool_calls=json.dumps(tools_usadas) if tools_usadas else None,
            tokens_in=tokens_in, tokens_out=tokens_out, custo_usd=custo_msg,
        )

        # Acumular na sessão atual
        _sess["tok_in"]  += tokens_in
        _sess["tok_out"] += tokens_out
        _sess["msgs"]    += 1

        # Extração de memórias em background
        _extrair_em_background(conversa_id)

        # Sumarização em background quando histórico fica longo (>20 msgs livres)
        if len(mensagens) >= 20:
            _sumarizar_em_background(conversa_id)

        st.rerun()
