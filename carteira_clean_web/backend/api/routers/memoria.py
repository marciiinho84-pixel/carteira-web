"""
Router: conversas (threads), mensagens e memórias do assistente.

3 recursos:
  - /conversas       — threads do chat
  - /conversas/{id}/mensagens — histórico de cada thread
  - /memorias        — memórias de longo prazo (extraídas ou manuais)
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.db.models import Conversa, Mensagem, MemoriaAssistente

router = APIRouter(tags=["memoria"])


# ─── Schemas locais ───────────────────────────────────────────────

class TituloUpdate(BaseModel):
    titulo: str


class ResumoUpdate(BaseModel):
    resumo: str


class MensagemCreate(BaseModel):
    role: str
    content: str
    tool_calls: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    custo_usd: float = 0.0


class MemoriaCreate(BaseModel):
    tipo: str
    conteudo: str
    conversa_id: Optional[int] = None
    fonte: str = "manual"


_TIPOS_VALIDOS = {"estrategia", "preferencia", "decisao", "meta", "fato"}
_FONTES_VALIDAS = {"extraida", "manual"}
_ROLES_VALIDOS = {"user", "assistant", "tool", "system"}


# ─── Conversas ────────────────────────────────────────────────────

@router.get("/conversas")
def listar_conversas(db: Session = Depends(get_db)):
    convs = (
        db.query(Conversa)
        .filter(Conversa.ativa == 1)
        .order_by(Conversa.atualizada_em.desc())
        .all()
    )
    return [c.to_dict() for c in convs]


@router.post("/conversas", status_code=status.HTTP_201_CREATED)
def criar_conversa(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    c = Conversa(titulo="Nova conversa", criada_em=now, atualizada_em=now,
                 ativa=1, total_msgs=0, total_tokens=0, custo_usd=0.0)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c.to_dict()


@router.get("/conversas/{conversa_id}")
def obter_conversa(conversa_id: int, db: Session = Depends(get_db)):
    c = db.get(Conversa, conversa_id)
    if not c or not c.ativa:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    return c.to_dict()


@router.patch("/conversas/{conversa_id}/titulo")
def atualizar_titulo(conversa_id: int, body: TituloUpdate, db: Session = Depends(get_db)):
    c = db.get(Conversa, conversa_id)
    if not c or not c.ativa:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    titulo = (body.titulo or "").strip() or "Nova conversa"
    c.titulo = titulo[:100]
    c.atualizada_em = datetime.utcnow()
    db.commit()
    db.refresh(c)
    return c.to_dict()


@router.patch("/conversas/{conversa_id}/resumo")
def salvar_resumo(conversa_id: int, body: ResumoUpdate, db: Session = Depends(get_db)):
    c = db.get(Conversa, conversa_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    c.resumo_historico = (body.resumo or "").strip() or None
    c.atualizada_em = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.delete("/conversas/{conversa_id}")
def excluir_conversa(conversa_id: int, db: Session = Depends(get_db)):
    c = db.get(Conversa, conversa_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    c.ativa = 0
    db.commit()
    return {"ok": True}


# ─── Mensagens ────────────────────────────────────────────────────

@router.get("/conversas/{conversa_id}/mensagens")
def listar_mensagens(conversa_id: int, db: Session = Depends(get_db)):
    c = db.get(Conversa, conversa_id)
    if not c or not c.ativa:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    msgs = (
        db.query(Mensagem)
        .filter(Mensagem.conversa_id == conversa_id)
        .order_by(Mensagem.id.desc())
        .limit(30)
        .all()
    )
    msgs.reverse()  # mais antigas primeiro
    return [m.to_dict() for m in msgs]


@router.post("/conversas/{conversa_id}/mensagens", status_code=status.HTTP_201_CREATED)
def criar_mensagem(conversa_id: int, body: MensagemCreate, db: Session = Depends(get_db)):
    c = db.get(Conversa, conversa_id)
    if not c or not c.ativa:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    if body.role not in _ROLES_VALIDOS:
        raise HTTPException(status_code=422, detail=f"role inválido: {body.role}")

    m = Mensagem(
        conversa_id=conversa_id,
        role=body.role,
        content=body.content or "",
        tool_calls=body.tool_calls,
        tokens_in=body.tokens_in or 0,
        tokens_out=body.tokens_out or 0,
        custo_usd=body.custo_usd or 0.0,
        criada_em=datetime.utcnow(),
    )
    db.add(m)

    # Atualizar totais na conversa
    c.total_msgs = (c.total_msgs or 0) + 1
    c.total_tokens = (c.total_tokens or 0) + (body.tokens_in or 0) + (body.tokens_out or 0)
    c.custo_usd = (c.custo_usd or 0.0) + (body.custo_usd or 0.0)
    c.atualizada_em = datetime.utcnow()

    db.commit()
    db.refresh(m)
    return m.to_dict()


# ─── Memórias ─────────────────────────────────────────────────────

_PRIORIDADE_TIPO = {"decisao": 1, "estrategia": 2, "meta": 3, "preferencia": 4, "fato": 5}


@router.get("/memorias")
def listar_memorias(db: Session = Depends(get_db)):
    mems = (
        db.query(MemoriaAssistente)
        .filter(MemoriaAssistente.ativa == 1)
        .order_by(MemoriaAssistente.criada_em.desc())
        .all()
    )
    return [m.to_dict() for m in mems]


@router.get("/memorias/priorizadas")
def listar_memorias_priorizadas(limite: int = 12, db: Session = Depends(get_db)):
    """Retorna até `limite` memórias ativas, ordenadas por tipo (decisão > estratégia > ...) e data."""
    mems = (
        db.query(MemoriaAssistente)
        .filter(MemoriaAssistente.ativa == 1)
        .all()
    )
    mems.sort(key=lambda m: (
        _PRIORIDADE_TIPO.get(m.tipo, 5),
        -(m.criada_em.timestamp() if m.criada_em else 0),
    ))
    return [m.to_dict() for m in mems[:limite]]


@router.post("/memorias", status_code=status.HTTP_201_CREATED)
def criar_memoria(body: MemoriaCreate, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse
    if body.tipo not in _TIPOS_VALIDOS:
        raise HTTPException(status_code=422, detail=f"tipo inválido: {body.tipo}")
    if body.fonte not in _FONTES_VALIDAS:
        raise HTTPException(status_code=422, detail=f"fonte inválida: {body.fonte}")
    conteudo = (body.conteudo or "").strip()
    if not conteudo:
        raise HTTPException(status_code=422, detail="conteudo vazio")

    # Deduplicação: não salvar se os primeiros 80 chars já existem
    prefixo = conteudo[:80].lower()
    existentes = db.query(MemoriaAssistente).filter(MemoriaAssistente.ativa == 1).all()
    if any(e.conteudo[:80].lower() == prefixo for e in existentes):
        return JSONResponse(status_code=200, content={"deduplicado": True})

    # FIFO: manter no máximo 50 memórias ativas
    _MAX_MEMORIAS = 50
    total_ativas = len(existentes)
    if total_ativas >= _MAX_MEMORIAS:
        excesso = total_ativas - _MAX_MEMORIAS + 1  # quantas desativar para caber a nova
        mais_antigas = (
            db.query(MemoriaAssistente)
            .filter(MemoriaAssistente.ativa == 1)
            .order_by(MemoriaAssistente.criada_em.asc())
            .limit(excesso)
            .all()
        )
        for m_antiga in mais_antigas:
            m_antiga.ativa = 0

    m = MemoriaAssistente(
        tipo=body.tipo,
        conteudo=conteudo,
        conversa_id=body.conversa_id,
        fonte=body.fonte,
        criada_em=datetime.utcnow(),
        ativa=1,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m.to_dict()


@router.delete("/memorias/{memoria_id}")
def excluir_memoria(memoria_id: int, db: Session = Depends(get_db)):
    m = db.get(MemoriaAssistente, memoria_id)
    if not m:
        raise HTTPException(status_code=404, detail="Memória não encontrada")
    m.ativa = 0
    db.commit()
    return {"ok": True}
