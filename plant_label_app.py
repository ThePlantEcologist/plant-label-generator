"""Plant Label Generator — CSV or printable Avery label PDF from Plant Toolbox URLs."""

from datetime import datetime
from io import StringIO

import pandas as pd
import streamlit as st

from plant_label_pdf import (
    FONT_FAMILIES,
    LabelStyle,
    build_labels_pdf,
    template_choices,
)
from plant_scraper import parse_urls, scrape_plant

st.set_page_config(
    page_title="Plant Label Generator",
    page_icon="🌿",
    layout="centered",
)

st.title("Plant Label Generator")
st.markdown(
    "Create plant labels from the "
    "[NC State Plant Toolbox](https://plants.ces.ncsu.edu/) as a **CSV** or **printable PDF**."
)

with st.expander("How to use this tool", expanded=False):
    st.markdown(
        """
        1. Open a plant page on the [Plant Toolbox](https://plants.ces.ncsu.edu/).
        2. Copy the web address from your browser.
        3. Paste one or more plant links below (one per line, or separated by commas).
        4. Choose how many labels you need **for each plant**.
        5. Pick **CSV** or **PDF** output and customize PDF options if needed.
        6. Click **Generate labels**, preview, then download.

        **Example link:** `https://plants.ces.ncsu.edu/plants/magnolia-ashei/`
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

    pdf_options["icon_file"] = st.file_uploader(
        "Label icon (optional)",
        type=["png", "jpg", "jpeg", "webp", "gif"],
        help="Shown on the left side of each label. Use a simple square logo or plant icon.",
    )

    col1, col2 = st.columns(2)
    with col1:
        pdf_options["font_family"] = st.selectbox(
            "Font",
            options=list(FONT_FAMILIES.keys()),
        )
        pdf_options["common_size"] = st.slider("Common name size", 6, 14, 9)
    with col2:
        pdf_options["scientific_size"] = st.slider("Scientific name size", 5, 12, 8)
        pdf_options["care_size"] = st.slider("Light / water line size", 5, 11, 7)

generate = st.button("Generate labels", type="primary", use_container_width=True)

if generate:
    if not url_input.strip():
        st.error("Please paste at least one Plant Toolbox link.")
    else:
        try:
            urls = parse_urls(url_input)
            progress = st.progress(0, text="Fetching plant information…")
            rows = []

            for index, url in enumerate(urls):
                plant_data = scrape_plant(url)
                for _ in range(labels_per_plant):
                    rows.append(plant_data.copy())
                progress.progress(
                    (index + 1) / len(urls),
                    text=f"Fetched {index + 1} of {len(urls)} plants…",
                )

            progress.empty()
            df = pd.DataFrame(rows)

            st.success(
                f"Ready! Created **{len(df)}** label(s) from **{len(urls)}** plant(s)."
            )

            st.subheader("Preview")
            preview_cols = ["Common Name", "Scientific Name", "Light", "Water"]
            st.dataframe(
                df[preview_cols],
                use_container_width=True,
                hide_index=True,
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if output_format == "CSV spreadsheet":
                csv_buffer = StringIO()
                df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="Download CSV file",
                    data=csv_buffer.getvalue(),
                    file_name=f"plant_labels_{timestamp}.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True,
                )
            else:
                icon_bytes = None
                if pdf_options.get("icon_file") is not None:
                    icon_bytes = pdf_options["icon_file"].getvalue()

                style = LabelStyle(
                    font_family=pdf_options["font_family"],
                    common_size=pdf_options["common_size"],
                    scientific_size=pdf_options["scientific_size"],
                    care_size=pdf_options["care_size"],
                )

                with st.spinner("Building PDF…"):
                    pdf_bytes = build_labels_pdf(
                        plants=rows,
                        template_code=pdf_options["template"],
                        style=style,
                        icon_bytes=icon_bytes,
                    )

                st.download_button(
                    label="Download PDF labels",
                    data=pdf_bytes,
                    file_name=f"plant_labels_{timestamp}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
                st.caption(
                    "Print at 100% scale (no fit-to-page). "
                    "Load the matching Avery sheet in your printer."
                )

        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")

st.caption("Data source: NC State Extension Plant Toolbox (plants.ces.ncsu.edu)")
