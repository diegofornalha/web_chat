from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path
from typing import List
import json
import asyncio
import os

from .models import (
    ChatRequest, ChatResponse, HealthResponse,
    StreamChatRequest, SessionInfo, SessionUpdateRequest, ChatMessage
)
from .sessions import SessionManager
from .audit import AuditTrail
from claude_mini_sdk.sandbox_manager import SandboxManager
from claude_mini_sdk.config import MINIMAX_CONFIG

router = APIRouter()
CURRENT_DIR = Path(__file__).parent


# ===== UTILITÁRIOS =====

def extract_and_save_artifacts(response_text: str) -> tuple[str, int]:
    """
    Extrai blocos de código da resposta e salva como artefatos.
    Retorna: (resposta_modificada, quantidade_de_artefatos)
    """
    import re
    from datetime import datetime

    # Regex para detectar code blocks markdown: ```lang\ncode\n``` ou ```\ncode\n```
    pattern = r'```(\w+)?\s*(.*?)```'
    matches = re.findall(pattern, response_text, re.DOTALL)

    # Se não encontrou code blocks, verificar se é HTML direto
    if not matches and ('<!doctype' in response_text.lower() or '<html' in response_text.lower()):
        # Extrair HTML direto da resposta
        html_match = re.search(r'<!doctype.*?</html>', response_text, re.DOTALL | re.IGNORECASE)
        if html_match:
            matches = [('html', html_match.group(0))]

    if not matches:
        return response_text, 0

    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)

    count = 0
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filenames = []

    for i, (lang, code) in enumerate(matches):
        # Determinar extensão baseado na linguagem
        ext_map = {
            'html': '.html',
            'htm': '.html',
            'css': '.css',
            'javascript': '.js',
            'js': '.js',
            'python': '.py',
            'py': '.py',
            'json': '.json',
            'xml': '.xml',
            'sql': '.sql',
            'bash': '.sh',
            'shell': '.sh',
            'typescript': '.ts',
            'tsx': '.tsx',
            'jsx': '.jsx',
        }

        # Se não tem linguagem especificada, tentar detectar pelo conteúdo
        if not lang:
            code_lower = code[:200].lower()
            if '<!doctype' in code_lower or '<html' in code_lower:
                ext = '.html'
            elif code_lower.strip().startswith('{') or code_lower.strip().startswith('['):
                ext = '.json'
            elif 'def ' in code or 'import ' in code or 'class ' in code:
                ext = '.py'
            else:
                ext = '.txt'
        else:
            ext = ext_map.get(lang.lower(), '.txt')

        filename = f"artifact_{timestamp}_{i+1}{ext}"

        # Salvar arquivo
        file_path = artifacts_dir / filename
        file_path.write_text(code.strip())
        print(f"📄 Artefato extraído e salvo: {filename}")
        filenames.append(filename)
        count += 1

    # Modificar resposta: remover blocos de código e adicionar mensagem
    if count > 0:
        # Remover todos os code blocks
        modified_response = re.sub(pattern, '', response_text, flags=re.DOTALL)
        # Limpar linhas vazias extras
        modified_response = re.sub(r'\n{3,}', '\n\n', modified_response).strip()

        # Adicionar mensagem sobre artefatos
        artifact_msg = f"\n\n✅ **{count} artefato(s) criado(s)!** "
        artifact_msg += f"[Clique aqui para visualizar](/artifacts)"

        modified_response = modified_response + artifact_msg

        return modified_response, count

    return response_text, 0


# ===== ENDPOINTS EXISTENTES (HTML/Legacy) =====

@router.get("/")
async def home():
    html_path = CURRENT_DIR / "static" / "index.html"
    if not html_path.exists():
        raise HTTPException(
            status_code=404,
            detail="index.html não encontrado"
        )
    return FileResponse(html_path)


@router.get("/recents")
async def recents_page():
    """Página de conversas recentes."""
    html_path = CURRENT_DIR / "static" / "recents.html"
    if not html_path.exists():
        raise HTTPException(
            status_code=404,
            detail="recents.html não encontrado"
        )
    return FileResponse(html_path)


@router.get("/config")
async def config_page():
    """Página de configurações RAG."""
    html_path = CURRENT_DIR / "static" / "config.html"
    if not html_path.exists():
        raise HTTPException(
            status_code=404,
            detail="config.html não encontrado"
        )
    return FileResponse(html_path)


@router.get("/ingest")
async def ingest_page():
    """Página de upload de documentos."""
    html_path = CURRENT_DIR / "static" / "ingest.html"
    if not html_path.exists():
        raise HTTPException(
            status_code=404,
            detail="ingest.html não encontrado"
        )
    return FileResponse(html_path)


@router.get("/audit")
async def audit_page():
    """Página de audit de sessão."""
    html_path = CURRENT_DIR / "static" / "audit.html"
    if not html_path.exists():
        raise HTTPException(
            status_code=404,
            detail="audit.html não encontrado"
        )
    return FileResponse(html_path)


@router.get("/documents")
async def documents_page():
    """Página de documentos RAG."""
    html_path = CURRENT_DIR / "static" / "documents.html"
    if not html_path.exists():
        raise HTTPException(
            status_code=404,
            detail="documents.html não encontrado"
        )
    return FileResponse(html_path)


@router.get("/tools")
async def tools_page():
    """Página de ferramentas disponíveis."""
    html_path = CURRENT_DIR / "static" / "tools.html"
    if not html_path.exists():
        raise HTTPException(
            status_code=404,
            detail="tools.html não encontrado"
        )
    return FileResponse(html_path)


@router.get("/document-detail")
async def document_detail_page():
    """Página de detalhes de um documento."""
    html_path = CURRENT_DIR / "static" / "document-detail.html"
    if not html_path.exists():
        raise HTTPException(
            status_code=404,
            detail="document-detail.html não encontrado"
        )
    return FileResponse(html_path)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        with SandboxManager.create_sandbox() as sandbox:
            print(f"✅ Sandbox criado: {sandbox.sandbox_id}")

            if not SandboxManager.setup_sandbox(sandbox):
                raise HTTPException(
                    status_code=500,
                    detail="Falha ao configurar sandbox E2B"
                )

            response_text = SandboxManager.send_message(sandbox, req.message)

            return ChatResponse(
                response=response_text,
                sandbox_id=sandbox.sandbox_id,
                model=MINIMAX_CONFIG["model"]
            )

    except HTTPException:
        raise

    except Exception as e:
        print(f"❌ Erro no endpoint /chat: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar mensagem: {str(e)}"
        )


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        model=MINIMAX_CONFIG["model"]
    )


# ===== ENDPOINTS SSE STREAMING (Angular SDK) =====

async def generate_sse_response(message: str, session_id: str, use_rag: bool = False):
    """Gera resposta SSE no formato esperado pelo Angular."""
    # Enviar session_id imediatamente no início (antes de qualquer processamento)
    yield f"data: {json.dumps({'type': 'session_init', 'session_id': session_id})}\n\n"

    try:
        # Rastrear: Criar sandbox
        AuditTrail.start_step(session_id, "create_sandbox")

        with SandboxManager.create_sandbox() as sandbox:
            AuditTrail.end_step(session_id, "create_sandbox", "success")
            print(f"✅ Sandbox SSE criado: {sandbox.sandbox_id}")

            # Rastrear: Setup sandbox
            AuditTrail.start_step(session_id, "setup_sandbox")
            if not SandboxManager.setup_sandbox(sandbox):
                AuditTrail.end_step(session_id, "setup_sandbox", "error", "Falha ao configurar")
                yield f"data: {json.dumps({'error': 'Falha ao configurar sandbox'})}\n\n"
                return
            AuditTrail.end_step(session_id, "setup_sandbox", "success")

            # Adicionar mensagem do usuário à sessão
            SessionManager.add_message(session_id, "user", message)

            # Se RAG está ativo, buscar contexto primeiro
            query_message = message
            rag_docs_count = 0

            if use_rag:
                try:
                    # Rastrear: Busca RAG
                    AuditTrail.start_step(session_id, "rag_search", {"query": message[:50]})

                    import httpx
                    async with httpx.AsyncClient() as client:
                        rag_response = await client.get(
                            f'http://localhost:8001/v1/rag/search/test?query={message}&top_k=3'
                        )
                        if rag_response.status_code == 200:
                            rag_data = rag_response.json()
                            results = rag_data.get('results', [])
                            rag_docs_count = len(results)

                            if results:
                                # Montar contexto com documentos
                                context = "\n\n".join([
                                    f"[Fonte: {r['source']}]\n{r['content'][:1000]}"
                                    for r in results
                                ])

                                query_message = f"""<base_conhecimento>
{context}
</base_conhecimento>

IMPORTANTE: Responda APENAS com base nos documentos acima da <base_conhecimento>.
Se a informação não estiver nos documentos, diga: "Não encontrei essa informação na base de conhecimento."
NÃO use conhecimento geral ou informações externas.

Pergunta: {message}"""
                                print(f"📚 RAG: {len(results)} documentos encontrados")
                                AuditTrail.end_step(session_id, "rag_search", "success")
                            else:
                                AuditTrail.end_step(session_id, "rag_search", "success", "Nenhum documento encontrado")
                except Exception as e:
                    print(f"⚠️ Erro ao buscar RAG: {e}")
                    AuditTrail.end_step(session_id, "rag_search", "error", str(e))

            # Rastrear: Chamar Minimax
            AuditTrail.start_step(session_id, "minimax_api", {"rag_used": use_rag, "docs_found": rag_docs_count})
            response_text = SandboxManager.send_message(sandbox, query_message)
            AuditTrail.end_step(session_id, "minimax_api", "success")

            # Rastrear: Extrair artefatos
            if response_text:
                AuditTrail.start_step(session_id, "extract_artifacts")
                modified_response, artifacts_count = extract_and_save_artifacts(response_text)

                # Atualizar details do step com contagem de artefatos
                if session_id in AuditTrail._trails:
                    for step in reversed(AuditTrail._trails[session_id]):
                        if step.step == "extract_artifacts" and step.status == "running":
                            step.details = {"artifacts_created": artifacts_count}
                            break

                AuditTrail.end_step(session_id, "extract_artifacts", "success")
            else:
                modified_response = ""
                artifacts_count = 0

            # Usar resposta modificada para streaming (sem código se foi extraído)
            words = modified_response.split()
            accumulated = ""

            for i, word in enumerate(words):
                accumulated += word + (" " if i < len(words) - 1 else "")

                chunk_data = {
                    "text": word + " ",
                    "session_id": session_id
                }

                # Enviar refresh_sessions na primeira chunk (nova sessão)
                if i == 0:
                    chunk_data["refresh_sessions"] = True

                yield f"data: {json.dumps(chunk_data)}\n\n"
                await asyncio.sleep(0.02)  # Pequeno delay para simular streaming

            # Adicionar resposta modificada à sessão
            SessionManager.add_message(session_id, "assistant", modified_response)

            if artifacts_count > 0:
                # Notificar sobre artefatos
                yield f"data: {json.dumps({'artifacts': artifacts_count})}\n\n"

            # Sinal de fim
            yield "data: [DONE]\n\n"

    except Exception as e:
        print(f"❌ Erro SSE: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@router.post("/chat/stream")
async def chat_stream(req: StreamChatRequest):
    """Endpoint de chat com SSE streaming para Angular SDK."""
    # DEBUG: Log da requisição
    print(f"🔍 DEBUG /chat/stream - req.session_id: {req.session_id}")
    print(f"🔍 DEBUG - Sessions disponíveis: {list(SessionManager._sessions.keys())}")

    # Buscar ou criar sessão
    session = SessionManager.get_or_create_session(req.session_id, req.model or "minimax")
    print(f"🔍 DEBUG - Sessão retornada: {session.session_id} (nova? {session.session_id != req.session_id})")

    return StreamingResponse(
        generate_sse_response(req.message, session.session_id, req.use_rag or False),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ===== ENDPOINTS DE SESSÕES (Angular SDK) =====

@router.get("/sessions", response_model=List[SessionInfo])
async def list_sessions():
    """Lista todas as sessões."""
    return SessionManager.list_sessions()


@router.get("/session/current")
async def get_current_session():
    """Retorna sessão atual."""
    session = SessionManager.get_current_session()
    if not session:
        # Criar nova sessão se não existir
        session = SessionManager.create_session()

    return SessionInfo(
        session_id=session.session_id,
        title=session.title,
        favorite=session.favorite,
        updated_at=session.updated_at,
        message_count=len(session.messages),
        model=session.model
    )


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Retorna mensagens de uma sessão no formato esperado pelo Angular."""
    session = SessionManager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    # Angular espera { messages: [...] }
    return {"messages": [msg.model_dump() for msg in session.messages]}


@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, req: SessionUpdateRequest):
    """Atualiza propriedades da sessão."""
    session = SessionManager.update_session(
        session_id,
        title=req.title,
        favorite=req.favorite,
        project_id=req.project_id
    )
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    return SessionInfo(
        session_id=session.session_id,
        title=session.title,
        favorite=session.favorite,
        updated_at=session.updated_at,
        message_count=len(session.messages),
        model=session.model
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Deleta uma sessão."""
    if not SessionManager.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return {"status": "deleted", "session_id": session_id}


@router.post("/reset")
async def reset_session():
    """Cria nova sessão."""
    session = SessionManager.reset()
    return SessionInfo(
        session_id=session.session_id,
        title=session.title,
        favorite=session.favorite,
        updated_at=session.updated_at,
        message_count=0,
        model=session.model
    )


# ===== ENDPOINTS DE ARTEFATOS =====

@router.get("/artifacts")
async def artifacts_page_or_list():
    """Retorna página HTML ou lista JSON de artefatos."""
    from fastapi import Request
    from starlette.requests import Request as StarletteRequest

    # Se é requisição do browser (Accept: text/html), retornar página
    # Se é requisição AJAX/fetch (Accept: application/json), retornar JSON
    html_path = CURRENT_DIR / "static" / "artifacts.html"
    if html_path.exists():
        return FileResponse(html_path)

    # Fallback para JSON
    artifacts_dir = Path("artifacts")
    if not artifacts_dir.exists():
        return {"files": []}

    files = []
    for file_path in artifacts_dir.iterdir():
        if file_path.is_file():
            stat = file_path.stat()
            files.append({
                "name": file_path.name,
                "size": stat.st_size,
                "created": stat.st_mtime
            })

    return {"files": sorted(files, key=lambda x: x["created"], reverse=True)}


@router.get("/api/artifacts")
async def list_artifacts_api():
    """Endpoint API para listar artefatos (JSON)."""
    artifacts_dir = Path("artifacts")
    if not artifacts_dir.exists():
        return {"files": []}

    files = []
    for file_path in artifacts_dir.iterdir():
        if file_path.is_file():
            stat = file_path.stat()
            files.append({
                "name": file_path.name,
                "size": stat.st_size,
                "created": stat.st_mtime
            })

    return {"files": sorted(files, key=lambda x: x["created"], reverse=True)}


@router.get("/artifacts/{filename}")
async def get_artifact(filename: str):
    """Retorna conteúdo de um artefato."""
    artifacts_dir = Path("artifacts")
    file_path = artifacts_dir / filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Artefato não encontrado")

    # Retornar como HTML para visualização
    content = file_path.read_text()
    ext = file_path.suffix.lower()

    # Se for HTML, retornar direto
    if ext in [".html", ".htm"]:
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=content)

    # Outros tipos, retornar como texto
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=content)


@router.delete("/artifacts/{filename}")
async def delete_artifact(filename: str):
    """Deleta um artefato."""
    artifacts_dir = Path("artifacts")
    file_path = artifacts_dir / filename

    # Validação de segurança - apenas filenames, não paths
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Artefato não encontrado")

    try:
        file_path.unlink()
        print(f"🗑️ Artefato deletado: {filename}")
        return {"status": "deleted", "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao deletar: {str(e)}")


# ===== ENDPOINTS DE AUDIT =====

@router.get("/api/audit/trail/{session_id}")
async def get_audit_trail(session_id: str):
    """Retorna audit trail de uma sessão (passos executados)."""
    trail = AuditTrail.get_trail(session_id)
    stats = AuditTrail.get_stats(session_id)

    return {
        "session_id": session_id,
        "trail": trail,
        "stats": stats
    }


# ===== ENDPOINTS DE UPLOAD =====

from fastapi import File, UploadFile
import subprocess
import tempfile

@router.post("/api/upload/pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload de PDF para ingestão no RAG."""
    try:
        # Salvar arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        print(f"📤 Upload recebido: {file.filename} ({len(content)} bytes)")

        # Copiar para diretório ingest do claude_rag_sdk
        ingest_dir = Path(__file__).parent.parent / "claude_rag_sdk" / "ingest"
        ingest_dir.mkdir(exist_ok=True)

        dest_path = ingest_dir / file.filename
        Path(tmp_path).rename(dest_path)

        print(f"📁 Salvo em: {dest_path}")

        # Executar script de ingest
        ingest_script = Path(__file__).parent.parent / "claude_rag_sdk" / "scripts" / "ingest.py"

        if not ingest_script.exists():
            raise HTTPException(status_code=500, detail="Script de ingest não encontrado")

        print(f"🔄 Executando ingest...")
        result = subprocess.run(
            ["python", str(ingest_script), str(dest_path)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ingest_script.parent.parent),
            env={**dict(os.environ), "PYTHONPATH": str(ingest_script.parent.parent.parent)}
        )

        # Limpar arquivo temporário se ainda existir
        if Path(tmp_path).exists():
            Path(tmp_path).unlink(missing_ok=True)

        if result.returncode == 0:
            print(f"✅ Ingest concluído: {file.filename}")
            print(f"Script output:\n{result.stdout}")

            # Tentar parsear chunks do output
            chunks = 0
            output_text = result.stdout + result.stderr

            # Procurar padrões: "X chunks", "Chunks: X", "chunks_stored: X"
            import re
            patterns = [
                r'(\d+)\s+chunks',
                r'chunks[:\s]+(\d+)',
                r'total[_\s]+chunks[:\s]+(\d+)'
            ]

            for pattern in patterns:
                match = re.search(pattern, output_text, re.IGNORECASE)
                if match:
                    chunks = int(match.group(1))
                    break

            return {
                "success": True,
                "filename": file.filename,
                "chunks": chunks,
                "message": "PDF ingerido com sucesso! Verifique em /documents",
                "output": result.stdout[:500]  # Truncar output
            }
        else:
            print(f"❌ Erro no ingest:\n{result.stderr}\n{result.stdout}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro no ingest: {result.stderr or result.stdout}"
            )

    except Exception as e:
        print(f"❌ Erro no upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))
