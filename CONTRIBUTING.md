# Setup para novo desenvolvedor

## Pré-requisitos

- Python 3.10+
- Git

## Instalação

```bash
git clone https://github.com/marciiinho84-pixel/carteira-web.git
cd carteira-web
pip install -r requirements.txt
```

## Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz (nunca commitá-lo):

```
ANTHROPIC_API_KEY=sk-ant-...
BRAPI_TOKEN=...
MCP_TOKEN=...
DB_PATH=/caminho/para/carteira.db   # opcional; default: carteira_clean_web/carteira.db
```

## Banco de dados

O schema é criado/atualizado via Alembic. Em banco vazio (primeiro uso):

```bash
alembic upgrade head
```

Isso aplica as 3 migrations em sequência:

| Revision | O que faz |
|----------|-----------|
| `0001`   | Cria tabela `cotacoes` (preços históricos). Seed do pkl se disponível. |
| `0002`   | Adiciona coluna `bloco_ips` em `ativos` (pula se tabela ainda não existe — o app cria via `create_all`). |
| `0003`   | Cria tabela `benchmarks` (CDI, IBOV, etc.). Seed do pkl se disponível. |

As tabelas de negócio (`ativos`, `eventos`, etc.) são criadas automaticamente pelo ORM na
primeira inicialização do backend (`uvicorn` ou `docker compose up`).

Para reverter tudo:

```bash
alembic downgrade base
```

## Subir localmente

```bash
# Backend (FastAPI)
uvicorn carteira_clean_web.backend.api.main:app --reload --port 8000

# Frontend (Streamlit) — em outro terminal
streamlit run carteira_clean_web/frontend/main.py --server.port 8501
```

Ou via Docker Compose:

```bash
sudo docker compose up --build
```

## Rodar os testes

```bash
pytest tests/ -v
```

Testes que fazem chamadas reais de rede são pulados automaticamente em ambientes sem internet
(flag `no_api=True` no engine).
