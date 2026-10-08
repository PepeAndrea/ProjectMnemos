"""Pure trigger evaluation; notification execution remains behind policy."""

from datetime import datetime
from uuid import UUID

from .domain import Reminder


def ready(
    reminder: Reminder,
    at: datetime,
    visible: set[UUID],
    place: str | None = None,
    topic: str | None = None,
) -> bool:
    if at.tzinfo is None:
        raise ValueError("clock requires timezone")
    if reminder.state not in {"pending", "snoozed"}:
        return False
    if reminder.snooze_until is not None and at < reminder.snooze_until:
        return False
    trigger = reminder.trigger
    return all(
        [
            trigger.due_at is None or at >= trigger.due_at,
            trigger.entity_visible is None or trigger.entity_visible in visible,
            trigger.place is None or trigger.place == place,
            trigger.topic is None or trigger.topic == topic,
        ]
    )
