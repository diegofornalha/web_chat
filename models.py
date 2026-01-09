from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid

class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Mensagem do usuário para o modelo"
    )

class ChatResponse(BaseModel):
    response: str = Field(..., description="Resposta do modelo")
    sandbox_id: str = Field(..., description="ID do sandbox E2B usado")
    model: str = Field(default="minimax/minimax-m2", description="Modelo utilizado")

class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Status do serviço")
    model: str = Field(..., description="Modelo configurado")

# Modelos para SSE Streaming (compatíveis com Angular SDK)
class StreamChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default="haiku")

class ChatMessage(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    timestamp: Optional[float] = Field(default_factory=lambda: datetime.now().timestamp())

class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: Optional[str] = None
    favorite: bool = False
    project_id: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    model: str = "haiku"
    message_count: int = 0

class SessionInfo(BaseModel):
    session_id: str
    title: Optional[str] = None
    favorite: bool = False
    updated_at: float
    message_count: int
    model: str

class SessionUpdateRequest(BaseModel):
    title: Optional[str] = None
    favorite: Optional[bool] = None
    project_id: Optional[str] = None
