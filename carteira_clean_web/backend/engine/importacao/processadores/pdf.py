"""
Pré-processamento de PDFs: extração de texto nativo ou envio via visão.
"""

import logging

log = logging.getLogger("engine.importacao.pdf")


def extrair_texto_pdf(pdf_bytes: bytes) -> str:
    """Extrai texto nativo do PDF via pypdf. Retorna string vazia se falhar."""
    try:
        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        if reader.is_encrypted:
            log.warning("PDF criptografado — não é possível extrair texto")
            return ""
        paginas = []
        for i, page in enumerate(reader.pages):
            if i >= 100:
                break
            try:
                t = page.extract_text() or ""
                paginas.append(t)
            except Exception:
                paginas.append("")
        return "\n".join(paginas)
    except Exception as e:
        log.warning(f"Falha ao extrair texto do PDF: {e}")
        return ""


def tem_texto_util(texto: str, min_chars: int = 200) -> bool:
    """Retorna True se o texto extraído parece conteúdo real (não PDF escaneado)."""
    sem_espacos = texto.replace(" ", "").replace("\n", "")
    return len(sem_espacos) >= min_chars


def validar_pdf(pdf_bytes: bytes) -> tuple[bool, str]:
    """Valida PDF. Retorna (ok, mensagem_erro)."""
    if len(pdf_bytes) > 32 * 1024 * 1024:
        return False, "PDF excede limite de 32 MB"
    try:
        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        if reader.is_encrypted:
            return False, "PDF está criptografado/protegido por senha"
        n_pages = len(reader.pages)
        if n_pages == 0:
            return False, "PDF sem páginas"
        if n_pages > 100:
            log.warning(f"PDF com {n_pages} páginas — processando apenas as primeiras 100")
        return True, ""
    except Exception as e:
        return False, f"PDF corrompido ou inválido: {e}"
