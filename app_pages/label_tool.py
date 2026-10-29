"""Label tool page: CSV or printable Avery label PDF from Plant Toolbox URLs.

Anyone can use the app without an account. Invited users who sign in with
Google also get saved settings, two saved label icons, and a sidebar of
their most-used Plant Toolbox links.
"""

from __future__ import annotations

import base64
from datetime import datetime
from io import StringIO

import pandas as pd
import streamlit as st

from plant_label_pdf import (
    FONT_FAMILIES,
    LabelStyle,
    build_alignment_test_pdf,
    build_labels_pdf,
    template_choices,
)
from plant_scraper import parse_urls, scrape_plant
from user_store import ICON_SLOTS, UserStore, UserStoreError, normalize_email, prepare_icon

EDIT_COLUMNS = ["Common Name", "Scientific Name", "Light", "Water", "Source URL"]
OUTPUT_FORMATS = ["CSV spreadsheet", "PDF labels (Avery)"]
TEMPLATE_MAP = template_choices()

NO_ICON = "No icon"
UPLOAD_ICON = "Upload an image"
UPLOAD_ICON_ONCE = "Upload an image (this time only)"


def slot_label(slot: int) -> str:
    return f"My icon {slot}"


# Settings that are saved for signed-in members. Keys are widget keys.
SETTING_DEFAULTS: dict[str, object] = {
    "opt_labels_per_plant": 1,
    "opt_output_format": OUTPUT_FORMATS[0],
    "opt_template": next(iter(TEMPLATE_MAP)),
    "opt_font_family": next(iter(FONT_FAMILIES)),
    "opt_common_size": 8,
    "opt_scientific_size": 7,
    "opt_care_size": 6,
    "opt_safe_margin_in": 0.08,
    "opt_offset_x_in": 0.0,
    "opt_offset_y_in": 0.0,
    "opt_icon_choice": NO_ICON,
}
NUMBER_LIMITS = {
    "opt_labels_per_plant": (1, 100),
    "opt_common_size": (6, 14),
    "opt_scientific_size": (5, 12),
    "opt_care_size": (5, 11),
    "opt_safe_margin_in": (0.03, 0.20),
    "opt_offset_x_in": (-0.25, 0.25),
    "opt_offset_y_in": (-0.25, 0.25),
}
CHOICE_LIMITS = {
    "opt_output_format": OUTPUT_FORMATS,
    "opt_template": list(TEMPLATE_MAP),
    "opt_font_family": list(FONT_FAMILIES),
}


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------


def secrets_section(name: str):
    try:
        return st.secrets[name] if name in st.secrets else None
    except Exception:  # noqa: BLE001 - no secrets file at all
        return None


@st.cache_resource(show_spinner=False)
def _store_for(url: str, key: str) -> UserStore:
    return UserStore(url, key)


def get_store() -> UserStore | None:
    """Supabase client from secrets, or None when accounts aren't configured."""
    section = secrets_section("supabase")
    try:
        url, key = section["url"], section["secret_key"]
    except (KeyError, TypeError):
        return None
    return _store_for(url, key) if url and key else None


def sign_in_available() -> bool:
    return secrets_section("auth") is not None and get_store() is not None


def current_account() -> dict:
    """Work out who is using the app.

    Returns a dict with ``status`` set to one of:
    ``guest`` (not signed in), ``not_invited``, ``member``, or ``offline``
    (signed in and invited, but Supabase couldn't be reached).
    """
    if not sign_in_available():
        return {"status": "guest"}
    try:
        logged_in = bool(st.user.is_logged_in)
    except Exception:  # noqa: BLE001
        logged_in = False
    if not logged_in:
        return {"status": "guest"}

    email = normalize_email(st.user.get("email"))
    name = st.user.get("name") or email
    account = {"email": email, "name": name}

    cached = st.session_state.get("invite_check")
    if cached and cached[0] == email:
        invited = cached[1]
    else:
        try:
            invited = get_store().is_invited(email)
        except (UserStoreError, OSError) as exc:
            return {**account, "status": "offline", "error": str(exc)}
        st.session_state.invite_check = (email, invited)

    return {**account, "status": "member" if invited else "not_invited"}


def apply_settings(saved: dict) -> None:
    """Copy valid saved settings into widget state."""
    for key, default in SETTING_DEFAULTS.items():
        name = key.removeprefix("opt_")
        if name not in saved:
            continue
        value = saved[name]
        if key in CHOICE_LIMITS:
            if value in CHOICE_LIMITS[key]:
                st.session_state[key] = value
        elif key in NUMBER_LIMITS:
            low, high = NUMBER_LIMITS[key]
            try:
                number = type(default)(value)
            except (TypeError, ValueError):
                continue
            st.session_state[key] = min(max(number, low), high)
        elif key == "opt_icon_choice" and isinstance(value, str):
            st.session_state[key] = value


def collect_settings() -> dict:
    return {key.removeprefix("opt_"): st.session_state.get(key, default)
            for key, default in SETTING_DEFAULTS.items()}


def load_member_data(account: dict) -> None:
    """Load settings, icons, and frequent plants once per signed-in session."""
    email = account["email"]
    if st.session_state.get("member_loaded_for") == email:
        return
    store = get_store()
    try:
        saved = store.get_settings(email)
        apply_settings(saved)
        st.session_state.last_saved_settings = saved
        st.session_state.icon_cache = {slot: store.get_icon(email, slot) for slot in ICON_SLOTS}
        st.session_state.top_plants = store.top_plants(email)
    except (UserStoreError, OSError) as exc:
        st.session_state.icon_cache = {}
        st.session_state.top_plants = []
        st.warning(f"Couldn't load your saved settings right now ({exc}). You can keep working as usual.")
    st.session_state.member_loaded_for = email


def save_settings_if_changed() -> None:
    account = st.session_state.get("account", {})
    if account.get("status") != "member":
        return
    settings = collect_settings()
    if settings == st.session_state.get("last_saved_settings"):
        return
    try:
        get_store().save_settings(account["email"], settings)
        st.session_state.last_saved_settings = settings
        st.toast("Settings saved to your account", icon="💾")
    except (UserStoreError, OSError) as exc:
        st.toast(f"Couldn't save settings: {exc}", icon="⚠️")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def expand_plants(plants: list[dict], labels_per_plant: int) -> list[dict]:
    """Duplicate each plant entry for the requested label count."""
    rows = []
    for plant in plants:
        for _ in range(labels_per_plant):
            rows.append(plant.copy())
    return rows


def show_pdf_preview(pdf_bytes: bytes) -> None:
    """Embed a PDF preview in the app."""
    encoded = base64.b64encode(pdf_bytes).decode()
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{encoded}" '
        'width="100%" height="640" style="border:1px solid #ddd;border-radius:8px;">'
        "</iframe>",
        unsafe_allow_html=True,
    )


def add_url_to_input(url: str) -> None:
    current = st.session_state.get("url_input", "")
    existing = {part.strip().rstrip("/") for part in current.replace(",", "\n").splitlines()}
    if url.rstrip("/") in existing:
        return
    st.session_state.url_input = f"{current.rstrip()}\n{url}".strip()


def add_urls_to_input(urls: list[str]) -> None:
    for url in urls:
        add_url_to_input(url)


def forget_plant(url: str) -> None:
    account = st.session_state.get("account", {})
    try:
        get_store().forget_plant(account["email"], url)
        st.session_state.top_plants = [
            p for p in st.session_state.get("top_plants", []) if p["url"] != url
        ]
    except (UserStoreError, OSError) as exc:
        st.toast(f"Couldn't remove that plant: {exc}", icon="⚠️")


def clear_all() -> None:
    st.session_state.url_input = ""
    for key in ("plants_df", "output_df", "pdf_bytes"):
        st.session_state.pop(key, None)


def plant_button_label(plant: dict) -> str:
    name = plant.get("common_name") or plant.get("scientific_name") or plant["url"]
    return f"＋ {name}"


def render_frequent_plants() -> None:
    top_plants = st.session_state.get("top_plants", [])
    if not top_plants:
        st.caption("Plants you load most often will show up here.")
    else:
        st.caption("Click to add a link to the box.")
        for index, plant in enumerate(top_plants):
            add_col, forget_col = st.columns([6, 1])
            with add_col:
                st.button(
                    plant_button_label(plant),
                    key=f"add_plant_{index}",
                    help=f"{plant.get('scientific_name') or ''}  ·  used {plant['use_count']}×",
                    on_click=add_url_to_input,
                    args=(plant["url"],),
                    width="stretch",
                )
            with forget_col:
                st.button(
                    "✕",
                    key=f"forget_plant_{index}",
                    help="Remove from this list",
                    on_click=forget_plant,
                    args=(plant["url"],),
                )
        st.button(
            "Add all to the box",
            on_click=add_urls_to_input,
            args=([p["url"] for p in top_plants],),
            width="stretch",
        )


# --------------------------------------------------------------------------
# Sidebar: account, frequent plants, icons
# --------------------------------------------------------------------------

# Re-assigning each key every run keeps Streamlit from discarding settings
# whose widgets are hidden (e.g. PDF options while CSV is selected, or
# everything before plants are loaded).
for key, default in SETTING_DEFAULTS.items():
    st.session_state[key] = st.session_state.get(key, default)
st.session_state.setdefault("url_input", "")

account = current_account()
st.session_state.account = account
is_member = account["status"] == "member"
if is_member:
    load_member_data(account)

with st.sidebar:
    st.header("Your account")
    if not sign_in_available():
        st.caption("Accounts aren't set up on this copy of the app. Everything works without one.")
    elif account["status"] == "guest":
        st.caption(
            "Optional. Invited accounts can save settings, two label icons, "
            "and their most-used plants. Everyone else can use the full tool without signing in."
        )
        st.button("Sign in with Google", on_click=st.login, width="stretch")
    else:
        st.markdown(f"Signed in as **{account['name']}**")
        if account["name"] != account["email"]:
            st.caption(account["email"])
        if account["status"] == "not_invited":
            st.info(
                "This Google account isn't on the invite list, so nothing will be saved. "
                "You can still use the whole tool as a guest."
            )
        elif account["status"] == "offline":
            st.warning(
                "Your saved settings can't be reached right now, so you're working as a guest. "
                "Try again in a little while."
            )
        st.button("Sign out", on_click=st.logout, width="stretch")

    if is_member:
        st.divider()
        st.subheader("Frequent plants")
        # Filled in at the end of the script, so plants loaded on this run
        # show up right away.
        frequent_plants_area = st.container()

        st.divider()
        st.subheader("My icons")
        st.caption("Save up to two images to use on your labels.")
        icon_cache = st.session_state.setdefault("icon_cache", {})
        for slot in ICON_SLOTS:
            with st.container(border=True):
                st.markdown(f"**{slot_label(slot)}**")
                if icon_cache.get(slot):
                    st.image(icon_cache[slot], width=90)
                upload_version = st.session_state.get(f"icon_upload_version_{slot}", 0)
                upload = st.file_uploader(
                    "Replace" if icon_cache.get(slot) else "Upload",
                    type=["png", "jpg", "jpeg", "webp", "gif"],
                    key=f"icon_upload_{slot}_{upload_version}",
                    label_visibility="collapsed",
                )
                save_col, delete_col = st.columns(2)
                with save_col:
                    if st.button("Save", key=f"icon_save_{slot}", disabled=upload is None,
                                 width="stretch"):
                        try:
                            png = prepare_icon(upload.getvalue())
                            get_store().save_icon(account["email"], slot, png)
                            icon_cache[slot] = png
                            # A new key gives an empty uploader after saving.
                            st.session_state[f"icon_upload_version_{slot}"] = upload_version + 1
                            st.toast(f"Saved {slot_label(slot)}", icon="🖼️")
                            st.rerun()
                        except (ValueError, UserStoreError, OSError) as exc:
                            st.error(str(exc))
                with delete_col:
                    if st.button("Delete", key=f"icon_delete_{slot}",
                                 disabled=not icon_cache.get(slot), width="stretch"):
                        try:
                            get_store().delete_icon(account["email"], slot)
                            icon_cache[slot] = None
                            st.rerun()
                        except (UserStoreError, OSError) as exc:
                            st.error(str(exc))


# --------------------------------------------------------------------------
# Main page
# --------------------------------------------------------------------------

st.title("Plant Label Generator")
st.markdown(
    "Create plant labels from the "
    "[NC State Plant Toolbox](https://plants.ces.ncsu.edu/) as a **CSV** or **printable PDF**. "
    "Free to use, no account needed. A project of The Plant Ecologist."
)

with st.expander("How to use this tool", expanded=False):
    st.markdown(
        """
        1. Paste Plant Toolbox links below and click **Load plant data**.
        2. Review and edit names or care info in the table (one row per species).
        3. Choose label count, output format, and PDF options if needed.
        4. Click **Generate labels** to preview and download.

        Edits apply to **every label** for that plant species.

        **Printing tip:** if labels land a little off the sheet, open
        **Print alignment** in the PDF options, download the test page, and
        adjust the nudge until the outlines line up with your labels.
        """
    )

st.text_area(
    "Plant Toolbox links",
    height=140,
    key="url_input",
    placeholder=(
        "Paste plant links here, one per line, for example:\n"
        "https://plants.ces.ncsu.edu/plants/magnolia-ashei/\n"
        "https://plants.ces.ncsu.edu/plants/asimina-triloba/"
    ),
    help="Only links from plants.ces.ncsu.edu/plants/ are accepted.",
)

load_col, clear_col = st.columns([3, 1])
with load_col:
    load_plants = st.button("Load plant data", type="primary", width="stretch")
with clear_col:
    st.button("Clear", on_click=clear_all, width="stretch")

if load_plants:
    url_input = st.session_state.url_input
    if not url_input.strip():
        st.error("Please paste at least one Plant Toolbox link.")
    else:
        try:
            urls = parse_urls(url_input)
            progress = st.progress(0, text="Fetching plant information…")
            rows = []

            for index, url in enumerate(urls):
                rows.append(scrape_plant(url))
                progress.progress(
                    (index + 1) / len(urls),
                    text=f"Fetched {index + 1} of {len(urls)} plants…",
                )

            progress.empty()
            st.session_state.plants_df = pd.DataFrame(rows)[EDIT_COLUMNS]
            st.session_state.pop("output_df", None)
            st.session_state.pop("pdf_bytes", None)
            st.success(f"Loaded **{len(rows)}** plant(s). Edit the table below if needed.")

            if is_member:
                try:
                    store = get_store()
                    store.record_plant_usage(account["email"], rows)
                    st.session_state.top_plants = store.top_plants(account["email"])
                except (UserStoreError, OSError):
                    pass  # Suggestions are a nice-to-have; never block label making.
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")

if "plants_df" in st.session_state and st.session_state.plants_df is not None:
    st.subheader("Edit plant info")
    st.caption(
        "Changes here apply to all labels for that species. "
        "Click **Generate labels** again after editing."
    )

    edited_df = st.data_editor(
        st.session_state.plants_df,
        column_config={
            "Common Name": st.column_config.TextColumn("Common Name", required=True),
            "Scientific Name": st.column_config.TextColumn("Scientific Name", required=True),
            "Light": st.column_config.TextColumn("Light", help="Short label, e.g. Full Sun"),
            "Water": st.column_config.TextColumn("Water", help="Short label, e.g. Moist"),
            "Source URL": st.column_config.TextColumn("Source URL", disabled=True),
        },
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key="plant_data_editor",
    )
    st.session_state.plants_df = edited_df

    st.divider()

    st.number_input(
        "Labels needed per plant",
        min_value=1,
        max_value=100,
        step=1,
        key="opt_labels_per_plant",
        help="Each plant will appear this many times in the output.",
    )

    st.radio("Output format", options=OUTPUT_FORMATS, horizontal=True, key="opt_output_format")
    output_format = st.session_state.opt_output_format

    one_time_icon = None
    if output_format == "PDF labels (Avery)":
        st.subheader("PDF label options")
        st.selectbox(
            "Avery label template",
            options=list(TEMPLATE_MAP.keys()),
            format_func=lambda code: TEMPLATE_MAP[code],
            key="opt_template",
        )

        # Icon choice: saved icons for members, a one-time upload for everyone.
        icon_cache = st.session_state.get("icon_cache", {}) if is_member else {}
        icon_options = [NO_ICON]
        icon_options += [slot_label(s) for s in ICON_SLOTS if icon_cache.get(s)]
        icon_options.append(UPLOAD_ICON_ONCE if is_member else UPLOAD_ICON)
        if st.session_state.opt_icon_choice not in icon_options:
            # Keep a saved choice of a one-time upload meaningful for either label.
            if st.session_state.opt_icon_choice in (UPLOAD_ICON, UPLOAD_ICON_ONCE):
                st.session_state.opt_icon_choice = icon_options[-1]
            else:
                st.session_state.opt_icon_choice = NO_ICON
        st.radio("Label icon", options=icon_options, key="opt_icon_choice", horizontal=True,
                 help="Shown on the left side of each label.")
        if st.session_state.opt_icon_choice in (UPLOAD_ICON, UPLOAD_ICON_ONCE):
            one_time_icon = st.file_uploader(
                "Icon image",
                type=["png", "jpg", "jpeg", "webp", "gif"],
                label_visibility="collapsed",
            )
        elif is_member and len(icon_options) == 2:
            st.caption("Tip: save icons under **My icons** in the sidebar to reuse them.")

        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Font", options=list(FONT_FAMILIES.keys()), key="opt_font_family")
            st.slider("Common name size", 6, 14, key="opt_common_size")
        with col2:
            st.slider("Scientific name size", 5, 12, key="opt_scientific_size")
            st.slider("Light / water line size", 5, 11, key="opt_care_size")

        with st.expander("Print alignment"):
            st.caption(
                "Print the test page on plain paper at **100% / Actual size**, "
                "lay it on top of a label sheet, and hold both up to a window. "
                "If the outlines sit to the right of the real labels, use a negative "
                "left/right nudge. If they sit too low, use a negative up/down nudge."
            )
            nudge_x, nudge_y = st.columns(2)
            with nudge_x:
                st.number_input("Left / right nudge (inches)", -0.25, 0.25, step=0.01,
                                format="%.2f", key="opt_offset_x_in",
                                help="Positive moves everything right.")
            with nudge_y:
                st.number_input("Up / down nudge (inches)", -0.25, 0.25, step=0.01,
                                format="%.2f", key="opt_offset_y_in",
                                help="Positive moves everything down.")
            st.slider("Blank border inside each label (inches)", 0.03, 0.20, step=0.01,
                      key="opt_safe_margin_in",
                      help="Keeps text and icons away from the label edges and rounded corners.")
            show_outlines = st.checkbox("Draw label outlines on the PDF", value=False,
                                        help="Useful for a test print on plain paper.")
            test_style = LabelStyle(
                safe_margin_in=st.session_state.opt_safe_margin_in,
                offset_x_in=st.session_state.opt_offset_x_in,
                offset_y_in=st.session_state.opt_offset_y_in,
            )
            st.download_button(
                "Download alignment test page",
                data=build_alignment_test_pdf(st.session_state.opt_template, test_style),
                file_name=f"alignment_test_{st.session_state.opt_template}.pdf",
                mime="application/pdf",
                on_click=save_settings_if_changed,
                width="stretch",
            )
    else:
        show_outlines = False

    if is_member:
        st.caption("Your choices are saved to your account when you generate labels.")

    generate = st.button("Generate labels", type="primary", width="stretch")

    if generate:
        save_settings_if_changed()
        try:
            labels_per_plant = int(st.session_state.opt_labels_per_plant)
            plants = edited_df.to_dict("records")
            rows = expand_plants(plants, labels_per_plant)
            output_df = pd.DataFrame(rows)
            st.session_state.output_df = output_df

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if output_format == "CSV spreadsheet":
                st.session_state.pop("pdf_bytes", None)
                st.session_state.csv_timestamp = timestamp
            else:
                icon_bytes = None
                choice = st.session_state.opt_icon_choice
                if choice in (UPLOAD_ICON, UPLOAD_ICON_ONCE):
                    if one_time_icon is not None:
                        icon_bytes = one_time_icon.getvalue()
                else:
                    for slot in ICON_SLOTS:
                        if choice == slot_label(slot):
                            icon_bytes = st.session_state.get("icon_cache", {}).get(slot)

                style = LabelStyle(
                    font_family=st.session_state.opt_font_family,
                    common_size=st.session_state.opt_common_size,
                    scientific_size=st.session_state.opt_scientific_size,
                    care_size=st.session_state.opt_care_size,
                    safe_margin_in=st.session_state.opt_safe_margin_in,
                    offset_x_in=st.session_state.opt_offset_x_in,
                    offset_y_in=st.session_state.opt_offset_y_in,
                    show_outlines=show_outlines,
                )

                with st.spinner("Building PDF…"):
                    st.session_state.pdf_bytes = build_labels_pdf(
                        plants=rows,
                        template_code=st.session_state.opt_template,
                        style=style,
                        icon_bytes=icon_bytes,
                    )
                st.session_state.pdf_timestamp = timestamp

            st.success(
                f"Created **{len(rows)}** label(s) from **{len(plants)}** plant(s)."
            )
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")

    if "output_df" in st.session_state and st.session_state.output_df is not None:
        st.subheader("Preview")
        preview_cols = ["Common Name", "Scientific Name", "Light", "Water"]
        st.dataframe(
            st.session_state.output_df[preview_cols],
            width="stretch",
            hide_index=True,
        )

        if "pdf_bytes" in st.session_state and st.session_state.pdf_bytes is not None:
            show_pdf_preview(st.session_state.pdf_bytes)
            st.download_button(
                label="Download PDF labels",
                data=st.session_state.pdf_bytes,
                file_name=f"plant_labels_{st.session_state.get('pdf_timestamp', 'export')}.pdf",
                mime="application/pdf",
                type="primary",
                width="stretch",
            )
            st.caption(
                "Print at 100% scale (Actual size, no fit-to-page). "
                "Load the matching Avery sheet in your printer."
            )
        elif st.session_state.output_df is not None:
            csv_buffer = StringIO()
            st.session_state.output_df.to_csv(csv_buffer, index=False)
            st.download_button(
                label="Download CSV file",
                data=csv_buffer.getvalue(),
                file_name=f"plant_labels_{st.session_state.get('csv_timestamp', 'export')}.csv",
                mime="text/csv",
                type="primary",
                width="stretch",
            )

st.divider()
st.caption("Plant data comes from the NC State Extension Plant Toolbox (plants.ces.ncsu.edu).")
footer_privacy, footer_terms, _ = st.columns([1, 1, 2])
with footer_privacy:
    st.page_link("app_pages/privacy_policy.py", label="Privacy Policy")
with footer_terms:
    st.page_link("app_pages/terms_of_service.py", label="Terms of Service")

if is_member:
    with frequent_plants_area:
        render_frequent_plants()
