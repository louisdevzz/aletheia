"""
Session Management - Manage conversation sessions

Handles session lifecycle, persistence, and metadata.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import uuid
import json

from aletheia.providers.base import ChatMessage


@dataclass
class Session:
    """A conversation session."""

    id: str
    created_at: datetime
    updated_at: datetime
    messages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, metadata: Optional[Dict] = None) -> "Session":
        """Create a new session."""
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

    def add_message(self, role: str, content: str, **kwargs):
        """Add a message to the session."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }
        self.messages.append(message)
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": self.messages,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create session from dictionary."""
        return cls(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            messages=data.get("messages", []),
            metadata=data.get("metadata", {}),
        )


class SessionManager:
    """Manages conversation sessions."""

    def __init__(self, storage_path: Optional[str] = None):
        self.sessions: Dict[str, Session] = {}
        self.storage_path = storage_path

    def create_session(self, metadata: Optional[Dict] = None) -> Session:
        """Create and store a new session."""
        session = Session.create(metadata)
        self.sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions (metadata only)."""
        return [
            {
                "id": s.id,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "message_count": len(s.messages),
                "metadata": s.metadata,
            }
            for s in self.sessions.values()
        ]

    def save_to_file(self, path: Optional[str] = None):
        """Save all sessions to file."""
        path = path or self.storage_path
        if not path:
            return

        data = {sid: s.to_dict() for sid, s in self.sessions.items()}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_file(self, path: Optional[str] = None):
        """Load sessions from file."""
        path = path or self.storage_path
        if not path:
            return

        try:
            with open(path, "r") as f:
                data = json.load(f)

            self.sessions = {
                sid: Session.from_dict(sdata) for sid, sdata in data.items()
            }
        except FileNotFoundError:
            pass


class SessionStore:
    """Persistent storage for sessions."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def save_session(self, session: Session):
        """Save session to storage."""
        # In real impl, would use SQLite
        pass

    def load_session(self, session_id: str) -> Optional[Session]:
        """Load session from storage."""
        return None

    def list_sessions(self) -> List[str]:
        """List all session IDs."""
        return []
