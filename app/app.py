import reflex as rx

from app.components.public_pages import home_page, bouquets_page, portraits_page
from app.states.public_state import PublicState
from app.states.customer_state import CustomerState
from app.states.admin_state import AdminState
from app.components.admin_dashboard_new import new_admin_dashboard_page
from app.components.customer_pages import (
    login_page,
    dashboard_page,
)
from app.components.customer_checkout_new import new_customer_checkout_page
from app.states.private_files import migrate_private_files
from app.states.private_file_api import order_image


def index() -> rx.Component:
    return home_page()


migrate_private_files()

app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(
            rel="preconnect",
            href="https://fonts.gstatic.com",
            cross_origin="",
        ),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600&family=DM+Sans:wght@400;500;600&display=swap",
            rel="stylesheet",
        ),
    ],
)
app._api.add_route(
    "/order-files/{order_id}/{kind}", order_image, methods=["GET"]
)
app.add_page(
    index,
    route="/",
    title="The Studio · Portraits & Bouquets",
    on_load=[PublicState.load_public, CustomerState.restore],
)
app.add_page(
    bouquets_page,
    route="/bouquets",
    title="Bouquet Collection",
    on_load=[PublicState.load_public, CustomerState.restore],
)
app.add_page(
    portraits_page,
    route="/portraits",
    title="Personal Portraits · Sizes & Art Styles",
    on_load=[PublicState.load_public, CustomerState.restore],
)
app.add_page(
    login_page,
    route="/login",
    title="Your Studio Account",
    on_load=[PublicState.load_public, CustomerState.load_account_page],
)
app.add_page(
    new_customer_checkout_page,
    route="/checkout",
    title="Checkout · Your Order",
    on_load=[PublicState.load_public, CustomerState.load_account_page],
)
app.add_page(
    new_admin_dashboard_page,
    route="/admin",
    title="Studio Workspace",
    on_load=[
        PublicState.load_public,
        CustomerState.restore,
        AdminState.load_admin,
    ],
)
app.add_page(
    dashboard_page,
    route="/dashboard",
    title="My Orders · Studio Account",
    on_load=[PublicState.load_public, CustomerState.load_account_page],
)
