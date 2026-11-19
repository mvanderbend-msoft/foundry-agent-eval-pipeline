"""Tool definitions. They are versioned in Git and released with the prompt and the code."""

from typing import Annotated

_ORDERS = {
    "CP-1001": {"status": "out for delivery", "eta_minutes": 12, "store": "Amsterdam"},
    "CP-1002": {"status": "delivered", "eta_minutes": 0, "store": "Utrecht"},
    "CP-1003": {"status": "in the oven", "eta_minutes": 25, "store": "Amsterdam"},
    "CP-1004": {"status": "delayed", "eta_minutes": 45, "store": "Rotterdam"},
}

_STORES = {
    "amsterdam": "Mon-Sun 11:00-23:00",
    "utrecht": "Mon-Sat 12:00-22:00, closed on Sunday",
    "rotterdam": "Mon-Sun 11:00-22:00",
}


def get_order_status(
    order_id: Annotated[str, "The order number, for example CP-1001."],
) -> str:
    """Look up the status and expected delivery time of a Contoso Pizza order."""
    order = _ORDERS.get(order_id.strip().upper())
    if order is None:
        return f"No order found with number {order_id}."
    return (
        f"Order {order_id.upper()} from the {order['store']} store is {order['status']}. "
        f"Expected in {order['eta_minutes']} minutes."
    )


def get_store_hours(
    city: Annotated[str, "City of the Contoso Pizza store, for example Amsterdam."],
) -> str:
    """Return the opening hours of the Contoso Pizza store in a city."""
    hours = _STORES.get(city.strip().lower())
    if hours is None:
        return f"There is no Contoso Pizza store in {city}. Stores: Amsterdam, Utrecht, Rotterdam."
    return f"The {city.title()} store is open {hours}."


TOOLS = [get_order_status, get_store_hours]
