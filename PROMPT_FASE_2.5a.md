# 🎯 Prompt para Claude Code — Fase 2.5a

**Objetivo:** Implementar importação automática de extratos via Claude API.
**Escopo:** Tier 1 — PDF + JPEG/PNG + XLSX + CSV.
**Esforço estimado:** 2-3 semanas

---

## Como usar este prompt

1. Antes de iniciar, certifique-se de que:
   - A Fase 2.4 está commitada (último commit f17031c ou superior)
   - O arquivo `.env` contém `ANTHROPIC_API_KEY=...`
   - 32/32 testes de regressão passando

2. Copie o bloco abaixo e cole no Claude Code.

3. Reporte ao concluir cada item antes de seguir para o próximo.

---

## PROMPT PARA O CLAUDE CODE

```
Implemente a Fase 2.5a — Importação automática de extratos
via Claude API.

ESCOPO:
- Formatos suportados: PDF (nativo e escaneado), JPEG, PNG,
  XLSX, CSV
- Documentos: B3 (custódia + movimentações), Caixa RV,
  FUNCEF, Caixa LCI, Caixa OURO, Caixa FIC FUNC,
  Tesouro Direto

ARQUITETURA:
- Backend: novo módulo backend/engine/importacao/
- Endpoints: novo router api/importacao.py
- Frontend: nova página "📥 Importar Extrato"
- Schema: nova tabela importacoes
- Storage: arquivos originais em ~/Carteira/extratos/

═══════════════════════════════════════════════════════════
ITEM 1 — Schema de banco para histórico de importações
═══════════════════════════════════════════════════════════

Criar migration alembic com nova tabela `importacoes`:

  id (PK, auto)
  data_upload (DATETIME, default now)
  arquivo_nome (TEXT) — nome original do arquivo
  arquivo_path (TEXT) — path arquivado em ~/Carteira/extratos/
  arquivo_hash (TEXT) — sha256 do conteúdo
  formato (TEXT) — pdf | jpeg | png | xlsx | csv
  tipo_documento (TEXT) — b3_custodia | b3_movimentacoes |
                          caixa_rv | funcef | caixa_lci |
                          caixa_ouro | caixa_fic_func |
                          tesouro_direto | desconhecido
  status (TEXT) — UPLOADED | PROCESSING | PREVIEW |
                   CONFIRMED | CANCELLED | ERROR
  total_eventos_extraidos (INT, default 0)
  total_eventos_gravados (INT, default 0)
  total_eventos_duplicados (INT, default 0)
  eventos_extraidos_json (TEXT) — JSON com os eventos
                                    extraídos pela IA
  erro_mensagem (TEXT, nullable)
  custo_api_usd (FLOAT, default 0)
  data_confirmacao (DATETIME, nullable)

Tabela auxiliar `importacao_evento` (associação importacao
↔ evento gravado):
  importacao_id (FK)
  evento_id (FK)

Endpoints já a expor:
- GET /api/v1/importacoes — listar histórico
- GET /api/v1/importacoes/{id} — detalhes
- DELETE /api/v1/importacoes/{id} — cancelar importação
  (só se status != CONFIRMED)

═══════════════════════════════════════════════════════════
ITEM 2 — Configuração Claude API
═══════════════════════════════════════════════════════════

1. Adicione dependência: anthropic>=0.39.0

2. Crie módulo backend/engine/importacao/claude_client.py:

   - Lê ANTHROPIC_API_KEY do .env (use python-dotenv)
   - Função get_claude_client() retorna anthropic.Anthropic()
   - Função call_claude_with_pdf(pdf_bytes, prompt) que:
     a) Codifica PDF em base64
     b) Chama API com modelo claude-sonnet-4-20250514
     c) Suporta PDF até 32MB / 100 páginas
     d) Retorna response.content[0].text
     e) Captura usage tokens para registro de custo

   - Função call_claude_with_image(image_bytes, mime, prompt):
     similar, mas com type "image"

   - Função call_claude_with_text(texto, prompt):
     para XLSX/CSV já convertidos

3. Tratamento de erros:
   - Sem API key: erro claro "Configure ANTHROPIC_API_KEY
     no arquivo .env"
   - Falha de rede: retry 3x com backoff exponencial
   - PDF > 32MB ou > 100 páginas: erro tratado
   - Crédito insuficiente na API: mensagem clara para user
   - Timeout: 60 segundos por chamada

4. Logging: backend/logs/importacao.log com cada chamada
   (sem o conteúdo, apenas metadados: timestamp, tipo,
   tokens, custo, sucesso/erro)

═══════════════════════════════════════════════════════════
ITEM 3 — Pré-processadores por formato
═══════════════════════════════════════════════════════════

Crie backend/engine/importacao/processadores/:

processadores/pdf.py:
  - extrair_texto_pdf(bytes) → str (tentativa nativa)
  - validar_pdf(bytes) → (ok: bool, motivo: str)
  - Se PDF tem texto extraível: envia como texto
  - Se PDF é imagem (scan): envia direto à Claude (vision)
  - Detecta automaticamente qual estratégia usar

processadores/imagem.py:
  - validar_imagem(bytes) → (ok, motivo)
  - Limita resolução máxima (~5000x5000)
  - Envia direto à Claude (vision)

processadores/xlsx.py:
  - Usa openpyxl/pandas
  - Lê todas as planilhas
  - Converte para texto formatado (CSV-like) para enviar
    à Claude
  - Preserva nomes de colunas

processadores/csv.py:
  - Detecta delimitador automaticamente (,; tab)
  - Detecta encoding (utf-8, utf-8-sig, latin-1)
  - Lê e envia como texto à Claude

Detector de formato:
  detectar_formato(arquivo_bytes, nome_arquivo) → str
  - Por extensão E magic bytes (não só extensão)
  - Retorna: pdf | jpeg | png | xlsx | csv | desconhecido

═══════════════════════════════════════════════════════════
ITEM 4 — Prompts específicos por tipo de extrato
═══════════════════════════════════════════════════════════

Crie diretório backend/engine/importacao/prompts/ com um
arquivo Python para cada tipo. Cada arquivo exporta uma
constante PROMPT (string) e função PARSE_RESPONSE.

Estrutura comum dos prompts:

  Você está analisando um {tipo_documento}.
  Extraia todas as movimentações/operações em formato JSON.

  Schema do JSON de saída:
  {
    "documento": {
      "tipo": "...",
      "periodo_inicio": "YYYY-MM-DD",
      "periodo_fim": "YYYY-MM-DD",
      "titular": "..." (opcional)
    },
    "eventos": [
      {
        "data": "YYYY-MM-DD",
        "ativo": "TICKER ou NOME_PADRONIZADO",
        "tipo": "COMPRA|VENDA|DIVIDENDO|JCP|RENDIMENTO|...",
        "qtd": 0.0,
        "preco": 0.0,
        "valor": 0.0,
        "obs": "..."
      }
    ]
  }

  REGRAS:
  - Retorne APENAS JSON válido, sem markdown ou texto adicional
  - Datas no formato ISO (YYYY-MM-DD)
  - Valores em reais com ponto como separador decimal
  - Não invente dados — se ambíguo, omita o evento

Arquivos a criar com prompts específicos:

1. prompts/b3_custodia.py
   - Extrai posições em uma data (não eventos)
   - Útil para reconciliação
   - Tipo de retorno: posições + saldos

2. prompts/b3_movimentacoes.py
   - Extrai compras, vendas, proventos
   - Padroniza tickers (sem espaços)
   - Identifica COMPRA/VENDA/BONIFICACAO/DESDOBRAMENTO

3. prompts/caixa_rv.py
   - Similar ao B3 movimentações
   - Atenção a IRRF retido nas vendas
   - Caixa às vezes nomeia ativos diferente — normalizar

4. prompts/funcef.py
   - Identifica:
     * Saldo de cotas inicial e final
     * Valor da cota mensal (atualizar HISTORICO_PRECOS)
     * Contribuição do mês (CONTRIBUICAO)
     * Rendimentos (informativo)
   - Gera evento CONTRIBUICAO com qtd_cotas e valor R$

5. prompts/caixa_lci.py
   - Saldo bruto, rendimento do período
   - Gera evento RENDIMENTO com valor R$
   - Atualiza saldo total

6. prompts/caixa_ouro.py
   - Cota atual + saldo + variação
   - Atualiza HISTORICO_PRECOS com cota
   - Sem geração de eventos (variação é via cota)

7. prompts/caixa_fic_func.py
   - Movimentações: aplicações (COMPRA) e resgates (VENDA)
   - Cota mensal (HISTORICO_PRECOS)
   - Saldo inicial e final

8. prompts/tesouro_direto.py
   - Foco em Tesouro Renda+ 2065
   - Valor do título atual (HISTORICO_PRECOS)
   - Movimentações se houver

Cada arquivo PARSE_RESPONSE valida e normaliza o JSON
retornado pela IA, convertendo para eventos compatíveis
com nosso schema existente.

═══════════════════════════════════════════════════════════
ITEM 5 — Detector automático de tipo de documento
═══════════════════════════════════════════════════════════

backend/engine/importacao/detector.py:

Função detectar_tipo_documento(texto_amostra) → str
- Usa heurísticas simples (palavras-chave)
- Exemplos:
  * "B3 S.A. - Brasil, Bolsa, Balcão" → b3_*
  * "CAIXA ECONÔMICA FEDERAL" + "RENDA VARIÁVEL" → caixa_rv
  * "FUNCEF" → funcef
  * "Tesouro Direto" → tesouro_direto
  * "LCI" no título → caixa_lci

Se não identifica: retorna "desconhecido"
e usuário deve selecionar manualmente.

Para PDFs e imagens, primeiro extrair texto/OCR rápido,
depois aplicar detecção. Para XLSX/CSV, ler cabeçalhos.

═══════════════════════════════════════════════════════════
ITEM 6 — Endpoint REST de processamento
═══════════════════════════════════════════════════════════

Crie backend/api/importacao.py com endpoints:

POST /api/v1/importacao/upload
  Form data: arquivo (multipart), tipo_documento (opcional)
  Fluxo:
    1. Salva arquivo em ~/Carteira/extratos/{ano}/{mes}/
    2. Detecta formato (extensão + magic bytes)
    3. Calcula hash sha256
    4. Cria registro em `importacoes` com status=UPLOADED
    5. Detecta tipo de documento (se não informado)
    6. Pré-processa conforme formato
    7. Chama Claude API com prompt apropriado
    8. Parse da resposta JSON
    9. Salva eventos_extraidos_json + custo_api_usd
    10. Atualiza status=PREVIEW
    11. Retorna importacao_id + preview dos eventos

GET /api/v1/importacao/{id}/preview
  Retorna lista de eventos extraídos com:
    - Marcador de duplicata (se já existe no event log)
    - Validação de tickers (já cadastrado? se não, sinaliza)
    - Total a gravar

POST /api/v1/importacao/{id}/confirmar
  Body: lista de índices dos eventos a manter (user pode
        ter removido alguns no preview)
  Fluxo:
    1. Verifica status == PREVIEW
    2. Para cada evento aprovado:
       - Verifica ticker cadastrado (cria automaticamente
         se for ativo novo, com flag de revisão)
       - Cria evento no banco
       - Vincula importacao_id ↔ evento_id
    3. Marca duplicatas (não grava) — incrementa contador
    4. Status = CONFIRMED
    5. Aciona recálculo do engine (POST /calcular)
    6. Retorna resumo: X gravados, Y duplicados, Z erros

DELETE /api/v1/importacao/{id}
  Só funciona se status != CONFIRMED
  Apaga registro e arquivo original

═══════════════════════════════════════════════════════════
ITEM 7 — Página Streamlit "Importar Extrato"
═══════════════════════════════════════════════════════════

Crie frontend/paginas/importar.py:

SEÇÃO 1 — Upload
  st.file_uploader aceitando:
    type=["pdf", "jpg", "jpeg", "png", "xlsx", "xls", "csv"]
  Suporte a múltiplos arquivos.

  Dropdown opcional "Tipo de documento":
    [Auto-detectar]
    B3 - Custódia
    B3 - Movimentações
    Caixa - Renda Variável
    Caixa - FIC FUNC
    Caixa - LCI
    Caixa - OURO
    FUNCEF
    Tesouro Direto

  Botão "📤 Processar com IA"

SEÇÃO 2 — Processamento (durante upload)
  Spinner com status:
    "Detectando formato..."
    "Detectando tipo de documento..."
    "Enviando à IA (pode demorar 30-60s)..."
    "Processando resposta..."

  Em caso de erro: mensagem clara + sugestão

SEÇÃO 3 — Preview (após processamento)
  Cabeçalho:
    "Documento: {tipo} | {N} eventos extraídos
     | Custo: R$ X,XX"

  Tabela editável com colunas:
    [✓] | Data | Ativo | Tipo | Qtd | Preço | Valor | Status

  Status pode ser:
    ✅ Novo evento (será gravado)
    ⚠️ Duplicata (já existe — não grava)
    ❓ Ticker não cadastrado (será criado)
    ❌ Erro de validação

  User pode:
    - Desmarcar checkbox de qualquer evento
    - Editar valores (se IA errou algo)
    - Ver totais que serão gravados em tempo real

  Botões:
    ✅ Confirmar e gravar (X eventos)
    💾 Salvar como rascunho (mantém PREVIEW)
    ❌ Cancelar importação

SEÇÃO 4 — Pós-confirmação
  Mensagem de sucesso com:
    - X eventos gravados
    - Y duplicatas ignoradas
    - Link "Ver atualização no Dashboard"

SEÇÃO 5 — Histórico de importações
  Tabela na parte inferior da página:
    Data | Arquivo | Tipo | Status | Eventos | Custo

  Filtros: período, status, tipo
  Botão "🗑️ Cancelar" só aparece se status != CONFIRMED

═══════════════════════════════════════════════════════════
ITEM 8 — Detecção de duplicatas
═══════════════════════════════════════════════════════════

Para cada evento extraído, gerar hash:
  evento_hash = sha256(f"{data}-{ativo}-{tipo}-{qtd}-{valor}")

Comparar com eventos existentes no banco.
Se hash já existe: marcar como duplicata, NÃO gravar.

═══════════════════════════════════════════════════════════
ITEM 9 — Auditoria e segurança
═══════════════════════════════════════════════════════════

Arquivamento:
  Arquivo original sempre salvo em
  ~/Carteira/extratos/{ano}/{mes}/{hash[:8]}-{nome_original}
  Mesmo se importação for cancelada (auditoria)

Log estruturado:
  backend/logs/importacao.log contém:
    - timestamp
    - arquivo_hash
    - tipo_documento
    - status final
    - tokens usados / custo USD
    - sem dados sensíveis

Backup:
  O backup automático já existente (Fase 2.4 Item 1)
  cobre a tabela importacoes — sem ação necessária.

═══════════════════════════════════════════════════════════
ITEM 10 — Casos edge a tratar
═══════════════════════════════════════════════════════════

1. PDF criptografado:
   Mensagem: "Este PDF está protegido por senha. Remova
   a senha e tente novamente."

2. PDF corrompido ou sem texto:
   Tenta vision (OCR via Claude); se falhar, erro claro.

3. Tipo não detectado:
   Fluxo permite usuário selecionar manualmente.
   Não bloqueia.

4. Ticker não cadastrado:
   No preview, mostra alerta amarelo.
   Botão "Cadastrar ativo automaticamente" cria o registro
   em CAD_ATIVOS com valores padrão (composite=Gerida,
   família=Ação BR) — usuário pode editar depois.

5. IA retorna JSON malformado:
   Tentar 1 retry. Se falhar: erro mostra o que a IA
   retornou para diagnosticar.

6. Datas fora do esperado:
   (ex: extrato é de 2025 mas usuário esperava 2026)
   Sinalização visual + confirmação extra antes de gravar.

7. Múltiplos arquivos no upload:
   Processa um por um, mostra progresso.
   Se um falha, os outros continuam.

═══════════════════════════════════════════════════════════
ITEM 11 — Configuração do .env
═══════════════════════════════════════════════════════════

Criar arquivo .env.example na raiz com:
  ANTHROPIC_API_KEY=
  ANTHROPIC_MODEL=claude-sonnet-4-20250514
  IMPORTACAO_ARQUIVAR_PATH=~/Carteira/extratos
  IMPORTACAO_MAX_PDF_MB=32
  IMPORTACAO_MAX_PAGINAS=100

Adicionar .env ao .gitignore (CRÍTICO — nunca commitar).

Documentar no README como obter a API key.

═══════════════════════════════════════════════════════════
ITEM 12 — Validações finais
═══════════════════════════════════════════════════════════

Antes do commit final, validar:

1. 32/32 testes de regressão ainda passando

2. Fluxo manual de teste (com um PDF de extrato real):
   - Upload do PDF
   - Tipo detectado automaticamente
   - Preview mostra eventos extraídos
   - Algumas duplicatas detectadas (assumindo que PDF
     contém eventos já existentes)
   - Confirmar grava apenas os novos
   - Engine recalcula
   - Dashboard reflete os novos eventos

3. Validação de custo:
   - Importação registra custo_api_usd > 0
   - Histórico mostra custo acumulado

4. Validação de segurança:
   - Arquivo .env NÃO está no Git (verificar git status)
   - .env está no .gitignore
   - Arquivos originais arquivados corretamente

═══════════════════════════════════════════════════════════
ENCERRAMENTO
═══════════════════════════════════════════════════════════

1. git commit -am "fase 2.5a: importação automática de
   extratos via Claude API — PDF, JPEG/PNG, XLSX, CSV"

2. Reporte:
   - Total de arquivos criados / modificados
   - 32/32 regressões passando
   - Custo estimado de 1 importação típica (B3) em R$
   - Print da página "Importar Extrato"
   - Print do preview após processar um extrato
   - Eventuais limitações descobertas durante a
     implementação

3. Sugestão de teste real:
   Recomende ao usuário fazer um primeiro teste com
   um PDF que ele já conhece (que tem eventos já no
   banco), para validar que a detecção de duplicatas
   funciona e que os eventos novos batem com o esperado.
```

---

## Após o Claude Code concluir

1. **Configure a API key**:
   - Crie/edite o arquivo `.env` na raiz de `~/carteira-web/`
   - Adicione: `ANTHROPIC_API_KEY=sk-ant-api03-...sua-chave`
   - Salve e reinicie o backend

2. **Teste com um PDF que você já conhece**:
   - Pegue um extrato B3 antigo (ex: janeiro 2026)
   - Faça upload via página "Importar Extrato"
   - Compare os eventos extraídos pela IA com os eventos
     já no banco
   - **Espere que 100% sejam marcados como DUPLICATAS** —
     se não forem, a IA está extraindo errado e precisamos
     ajustar o prompt

3. **Teste com um PDF novo** (ex: extrato de maio que ainda
   não foi processado):
   - Upload
   - Verifique preview
   - Confirme
   - Veja eventos chegando no banco

4. **Monitore custos**:
   - Acompanhe em https://console.anthropic.com/usage
   - Esperado: R$ 0,10-0,50 por extrato B3
