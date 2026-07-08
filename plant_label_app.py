"""Plant Label Generator — CSV or printable Avery label PDF from Plant Toolbox URLs."""

from datetime import datetime
from io import StringIO

import pandas as pd
import streamlit as st

from plant_label_pdf import (
    FONT_FAMILIES,
    LabelStyle,
    build_labels_pdf,
    render_pdf_preview_png,
    template_choices,
)
from plant_scraper import parse_urls, scrape_plant

st.set_page_config(
    page_title="Plant Label Generator",
    page_icon="🌿",
    layout="centered",
)

EDIT_COLUMNS = ["Common Name", "Scientific Name", "Light", "Water", "Source URL"]
POINTS_PER_INCH = 72.0


def expand_plants(plants: list[dict], labels_per_plant: int) -> list[dict]:
    """Duplicate each plant entry for the requested label count."""
    rows = []
    for plant in plants:
        for _ in range(labels_per_plant):
            rows.append(plant.copy())
    return rows


def show_pdf_preview(pdf_bytes: bytes) -> None:
    """Show the first page of the label sheet as an image (works in all browsers)."""
    preview_png = render_pdf_preview_png(pdf_bytes)
    st.image(preview_png, caption="Label sheet preview (page 1)", use_container_width=True)


st.title("Plant Label Generator")
st.markdown(
    "Create plant labels from the "
    "[NC State Plant Toolbox](https://plants.ces.ncsu.edu/) as a **CSV** or **printable PDF**."
)

with st.expander("How to use this tool", expanded=False):
    st.markdown(
        """
        1. Paste Plant Toolbox links below and click **Load plant data**.
        2. Review and edit names or care info in the table (one row per species).
        3. Choose label count, output format, and PDF options if needed.
        4. Click **Generate labels** to preview and download.

        Edits apply to **every label** for that plant species.
        """
    )

url_input = st.text_area(
    "Plant Toolbox links",
    height=140,
    placeholder=(
        "Paste plant links here — one per line, for example:\n"
        "https://plants.ces.ncsu.edu/plants/magnolia-ashei/\n"
        "https://plants.ces.ncsu.edu/plants/asimina-triloba/"
    ),
    help="Only links from plants.ces.ncsu.edu/plants/ are accepted.",
)

load_col, clear_col = st.columns([3, 1])
with load_col:
    load_plants = st.button("Load plant data", type="primary", use_container_width=True)
with clear_col:
    if st.button("Clear", use_container_width=True):
        st.session_state.pop("plants_df", None)
        st.session_state.pop("output_df", None)
        st.session_state.pop("pdf_bytes", None)
        st.session_state.pop("label_icon_bytes", None)
        st.rerun()

if load_plants:
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
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="plant_data_editor",
    )
    st.session_state.plants_df = edited_df

    st.divider()

    labels_per_plant = st.number_input(
        "Labels needed per plant",
        min_value=1,
        max_value=100,
        value=1,
        step=1,
        help="Each plant will appear this many times in the output.",
    )

    output_format = st.radio(
        "Output format",
        options=["CSV spreadsheet", "PDF labels (Avery)"],
        horizontal=True,
    )

    pdf_options = {}
    if output_format == "PDF labels (Avery)":
        st.subheader("PDF label options")
        template_map = template_choices()
        pdf_options["template"] = st.selectbox(
            "Avery label template",
            options=list(template_map.keys()),
            format_func=lambda code: template_map[code],
            index=0,
        )

        uploaded_icon = st.file_uploader(
            "Label icon (optional)",
            type=["png", "jpg", "jpeg", "webp", "gif"],
            help="Shown on the left side of each label.",
            key="label_icon_uploader",
        )
        if uploaded_icon is not None:
            st.session_state.label_icon_bytes = uploaded_icon.getvalue()

        if st.session_state.get("label_icon_bytes"):
            icon_col, clear_icon_col = st.columns([1, 3])
            with icon_col:
                st.image(
                    st.session_state.label_icon_bytes,
                    width=72,
                    caption="Icon preview",
                )
            with clear_icon_col:
                if st.button("Remove icon"):
                    st.session_state.pop("label_icon_bytes", None)
                    st.rerun()

        col1, col2 = st.columns(2)
        with col1:
            pdf_options["font_family"] = st.selectbox(
                "Font",
                options=list(FONT_FAMILIES.keys()),
            )
            pdf_options["common_size"] = st.slider("Common name size", 6, 14, 8)
        with col2:
            pdf_options["scientific_size"] = st.slider("Scientific name size", 5, 12, 7)
            pdf_options["care_size"] = st.slider("Light / water line size", 5, 11, 6)

        with st.expander("Print alignment (calibration)", expanded=False):
            st.caption(
                "Use small nudges if labels are shifted. "
                "Positive X moves right; positive Y moves up."
            )
            cal_col1, cal_col2 = st.columns(2)
            with cal_col1:
                pdf_options["offset_x_in"] = st.number_input(
                    "Horizontal offset (inches)",
                    min_value=-0.5,
                    max_value=0.5,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                )
            with cal_col2:
                pdf_options["offset_y_in"] = st.number_input(
                    "Vertical offset (inches)",
                    min_value=-0.5,
                    max_value=0.5,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                )

    generate = st.button("Generate labels", type="primary", use_container_width=True)

    if generate:
        try:
            plants = edited_df.to_dict("records")
            rows = expand_plants(plants, labels_per_plant)
            output_df = pd.DataFrame(rows)
            st.session_state.output_df = output_df

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if output_format == "CSV spreadsheet":
                st.session_state.pop("pdf_bytes", None)
                st.session_state.csv_timestamp = timestamp
            else:
                icon_bytes = st.session_state.get("label_icon_bytes")

                style = LabelStyle(
                    font_family=pdf_options["font_family"],
                    common_size=pdf_options["common_size"],
                    scientific_size=pdf_options["scientific_size"],
                    care_size=pdf_options["care_size"],
                )

                with st.spinner("Building PDF…"):
                    st.session_state.pdf_bytes = build_labels_pdf(
                        plants=rows,
                        template_code=pdf_options["template"],
                        style=style,
                        icon_bytes=icon_bytes,
                        offset_x_points=pdf_options["offset_x_in"] * POINTS_PER_INCH,
                        offset_y_points=pdf_options["offset_y_in"] * POINTS_PER_INCH,
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
            use_container_width=True,
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
                use_container_width=True,
            )
            st.caption(
                "Preview shows page 1 as an image. Download the PDF to print. "
                "Print at 100% scale (no fit-to-page)."
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
                use_container_width=True,
            )

st.caption("Data source: NC State Extension Plant Toolbox (plants.ces.ncsu.edu)")
