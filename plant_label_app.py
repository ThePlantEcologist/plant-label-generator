"""Plant Label Generator — simple web app for creating plant label CSV files."""

from datetime import datetime
from io import StringIO

import pandas as pd
import streamlit as st

from plant_scraper import parse_urls, scrape_plant

st.set_page_config(
    page_title="Plant Label Generator",
    page_icon="🌿",
    layout="centered",
)

st.title("Plant Label Generator")
st.markdown(
    "Create a CSV file for plant labels using information from the "
    "[NC State Plant Toolbox](https://plants.ces.ncsu.edu/)."
)

with st.expander("How to use this tool", expanded=False):
    st.markdown(
        """
        1. Open a plant page on the [Plant Toolbox](https://plants.ces.ncsu.edu/).
        2. Copy the web address from your browser.
        3. Paste one or more plant links below (one per line, or separated by commas).
        4. Choose how many labels you need **for each plant**.
        5. Click **Generate CSV**, preview the results, then download the file.

        **Example link:**  
        `https://plants.ces.ncsu.edu/plants/magnolia-ashei/`

        The CSV includes: common name, scientific name, light, water, soil, and pH.
        """
    )

url_input = st.text_area(
    "Plant Toolbox links",
    height=160,
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
    help="Each plant will appear this many times in the CSV (one row per label).",
)

generate = st.button("Generate CSV", type="primary", use_container_width=True)

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
                f"Ready! Created **{len(df)}** label row(s) "
                f"from **{len(urls)}** plant(s)."
            )

            st.subheader("Preview")
            st.dataframe(df, use_container_width=True, hide_index=True)

            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"plant_labels_{timestamp}.csv"

            st.download_button(
                label="Download CSV file",
                data=csv_buffer.getvalue(),
                file_name=filename,
                mime="text/csv",
                type="primary",
                use_container_width=True,
            )

        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")

st.caption("Data source: NC State Extension Plant Toolbox (plants.ces.ncsu.edu)")
