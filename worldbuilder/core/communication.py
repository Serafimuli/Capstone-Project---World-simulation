# Messages, channels, protocols (Message, Inbox, Outbox)
from __future__ import annotations
from pydantic import BaseModel
from typing import Literal, Any

MessageType = Literal["PROPOSE","REQUEST","COUNTER","REPORT","ALERT","TREATY","TRADE"]

class Message(BaseModel):
    """
    Tool: Send a message between agents or states.
    Parameters:
        type (MessageType): Type of message (PROPOSE, REQUEST, COUNTER, REPORT, ALERT, TREATY, TRADE)
        sender (str): Agent or state sending the message
        receiver (str): Agent or state receiving the message
        topic (str): Subject of the message
        payload (Any): Data or content of the message
        credibility (float): Trust level of the message (default 0.5)
        cost (float): Cost to send the message (default 0.0)
        ts (int): Timestamp or tick (default 0)
    Returns:
        Message object
    """
    type: MessageType
    sender: str
    receiver: str
    topic: str
    payload: Any
    credibility: float = 0.5
    cost: float = 0.0
    ts: int = 0

def can_talk(sender: str, receiver: str) -> bool:
    """
    Tool: Check if two agents can communicate.
    Parameters:
        sender (str): Agent or state sending the message (e.g., 'S1', 'S1.C1', 'S1.C1.A1')
        receiver (str): Agent or state receiving the message
    Returns:
        bool: True if communication is allowed (intra-state or inter-state at State level), False otherwise
    """
    s_state = sender.split(".")[0]      # "S1"
    r_state = receiver.split(".")[0]
    s_is_state = sender.startswith("S") and sender.count(".") == 0
    r_is_state = receiver.startswith("S") and receiver.count(".") == 0

    # inter-stat doar la nivel State<->State
    if s_is_state and r_is_state:
        return True
    # intra-stat: orice altă combinație trebuie să fie în același stat
    return s_state == r_state
