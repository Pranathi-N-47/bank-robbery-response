from __future__ import annotations
from typing import Any
import mesa
from brrs.core.messaging import MessageBus, Message, MessageType


class CommAgent(mesa.Agent):
    """
    Base autonomous agent integrating with Mesa and the MessageBus.
    Provides standard Perceive-Decide-Act operational loop.
    """

    def __init__(self, model: mesa.Model, name: str, role: str):
        super().__init__(model)
        self.agent_name = name
        self.role = role
        self.inbox: list[Message] = []
        
        # Register with message bus
        self.bus: MessageBus = getattr(model, "bus", None)
        if self.bus:
            self.bus.register_agent(self.agent_name, self.role)

    def subscribe(self, topic: str) -> None:
        """Subscribe this agent to a message topic."""
        if self.bus:
            self.bus.subscribe(self.agent_name, topic)

    def send(
        self,
        recipient: str | None,
        topic: str,
        type: MessageType,
        payload: dict[str, Any],
        priority: int = 0,
    ) -> Message:
        """Send message through the model's message bus."""
        return self.bus.send(
            tick=self.model.steps,
            sender=self.agent_name,
            recipient=recipient,
            topic=topic,
            type=type,
            payload=payload,
            priority=priority,
        )

    def fetch_messages(self) -> list[Message]:
        """Fetch incoming messages and store in self.inbox."""
        if self.bus:
            self.inbox.extend(self.bus.retrieve_inbox(self.agent_name))
        msgs = list(self.inbox)
        self.inbox.clear()
        return msgs

    def perceive(self) -> None:
        """Step 1: Read sensors, scan environment, ingest messages."""
        pass

    def decide(self) -> None:
        """Step 2: Reason, plan, evaluate objectives."""
        pass

    def act(self) -> None:
        """Step 3: Execute movement, dispatch messages, update state."""
        pass

    def step(self) -> None:
        """Default Mesa step invoking the three-phase loop."""
        self.perceive()
        self.decide()
        self.act()

    def state_dict(self) -> dict[str, Any]:
        """Serialize state for UI agent inspection cards."""
        return {
            "name": self.agent_name,
            "role": self.role,
        }
