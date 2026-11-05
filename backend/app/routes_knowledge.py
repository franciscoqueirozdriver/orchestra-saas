from csv import reader as csv_reader
from io import BytesIO, StringIO
from pathlib import PurePath

from docx import Document as DocxDocument
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from openpyxl import load_workbook
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_tenant_id
from app.embedding_client import embed_texts
from app.embedding_config import knowledge_embedding_config, connection_embedding_config
from app.llm_client import LLMError
from app.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSearchConfig, LLMConfig, User
from app.control import serialized_mutation
from app.security import encrypt_secret
from app.schemas import KnowledgeSearchUpsert

router = APIRouter(prefix="/api/knowledge/documents", tags=["conhecimento"])


def _require_admin(user: User) -> None:
    if user.role not in {"platform_admin", "tenant_admin"}:
        raise HTTPException(status_code=403, detail="Ação restrita a administradores")


def _extract(filename: str, content: bytes) -> tuple[str, str]:
    ext = PurePath(filename).suffix.lower()
    if ext in {".txt", ".md", ".csv"}:
        text = content.decode("utf-8-sig", errors="replace")
        if ext == ".csv":
            rows = csv_reader(StringIO(text))
            text = "\n".join(" | ".join(cell for cell in row) for row in rows)
        return text, "text/plain"
    if ext == ".pdf":
        reader = PdfReader(BytesIO(content), strict=False)
        if len(reader.pages) > 200:
            raise HTTPException(status_code=413, detail="PDF limitado a 200 páginas nesta versão")
        return "\n".join(page.extract_text() or "" for page in reader.pages), "application/pdf"
    if ext == ".docx":
        document = DocxDocument(BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if ext == ".xlsx":
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        lines = []
        for sheet in workbook.worksheets:
            lines.append(f"Planilha: {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                values = [str(value) for value in row if value is not None]
                if values:
                    lines.append(" | ".join(values))
        workbook.close()
        return "\n".join(lines), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    raise HTTPException(status_code=415, detail="Formato não suportado. Use TXT, Markdown, CSV, PDF, DOCX ou XLSX")


def _chunks(text: str, size: int = 3000, overlap: int = 250) -> list[str]:
    normalized = "\n".join(line.strip() for line in text.replace("\x00", "").splitlines() if line.strip())
    if len(normalized) > 600_000:
        raise HTTPException(status_code=413, detail="Documento excede 600 mil caracteres extraídos")
    chunks = []
    start = 0
    while start < len(normalized):
        end = min(start + size, len(normalized))
        part = normalized[start:end].strip()
        if part:
            chunks.append(part)
        if end >= len(normalized):
            break
        start = end - overlap
    if len(chunks) > 128:
        raise HTTPException(status_code=413, detail="Documento gera mais de 128 trechos; divida o arquivo")
    return chunks


@router.get("")
def list_documents(db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    rows = db.query(KnowledgeDocument).filter(KnowledgeDocument.tenant_id == tenant_id).order_by(KnowledgeDocument.created_at.desc()).all()
    return [{"id": x.id, "filename": x.filename, "mime_type": x.mime_type, "status": x.status, "created_at": x.created_at.isoformat()} for x in rows]


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    user: User = Depends(get_current_user),
) -> dict:
    _require_admin(user)
    filename = PurePath(file.filename or "documento").name[:240]
    maximum = settings.upload_max_mb * 1024 * 1024
    content = await file.read(maximum + 1)
    await file.close()
    if len(content) > maximum:
        raise HTTPException(status_code=413, detail=f"Arquivo excede o limite de {settings.upload_max_mb} MB")
    try:
        text, mime_type = _extract(filename, content)
        chunks = _chunks(text)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Não foi possível ler o documento") from exc
    if not chunks:
        raise HTTPException(status_code=422, detail="Documento sem texto extraível")
    doc = KnowledgeDocument(tenant_id=tenant_id, filename=filename, mime_type=mime_type,
                            status="pending_index", extracted_text=text.replace("\x00", ""))
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "filename": doc.filename, "mime_type": doc.mime_type,
            "status": doc.status, "chunk_count": 0, "created_at": doc.created_at.isoformat()}


@router.get("/search-settings")
def get_search_settings(db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    row=db.get(KnowledgeSearchConfig,tenant_id)
    result={"configured":False,"source":"none","connection_id":row.connection_id if row else None,
            "base_url":row.embedding_base_url if row else "","model":row.embedding_model if row else "","dimensions":1536}
    try:
        base,model,_=knowledge_embedding_config(db,tenant_id)
        result.update(configured=True,source=('connection' if row.connection_id else 'dedicated') if row else 'legacy',base_url=base,model=model)
    except LLMError as exc:
        result['configuration_error']=str(exc)
    return result


@router.put("/search-settings")
@serialized_mutation
def save_search_settings(payload: KnowledgeSearchUpsert, db: Session = Depends(get_db),
                         tenant_id: str = Depends(get_tenant_id), user: User = Depends(get_current_user)):
    _require_admin(user)
    row=db.get(KnowledgeSearchConfig,tenant_id)
    selected=None
    requested_base=payload.base_url
    if payload.connection_id:
        selected=db.query(LLMConfig).filter_by(id=payload.connection_id,tenant_id=tenant_id).first()
        if selected is None:raise HTTPException(422,'Conexão não encontrada nesta empresa')
        if payload.api_key or payload.base_url:raise HTTPException(422,'Ao selecionar conexão, não envie URL ou chave manual')
        try:requested_base,_=connection_embedding_config(selected)
        except LLMError as exc:raise HTTPException(422,str(exc)) from exc
    elif not requested_base:raise HTTPException(422,'Informe uma conexão cadastrada ou a URL da busca')
    try:
        base,model,_=knowledge_embedding_config(db,tenant_id)
    except LLMError:
        # Preserve the indexed namespace even when credentials are unavailable.
        base,model=(row.embedding_base_url,row.embedding_model) if row else (None,None)
    if (base,model)!=(requested_base,payload.model) and db.query(KnowledgeDocument).filter_by(tenant_id=tenant_id,status='indexed').first():
        raise HTTPException(409,'Há documentos indexados: alterar a busca exige reindexação planejada')
    if selected is None and not payload.api_key and (row is None or row.connection_id or row.embedding_base_url!=requested_base):
        raise HTTPException(422,'Informe a chave da busca ao configurar ou alterar o endpoint')
    if row is None:
        row=KnowledgeSearchConfig(tenant_id=tenant_id);db.add(row)
    row.embedding_base_url=requested_base;row.embedding_model=payload.model
    row.connection_id=selected.id if selected else None
    if selected:row.embedding_api_key_encrypted=''
    elif payload.api_key:row.embedding_api_key_encrypted=encrypt_secret(payload.api_key)
    db.commit()
    return get_search_settings(db,tenant_id)


@router.post("/{document_id}/index")
@serialized_mutation
def index_document(document_id: str, db: Session = Depends(get_db),
                   tenant_id: str = Depends(get_tenant_id), user: User = Depends(get_current_user)):
    _require_admin(user)
    doc=db.query(KnowledgeDocument).filter_by(id=document_id,tenant_id=tenant_id).first()
    if doc is None:raise HTTPException(404,'Documento não encontrado')
    if doc.status=='indexed':return {"id":doc.id,"status":doc.status}
    if not doc.extracted_text:raise HTTPException(409,'Reenvie o documento: texto original indisponível nesta versão antiga')
    chunks=_chunks(doc.extracted_text)
    try:
        base,model,key=knowledge_embedding_config(db,tenant_id)
        vectors=embed_texts(base,model,key,chunks)
    except LLMError as exc:
        raise HTTPException(409 if exc.category=='configuration' else 502,str(exc)) from exc
    db.query(KnowledgeChunk).filter_by(tenant_id=tenant_id,document_id=doc.id).delete(synchronize_session=False)
    db.add_all([KnowledgeChunk(tenant_id=tenant_id,document_id=doc.id,content=chunk,embedding=vector,embedding_model=model)
                for chunk,vector in zip(chunks,vectors,strict=True)])
    doc.status='indexed';db.commit()
    return {"id":doc.id,"status":doc.status,"chunk_count":len(chunks)}


@router.delete("/{document_id}", status_code=204)
@serialized_mutation
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    user: User = Depends(get_current_user),
) -> None:
    _require_admin(user)
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id, KnowledgeDocument.tenant_id == tenant_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id, KnowledgeChunk.tenant_id == tenant_id).delete(synchronize_session=False)
    db.delete(doc)
    db.commit()
