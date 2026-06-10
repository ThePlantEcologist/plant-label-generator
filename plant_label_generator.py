#!/usr/bin/env python3
"""Command-line wrapper for the plant label CSV generator."""

import argparse
import sys
from datetime import datetime

from plant_scraper import build_label_rows, parse_urls


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate plant label CSV data from NC State Plant Toolbox URLs."
    )
    parser.add_argument("--urls", help="Comma-separated Plant Toolbox URLs.")
    parser.add_argument("--labels", type=int, help="Number of label rows per plant.")
    parser.add_argument("--output", help="Output CSV filename.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        url_input = args.urls or input(
            "Plant Toolbox URLs (comma-separated): "
        ).strip()
        urls = parse_urls(url_input)

        if args.labels is not None:
            if args.labels < 1:
                raise ValueError("Number of labels must be 1 or greater.")
            labels_per_plant = args.labels
        else:
            labels_per_plant = int(input("Labels per plant: ").strip())

        default_name = f"plant_labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        output_path = args.output or input(f"Output CSV [{default_name}]: ").strip() or default_name
        if not output_path.lower().endswith(".csv"):
            output_path += ".csv"

        df = build_label_rows(urls, labels_per_plant)
        df.to_csv(output_path, index=False)
        print(f"Done! Wrote {len(df)} label row(s) to '{output_path}'.")
        return 0

    except (ValueError, KeyboardInterrupt) as exc:
        if isinstance(exc, KeyboardInterrupt):
            print("\nCancelled.")
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
