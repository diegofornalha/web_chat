from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path
from typing import List
import json
import asyncio

from .models import (
    ChatRequest, ChatResponse, HealthResponse,
    StreamChatRequest, SessionInfo, SessionUpdateRequest, ChatMessage
)
from .sessions import SessionManager
from claude_mini_sdk.sandbox_manager import SandboxManager
from claude_mini_sdk.config import MINIMAX_CONFIG

router = APIRouter()
CURRENT_DIR = Path(__file__).parent


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

async def generate_sse_response(message: str, session_id: str):
    """Gera resposta SSE no formato esperado pelo Angular."""
    try:
        with SandboxManager.create_sandbox() as sandbox:
            print(f"✅ Sandbox SSE criado: {sandbox.sandbox_id}")

            if not SandboxManager.setup_sandbox(sandbox):
                yield f"data: {json.dumps({'error': 'Falha ao configurar sandbox'})}\n\n"
                return

            # Adicionar mensagem do usuário à sessão
            SessionManager.add_message(session_id, "user", message)

            # Obter resposta do modelo
            response_text = SandboxManager.send_message(sandbox, message)

            # Simular streaming enviando em chunks
            words = response_text.split()
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

            # Adicionar resposta completa à sessão
            SessionManager.add_message(session_id, "assistant", response_text)

            # Sinal de fim
            yield "data: [DONE]\n\n"

    except Exception as e:
        print(f"❌ Erro SSE: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@router.post("/chat/stream")
async def chat_stream(req: StreamChatRequest):
    """Endpoint de chat com SSE streaming para Angular SDK."""
    # Buscar ou criar sessão
    session = SessionManager.get_or_create_session(req.session_id, req.model or "haiku")

    return StreamingResponse(
        generate_sse_response(req.message, session.session_id),
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
