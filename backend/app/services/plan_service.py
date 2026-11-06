"""plan_service: 업무 규칙과 트랜잭션 처리."""

from datetime import timedelta
from app.shared.dates import parse_time


def condition_value(row, key):
    return next(
        (c.get("value") for c in row["conditions_json"] if c.get("key") == key), None
    )


def new_alternative(row, key, title, items, description):
    return dict(
        id=key,
        title=title,
        a_selected=False,
        b_selected=False,
        plan_json=dict(
            type="OTHER",
            description=description,
            items=items,
            schedule_changes=[],
            specification=condition_value(row, "specification"),
        ),
    )


def make_items(row, quantity, split=False):
    due = parse_time(row["due_at"])
    if split and isinstance(quantity, int) and (quantity > 1):
        quantities = [quantity - 1, 1]
    else:
        quantities = [quantity]
    items = []
    for i, q in enumerate(quantities):
        start = due.replace(hour=13 + i * 2, minute=0, second=0)
        end = start + timedelta(hours=2)
        items.append(
            dict(
                item_key=f"delivery_{i + 1}",
                assignee_id=row["assignee_id"],
                quantity=q,
                start_at=start.isoformat(),
                end_at=end.isoformat(),
                due_at=due.isoformat(),
            )
        )
    return items
