"""
Gerenciamento de sessões de chat em memória.
Compatível com o Angular SDK que espera endpoints de sessão.
"""
from typing import Dict, Optional, List
from datetime import datetime
import uuid

from .models import Session, ChatMessage, SessionInfo


class SessionManager:
    """Gerencia sessões de chat em memória."""

    _sessions: Dict[str, Session] = {}
    _current_session_id: Optional[str] = None

    @classmethod
    def create_session(cls, model: str = "haiku") -> Session:
        """Cria uma nova sessão."""
        session = Session(
            session_id=str(uuid.uuid4()),
            model=model,
            updated_at=datetime.now().timestamp()
        )
        cls._sessions[session.session_id] = session
        cls._current_session_id = session.session_id
        return session

    @classmethod
    def get_session(cls, session_id: str) -> Optional[Session]:
        """Busca sessão por ID."""
        return cls._sessions.get(session_id)

    @classmethod
    def get_or_create_session(cls, session_id: Optional[str] = None, model: str = "haiku") -> Session:
        """Busca sessão existente ou cria uma nova."""
        if session_id and session_id in cls._sessions:
            return cls._sessions[session_id]
        return cls.create_session(model)

    @classmethod
    def get_current_session(cls) -> Optional[Session]:
        """Retorna a sessão atual."""
        if cls._current_session_id:
            return cls._sessions.get(cls._current_session_id)
        return None

    @classmethod
    def set_current_session(cls, session_id: str) -> bool:
        """Define a sessão atual."""
        if session_id in cls._sessions:
            cls._current_session_id = session_id
            return True
        return False

    @classmethod
    def list_sessions(cls) -> List[SessionInfo]:
        """Lista todas as sessões ordenadas por data de atualização."""
        sessions = sorted(
            cls._sessions.values(),
            key=lambda s: s.updated_at,
            reverse=True
        )
        return [
            SessionInfo(
                session_id=s.session_id,
                title=s.title,
                favorite=s.favorite,
                updated_at=s.updated_at,
                message_count=len(s.messages),
                model=s.model
            )
            for s in sessions
        ]

    @classmethod
    def add_message(cls, session_id: str, role: str, content: str) -> Optional[ChatMessage]:
        """Adiciona mensagem à sessão."""
        session = cls._sessions.get(session_id)
        if not session:
            return None

        message = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.now().timestamp()
        )
        session.messages.append(message)
        session.message_count = len(session.messages)
        session.updated_at = datetime.now().timestamp()

        # Auto-gerar título na primeira mensagem do usuário
        if not session.title and role == "user":
            session.title = content[:50] + ("..." if len(content) > 50 else "")

        return message

    @classmethod
    def get_messages(cls, session_id: str) -> List[ChatMessage]:
        """Retorna mensagens de uma sessão."""
        session = cls._sessions.get(session_id)
        return session.messages if session else []

    @classmethod
    def update_session(
        cls,
        session_id: str,
        title: Optional[str] = None,
        favorite: Optional[bool] = None,
        project_id: Optional[str] = None
    ) -> Optional[Session]:
        """Atualiza propriedades da sessão."""
        session = cls._sessions.get(session_id)
        if not session:
            return None

        if title is not None:
            session.title = title
        if favorite is not None:
            session.favorite = favorite
        if project_id is not None:
            session.project_id = project_id

        session.updated_at = datetime.now().timestamp()
        return session

    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        """Deleta uma sessão."""
        if session_id in cls._sessions:
            del cls._sessions[session_id]
            if cls._current_session_id == session_id:
                cls._current_session_id = None
            return True
        return False

    @classmethod
    def reset(cls, model: str = "haiku") -> Session:
        """Cria nova sessão e define como atual."""
        return cls.create_session(model)
