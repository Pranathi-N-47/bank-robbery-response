from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageType(str, Enum):
    INCIDENT_ALERT = "INCIDENT_ALERT"
    ROBBER_SIGHTING = "ROBBER_SIGHTING"
    INTERCEPT_PLAN = "INTERCEPT_PLAN"
    ASSIGNMENT = "ASSIGNMENT"
    RECALL = "RECALL"
    ROUTE_PLANNED = "ROUTE_PLANNED"
    POSITION_UPDATE = "POSITION_UPDATE"
    ARRIVED = "ARRIVED"
    ROBBER_STATE = "ROBBER_STATE"
    INCIDENT_CLOSED = "INCIDENT_CLOSED"


@dataclass
class Message:
    id: int
    tick: int
    sender: str
    recipient: str | None  # specific id or 'role:dispatch' or None (for topics)
    topic: str
    type: MessageType
    payload: dict[str, Any]
    priority: int = 0


class MessageBus:
    """Publish-Subscribe and direct message broker for multi-agent communication."""

    def __init__(self):
        self._counter: int = 0
        self._inboxes: dict[str, list[Message]] = {}
        self._role_members: dict[str, set[str]] = {}
        self._topic_subscribers: dict[str, set[str]] = {}
        self.event_log: list[Message] = []

    def register_agent(self, agent_id: str, role: str) -> None:
        """Register agent with specific ID and role."""
        if agent_id not in self._inboxes:
            self._inboxes[agent_id] = []
        if role not in self._role_members:
            self._role_members[role] = set()
        self._role_members[role].add(agent_id)

    def subscribe(self, agent_id: str, topic: str) -> None:
        """Subscribe agent to a broadcast topic."""
        if topic not in self._topic_subscribers:
            self._topic_subscribers[topic] = set()
        self._topic_subscribers[topic].add(agent_id)

    def send(
        self,
        tick: int,
        sender: str,
        recipient: str | None,
        topic: str,
        type: MessageType,
        payload: dict[str, Any],
        priority: int = 0,
    ) -> Message:
        """Route message to recipient, role, or subscribed topic listeners."""
        self._counter += 1
        msg = Message(
            id=self._counter,
            tick=tick,
            sender=sender,
            recipient=recipient,
            topic=topic,
            type=type,
            payload=payload,
            priority=priority,
        )
        self.event_log.append(msg)

        # 1. Direct recipient
        if recipient:
            if recipient.startswith("role:"):
                role_name = recipient.split(":", 1)[1]
                for member_id in self._role_members.get(role_name, set()):
                    if member_id in self._inboxes:
                        self._inboxes[member_id].append(msg)
            elif recipient in self._inboxes:
                self._inboxes[recipient].append(msg)

        # 2. Topic subscribers
        if topic and topic in self._topic_subscribers:
            for sub_id in self._topic_subscribers[topic]:
                if sub_id != sender and sub_id in self._inboxes:
                    # Avoid duplicate if already received via direct recipient
                    if not (recipient == sub_id):
                        self._inboxes[sub_id].append(msg)

        return msg

    def retrieve_inbox(self, agent_id: str) -> list[Message]:
        """Fetch all queued messages for agent and clear inbox."""
        if agent_id not in self._inboxes:
            return []
        msgs = self._inboxes[agent_id]
        self._inboxes[agent_id] = []
        return msgs

    def get_recent_events(self, limit: int = 50) -> list[dict]:
        """Serialize recent message events for live UI logging."""
        return [
            {
                "id": m.id,
                "tick": m.tick,
                "sender": m.sender,
                "recipient": m.recipient,
                "topic": m.topic,
                "type": m.type.value,
                "payload": m.payload,
            }
            for m in self.event_log[-limit:]
        ]
