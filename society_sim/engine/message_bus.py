# society_sim/engine/message_bus.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time
import itertools
import uuid

@dataclass
class Message:
    sender: str
    receivers: List[str]
    intent: str  # propose|request|inform|counter|accept|commit|threat|abort
    content: Dict[str, Any]
    valid_until_tick: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)

class MessageBus:
    """
    In-memory bus per run. Keep it simple: append-only log + filtered views.
    """
    def __init__(self) -> None:
        self._messages: List[Message] = []

    # --- write ---
    def post(self, msg: Message) -> str:
        self._messages.append(msg)
        return msg.id

    def post_many(self, msgs: List[Message]) -> List[str]:
        return [self.post(m) for m in msgs]

    # --- read ---
    def inbox(self, role: str, tick: int) -> List[Message]:
        return [
            m for m in self._messages
            if role in m.receivers and m.valid_until_tick >= tick
        ]

    def all_for_tick(self, tick: int) -> List[Message]:
        return [m for m in self._messages if m.valid_until_tick >= tick]

    # --- housekeeping ---
    def gc(self, tick: int) -> None:
        self._messages = [m for m in self._messages if m.valid_until_tick >= tick]

    # --- helpers ---
    def to_jsonable(self, msgs: List[Message]) -> List[Dict[str, Any]]:
        out = []
        for m in msgs:
            out.append({
                "id": m.id,
                "sender": m.sender,
                "receivers": list(m.receivers),
                "intent": m.intent,
                "content": m.content,
                "valid_until_tick": m.valid_until_tick,
                "created_at": m.created_at
            })
        return out
