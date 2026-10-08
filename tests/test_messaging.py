import pytest
from brrs.core.messaging import MessageBus, MessageType

def test_message_bus_direct_routing():
    bus = MessageBus()
    bus.register_agent("patrol_1", "patrol")
    bus.register_agent("dispatch", "dispatch")

    # Send direct message
    bus.send(
        tick=1,
        sender="dispatch",
        recipient="patrol_1",
        topic="orders",
        type=MessageType.ASSIGNMENT,
        payload={"dest": 10},
    )

    inbox = bus.retrieve_inbox("patrol_1")
    assert len(inbox) == 1
    assert inbox[0].type == MessageType.ASSIGNMENT
    assert inbox[0].payload["dest"] == 10

    # Ensure inbox is cleared upon fetch
    assert len(bus.retrieve_inbox("patrol_1")) == 0

def test_message_bus_role_routing():
    bus = MessageBus()
    bus.register_agent("cmd_1", "command")
    bus.register_agent("surv_1", "surveillance")

    bus.send(
        tick=2,
        sender="surv_1",
        recipient="role:command",
        topic="alerts",
        type=MessageType.INCIDENT_ALERT,
        payload={"location": 5},
    )

    inbox = bus.retrieve_inbox("cmd_1")
    assert len(inbox) == 1
    assert inbox[0].type == MessageType.INCIDENT_ALERT

def test_message_bus_topic_broadcast():
    bus = MessageBus()
    bus.register_agent("p1", "patrol")
    bus.register_agent("p2", "patrol")
    bus.register_agent("cmd", "command")

    bus.subscribe("cmd", "unit.status")
    bus.subscribe("p2", "unit.status")

    bus.send(
        tick=3,
        sender="p1",
        recipient=None,
        topic="unit.status",
        type=MessageType.POSITION_UPDATE,
        payload={"node": 12},
    )

    assert len(bus.retrieve_inbox("cmd")) == 1
    assert len(bus.retrieve_inbox("p2")) == 1
    assert len(bus.retrieve_inbox("p1")) == 0  # Sender doesn't receive its own message
