import reflex as rx

from app.components.public_collection import collection
from app.components.customer_forms import bouquet_order_panel, feedback
from app.states.customer_state import CustomerState
from app.components.public_layout import action_link, public_layout
from app.states.public_state import PublicState
from app.states.store_models import PortraitSize, PortraitStyle


def home_hero() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.p(
                "PORTRAITS & BOUQUETS",
                class_name="text-xs font-medium tracking-[0.25em] text-[var(--studio-accent)] mb-7",
            ),
            rx.el.h1(
                rx.cond(
                    PublicState.settings["welcome_text"] != "",
                    PublicState.settings["welcome_text"],
                    "Art made personal. Flowers made to keep.",
                ),
                class_name="font-['Cormorant_Garamond'] text-5xl sm:text-6xl lg:text-7xl leading-[1.05] font-medium whitespace-pre-line break-words",
            ),
            rx.el.p(
                "For the people, moments and little things that matter. Explore the bouquet collection or begin a portrait made around your favourite photograph.",
                class_name="mt-7 text-base leading-7 text-[var(--studio-text)]/65 max-w-lg",
            ),
            rx.el.div(
                action_link("Explore bouquets", "/bouquets"),
                rx.el.a(
                    "Book a portrait",
                    rx.icon("arrow-right", class_name="h-4 w-4"),
                    href="/portraits",
                    class_name="inline-flex items-center gap-3 py-3 text-sm font-medium text-[var(--studio-text)] hover:text-[var(--studio-accent)]",
                ),
                class_name="flex flex-wrap items-center gap-x-7 gap-y-3 mt-9",
            ),
            class_name="w-full py-4 lg:py-12",
        ),
        rx.el.div(
            rx.cond(
                PublicState.settings["hero_image_path"] != "",
                rx.el.img(
                    src=rx.get_upload_url(
                        PublicState.settings["hero_image_path"]
                    ),
                    alt=f"Featured artwork from {PublicState.settings['brand_name']}",
                    class_name="w-full aspect-[4/5] max-h-[640px] object-cover",
                ),
                rx.el.div(
                    rx.el.div(
                        rx.icon(
                            "flower-2",
                            class_name="w-20 h-20 text-[var(--studio-accent)]",
                        ),
                        class_name="border border-[var(--studio-accent)]/30 rounded-t-full w-48 h-64 flex items-center justify-center",
                    ),
                    rx.el.p(
                        "Something personal.\nSomething to treasure.",
                        class_name="font-['Cormorant_Garamond'] text-3xl sm:text-4xl text-center whitespace-pre-line leading-tight",
                    ),
                    rx.el.span(
                        "THE STUDIO",
                        class_name="text-[10px] tracking-[0.3em] text-[var(--studio-accent)]",
                    ),
                    class_name="aspect-[4/5] max-h-[640px] flex flex-col items-center justify-center gap-9 bg-[var(--studio-accent)]/7 border border-[var(--studio-accent)]/15 p-8",
                ),
            ),
            rx.el.p(
                "A thoughtful gift begins with a little inspiration.",
                class_name="mt-4 text-xs text-[var(--studio-text)]/55 text-center",
            ),
            class_name="w-full min-w-0",
        ),
        class_name="grid lg:grid-cols-2 items-center gap-12 lg:gap-20 py-12 md:py-20",
    )


def studio_paths() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.p(
                "TWO WAYS TO MAKE IT PERSONAL",
                class_name="text-xs tracking-[0.2em] text-[var(--studio-accent)]",
            ),
            rx.el.h2(
                "Thoughtful by nature.",
                class_name="font-['Cormorant_Garamond'] text-4xl md:text-5xl mt-4",
            ),
            class_name="mb-10",
        ),
        rx.el.div(
            rx.el.a(
                rx.icon(
                    "flower-2", class_name="h-8 w-8 text-[var(--studio-accent)]"
                ),
                rx.el.h3(
                    "The bouquet collection",
                    class_name="font-['Cormorant_Garamond'] text-3xl mt-7",
                ),
                rx.el.p(
                    "Browse the artist’s available designs and find a bouquet that feels just right.",
                    class_name="mt-3 text-sm leading-6 text-[var(--studio-text)]/65",
                ),
                rx.el.span(
                    "Discover the collection",
                    rx.icon("arrow-up-right", class_name="h-4 w-4"),
                    class_name="inline-flex items-center gap-3 text-sm text-[var(--studio-accent)] mt-7",
                ),
                href="/bouquets",
                class_name="border border-[var(--studio-text)]/15 p-8 md:p-10 hover:border-[var(--studio-accent)]/60 transition-colors",
            ),
            rx.el.a(
                rx.icon(
                    "pencil-line",
                    class_name="h-8 w-8 text-[var(--studio-accent)]",
                ),
                rx.el.h3(
                    "A portrait, just for you",
                    class_name="font-['Cormorant_Garamond'] text-3xl mt-7",
                ),
                rx.el.p(
                    "Choose from the studio’s current portrait sizes and art styles, and prepare a photograph of someone special.",
                    class_name="mt-3 text-sm leading-6 text-[var(--studio-text)]/65",
                ),
                rx.el.span(
                    "Begin your portrait",
                    rx.icon("arrow-up-right", class_name="h-4 w-4"),
                    class_name="inline-flex items-center gap-3 text-sm text-[var(--studio-accent)] mt-7",
                ),
                href="/portraits",
                class_name="border border-[var(--studio-text)]/15 p-8 md:p-10 hover:border-[var(--studio-accent)]/60 transition-colors",
            ),
            class_name="grid md:grid-cols-2 gap-6",
        ),
        class_name="py-14 border-t border-[var(--studio-text)]/10",
    )


def artist_section() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.p(
                "BEHIND THE WORK",
                class_name="text-xs tracking-[0.2em] text-[var(--studio-accent)]",
            ),
            rx.el.h2(
                "Meet the artist",
                class_name="font-['Cormorant_Garamond'] text-4xl md:text-5xl mt-4",
            ),
        ),
        rx.el.div(
            rx.el.p(
                rx.cond(
                    PublicState.settings["artist_biography"] != "",
                    PublicState.settings["artist_biography"],
                    "The artist’s story will be shared here soon. In the meantime, explore the collection or get in touch about a personal piece.",
                ),
                class_name="whitespace-pre-line break-words text-base leading-8 text-[var(--studio-text)]/70",
            ),
            rx.el.a(
                "Say hello to the studio",
                rx.icon("arrow-right", class_name="h-4 w-4"),
                href="#contact",
                class_name="inline-flex items-center gap-3 text-sm text-[var(--studio-accent)] mt-7 hover:underline",
            ),
        ),
        id="artist",
        class_name="grid md:grid-cols-[1fr_1.5fr] gap-8 md:gap-16 border-t border-[var(--studio-text)]/10 py-16 md:py-24",
    )


def home_page() -> rx.Component:
    return public_layout(
        rx.el.div(
            home_hero(),
            studio_paths(),
            artist_section(),
            class_name="w-full max-w-7xl mx-auto px-6 md:px-10",
        )
    )


def bouquets_page() -> rx.Component:
    return public_layout(
        rx.el.div(
            rx.el.section(
                rx.el.p(
                    "THE BOUQUET COLLECTION",
                    class_name="text-xs tracking-[0.25em] text-[var(--studio-accent)] mb-5",
                ),
                rx.el.h1(
                    "Flowers with a personal touch.",
                    class_name="font-['Cormorant_Garamond'] text-5xl md:text-6xl font-medium leading-tight",
                ),
                rx.el.p(
                    "Explore the studio’s current bouquet designs. Choose a favourite, select your quantity and create an order with your customer account.",
                    class_name="mt-5 text-base leading-7 text-[var(--studio-text)]/65 max-w-2xl",
                ),
                class_name="pt-14 md:pt-20 pb-12 md:pb-16",
            ),
            collection(),
            bouquet_order_panel(),
            rx.el.p(
                "Only designs listed by the artist are shown. Orders save the current catalog price in Indian rupees. Please confirm availability with the studio before paying.",
                class_name="text-xs leading-6 text-[var(--studio-text)]/55 mt-10",
            ),
            class_name="w-full max-w-7xl mx-auto px-6 md:px-10 pb-20",
        ),
    )


def size_card(size: PortraitSize) -> rx.Component:
    return rx.el.button(
        rx.el.div(
            rx.el.span(
                size["name"],
                class_name="font-['Cormorant_Garamond'] text-4xl break-words",
            ),
            rx.cond(
                PublicState.portrait_size_id == size["id"],
                rx.icon(
                    "circle-check",
                    class_name="h-5 w-5 text-[var(--studio-accent)]",
                ),
                rx.icon(
                    "circle", class_name="h-5 w-5 text-[var(--studio-text)]/30"
                ),
            ),
            class_name="flex items-center justify-between",
        ),
        rx.el.p(
            size["dimensions"],
            class_name="mt-2 text-xs text-[var(--studio-text)]/60",
        ),
        rx.el.p(
            f"From ₹{size['price_paise'] / 100:,.2f}",
            class_name="mt-6 text-sm font-medium",
        ),
        rx.el.p(
            "Provisional example",
            class_name="mt-1 text-[11px] text-[var(--studio-text)]/55",
        ),
        on_click=lambda: PublicState.choose_size(size["id"]),
        key=size["id"],
        disabled=CustomerState.busy | PublicState.loading,
        type="button",
        aria_pressed=PublicState.portrait_size_id == size["id"],
        class_name=rx.cond(
            PublicState.portrait_size_id == size["id"],
            "w-full text-left border border-[var(--studio-accent)] bg-[var(--studio-accent)]/7 text-[var(--studio-text)] p-6 focus-visible:outline-2 focus-visible:outline-offset-4",
            "w-full text-left border border-[var(--studio-text)]/20 bg-transparent text-[var(--studio-text)] p-6 hover:border-[var(--studio-accent)] focus-visible:outline-2 focus-visible:outline-offset-4",
        ),
    )


def style_card(style: PortraitStyle) -> rx.Component:
    return rx.el.button(
        rx.icon(
            "paintbrush",
            class_name="h-5 w-5 shrink-0 text-[var(--studio-accent)]",
        ),
        rx.el.span(style["name"], class_name="text-sm break-words"),
        rx.cond(
            PublicState.portrait_style_id == style["id"],
            rx.icon(
                "circle-check",
                class_name="h-5 w-5 ml-auto text-[var(--studio-accent)]",
            ),
            rx.icon(
                "circle",
                class_name="h-5 w-5 ml-auto text-[var(--studio-text)]/30",
            ),
        ),
        on_click=lambda: PublicState.choose_style(style["id"]),
        key=style["id"],
        type="button",
        disabled=CustomerState.busy | PublicState.loading,
        aria_pressed=PublicState.portrait_style_id == style["id"],
        class_name=rx.cond(
            PublicState.portrait_style_id == style["id"],
            "w-full flex items-center gap-3 p-5 border border-[var(--studio-accent)] bg-[var(--studio-accent)]/7 text-[var(--studio-text)] focus-visible:outline-2",
            "w-full flex items-center gap-3 p-5 border border-[var(--studio-text)]/20 bg-transparent text-[var(--studio-text)] hover:border-[var(--studio-accent)] focus-visible:outline-2",
        ),
    )


def reference_entry() -> rx.Component:
    return rx.el.section(
        rx.el.h2(
            "03 / Prepare your reference", class_name="text-sm font-medium mb-4"
        ),
        rx.upload.root(
            rx.el.div(
                rx.icon(
                    "image-plus",
                    class_name="h-7 w-7 text-[var(--studio-accent)]",
                ),
                rx.el.p(
                    "Choose a reference photograph",
                    class_name="text-sm font-medium",
                ),
                rx.el.p(
                    "Click to select or drop one image here",
                    class_name="text-xs text-[var(--studio-text)]/60",
                ),
                rx.el.p(
                    "JPEG, PNG or WebP · up to 10 MB",
                    class_name="text-xs text-[var(--studio-text)]/50",
                ),
                class_name="flex flex-col items-center text-center gap-3 py-7 px-5",
            ),
            id="portrait-reference",
            multiple=False,
            max_files=1,
            accept={
                "image/jpeg": [".jpg", ".jpeg"],
                "image/png": [".png"],
                "image/webp": [".webp"],
            },
            class_name="w-full border border-dashed border-[var(--studio-text)]/25 bg-transparent cursor-pointer hover:border-[var(--studio-accent)] text-[var(--studio-text)]",
        ),
        rx.foreach(
            rx.selected_files("portrait-reference"),
            lambda filename: rx.el.div(
                rx.icon(
                    "file-image",
                    class_name="h-4 w-4 shrink-0 text-[var(--studio-accent)]",
                ),
                rx.el.p(
                    "One reference selected",
                    class_name="min-w-0 text-sm text-[var(--studio-text)]",
                ),
                rx.el.button(
                    "Remove",
                    on_click=rx.clear_selected_files("portrait-reference"),
                    type="button",
                    class_name="text-xs underline text-[var(--studio-accent)] ml-auto",
                ),
                class_name="mt-3 flex items-center gap-3 border border-[var(--studio-text)]/15 p-3",
            ),
        ),
        rx.el.p(
            "Order Now uploads the selected image and saves it privately with your order. Only your signed-in account and the studio owner can view the saved reference. JPEG, PNG or WebP only; oversized or invalid images are rejected on submission.",
            class_name="text-xs text-[var(--studio-text)]/60 leading-6 mt-4",
        ),
        rx.el.p(
            "Choose a clear, well-lit photo with the face in focus, and make sure you have permission to share it.",
            class_name="text-xs text-[var(--studio-text)]/60 leading-6 mt-2",
        ),
        class_name="mt-9",
    )


def portraits_page() -> rx.Component:
    return public_layout(
        rx.el.div(
            rx.el.section(
                rx.el.p(
                    "PERSONAL PORTRAITS",
                    class_name="text-xs tracking-[0.25em] text-[var(--studio-accent)] mb-5",
                ),
                rx.el.h1(
                    "A familiar face.\nA forever feeling.",
                    class_name="font-['Cormorant_Garamond'] text-5xl md:text-6xl font-medium leading-tight whitespace-pre-line",
                ),
                rx.el.p(
                    "Turn a favourite photograph into a personal portrait. Choose a size and art style, then upload your reference to create an order. The artist must still confirm the final quote.",
                    class_name="text-base leading-7 text-[var(--studio-text)]/65 mt-6 max-w-xl",
                ),
                class_name="pt-14 md:pt-20 pb-12",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        rx.icon(
                            "pencil-line",
                            class_name="h-10 w-10 text-[var(--studio-accent)] mb-6",
                        ),
                        rx.el.p(
                            "Made around\nyour memories.",
                            class_name="font-['Cormorant_Garamond'] text-4xl md:text-5xl whitespace-pre-line text-center leading-tight",
                        ),
                        rx.el.p(
                            "YOUR SIZE. YOUR STYLE.",
                            class_name="mt-8 text-xs tracking-[0.3em] text-[var(--studio-accent)]",
                        ),
                        class_name="aspect-[4/5] max-h-[540px] flex flex-col items-center justify-center border border-[var(--studio-accent)]/20 bg-[var(--studio-accent)]/7 p-8",
                    ),
                    rx.el.div(
                        rx.icon(
                            "shield-check",
                            class_name="h-5 w-5 shrink-0 text-[var(--studio-accent)]",
                        ),
                        rx.el.p(
                            "Your reference is personal. No customer photos or payment proofs are displayed in this public gallery.",
                            class_name="text-xs leading-6 text-[var(--studio-text)]/60",
                        ),
                        class_name="flex gap-3 mt-5",
                    ),
                ),
                rx.el.div(
                    rx.el.h2(
                        "01 / Choose your size",
                        class_name="text-sm font-medium mb-4",
                    ),
                    rx.el.button(
                        rx.icon("refresh-cw", class_name="h-4 w-4"),
                        "Refresh portrait options",
                        on_click=PublicState.load_public,
                        disabled=CustomerState.busy | PublicState.loading,
                        type="button",
                        class_name="flex items-center gap-2 mb-4 text-xs text-[var(--studio-accent)] hover:underline",
                    ),
                    rx.cond(
                        PublicState.loading,
                        rx.el.div(
                            role="status",
                            aria_label="Loading portrait options",
                            class_name="h-40 animate-pulse bg-[var(--studio-text)]/5",
                        ),
                        rx.cond(
                            PublicState.portrait_sizes.length() > 0,
                            rx.el.div(
                                rx.foreach(
                                    PublicState.portrait_sizes, size_card
                                ),
                                class_name="grid sm:grid-cols-2 gap-4",
                            ),
                            rx.el.p(
                                "No portrait sizes are available. Please contact the studio or refresh later.",
                                class_name="border border-[var(--studio-text)]/20 p-5 text-sm text-[var(--studio-text)]/65",
                            ),
                        ),
                    ),
                    rx.el.h2(
                        "02 / Choose your art style",
                        class_name="text-sm font-medium mt-8 mb-4",
                    ),
                    rx.cond(
                        PublicState.portrait_styles.length() > 0,
                        rx.el.div(
                            rx.foreach(PublicState.portrait_styles, style_card),
                            class_name="grid sm:grid-cols-2 gap-4",
                        ),
                        rx.el.p(
                            "No art styles are currently available. Portrait booking is paused until options are published.",
                            class_name="border border-[var(--studio-text)]/20 p-5 text-sm text-[var(--studio-text)]/65",
                        ),
                    ),
                    rx.cond(
                        PublicState.selection_notice != "",
                        rx.el.p(
                            PublicState.selection_notice,
                            role="status",
                            class_name="mt-4 text-sm text-[var(--studio-accent)]",
                        ),
                    ),
                    rx.cond(
                        PublicState.load_error != "",
                        rx.el.p(
                            PublicState.load_error,
                            role="alert",
                            class_name="mt-4 text-sm text-red-500",
                        ),
                    ),
                    rx.el.p(
                        "These are provisional prices, not artist-confirmed rates. Your order saves the current size price and selected labels at submission. Contact the studio to confirm the final price, style, number of subjects and timing before paying.",
                        class_name="mt-4 text-xs leading-6 text-[var(--studio-text)]/60",
                    ),
                    reference_entry(),
                    feedback(),
                    rx.el.div(
                        rx.el.p(
                            PublicState.portrait_selection,
                            class_name="text-sm text-[var(--studio-text)]/70 mb-4",
                        ),
                        rx.el.button(
                            rx.cond(
                                CustomerState.busy,
                                "Uploading & saving…",
                                "Order Now",
                            ),
                            rx.icon("arrow-up-right", class_name="h-4 w-4"),
                            on_click=CustomerState.order_portrait(
                                rx.upload_files(upload_id="portrait-reference")
                            ),
                            disabled=(
                                rx.selected_files("portrait-reference").length()
                                != 1
                            )
                            | CustomerState.busy
                            | PublicState.loading
                            | (PublicState.portrait_size_id == 0)
                            | (PublicState.portrait_style_id == 0)
                            | (PublicState.portrait_sizes.length() == 0)
                            | (PublicState.portrait_styles.length() == 0),
                            aria_describedby="portrait-order-help",
                            aria_busy=CustomerState.busy,
                            type="button",
                            class_name="w-full flex items-center justify-center gap-4 bg-[var(--studio-accent)] text-[var(--studio-bg)] px-6 py-4 text-sm font-medium enabled:hover:opacity-85 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-4",
                        ),
                        rx.el.p(
                            "Choose a size, art style and one reference photo before ordering.",
                            id="portrait-order-help",
                            class_name="text-xs text-[var(--studio-text)]/70 mt-3",
                        ),
                        rx.el.p(
                            "Sign in first if needed, then select your photo again. This creates an order, not a payment.",
                            class_name="text-center text-xs text-[var(--studio-text)]/50 mt-3",
                        ),
                        class_name="mt-8",
                    ),
                ),
                class_name="grid lg:grid-cols-2 gap-10 lg:gap-20 items-start",
            ),
            class_name="w-full max-w-7xl mx-auto px-6 md:px-10 pb-20",
        ),
    )
