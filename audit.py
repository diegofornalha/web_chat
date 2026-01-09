"""
Sistema de audit trail para web_chat.
Rastreia passos executados durante cada request.
"""
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import json


@dataclass
class AuditStep:
    """Representa um passo executado."""
    step: str
    status: str  # 'running', 'success', 'error'
    started_at: float
    ended_at: Optional[float] = None
    duration_ms: Optional[int] = None
    details: Optional[Dict] = None
    error: Optional[str] = None


class AuditTrail:
    """Gerencia audit trail de uma requisição."""

    _trails: Dict[str, List[AuditStep]] = {}

    @classmethod
    def start_step(cls, session_id: str, step: str, details: Optional[Dict] = None) -> AuditStep:
        """Inicia um novo passo."""
        audit_step = AuditStep(
            step=step,
            status='running',
            started_at=datetime.now().timestamp(),
            details=details
        )

        if session_id not in cls._trails:
            cls._trails[session_id] = []

        cls._trails[session_id].append(audit_step)
        return audit_step

    @classmethod
    def end_step(cls, session_id: str, step: str, status: str = 'success', error: Optional[str] = None):
        """Finaliza um passo."""
        if session_id not in cls._trails:
            return

        for audit_step in reversed(cls._trails[session_id]):
            if audit_step.step == step and audit_step.status == 'running':
                audit_step.ended_at = datetime.now().timestamp()
                audit_step.duration_ms = int((audit_step.ended_at - audit_step.started_at) * 1000)
                audit_step.status = status
                audit_step.error = error
                break

    @classmethod
    def get_trail(cls, session_id: str) -> List[Dict]:
        """Retorna trail de uma sessão."""
        if session_id not in cls._trails:
            return []

        return [asdict(step) for step in cls._trails[session_id]]

    @classmethod
    def get_stats(cls, session_id: str) -> Dict:
        """Retorna estatísticas do audit."""
        trail = cls._trails.get(session_id, [])

        if not trail:
            return {
                'total_steps': 0,
                'errors': 0,
                'total_duration_ms': 0,
                'avg_duration_ms': 0
            }

        completed = [s for s in trail if s.ended_at]
        errors = [s for s in trail if s.status == 'error']
        total_duration = sum(s.duration_ms or 0 for s in completed)

        return {
            'total_steps': len(trail),
            'completed': len(completed),
            'errors': len(errors),
            'total_duration_ms': total_duration,
            'avg_duration_ms': total_duration // len(completed) if completed else 0
        }
