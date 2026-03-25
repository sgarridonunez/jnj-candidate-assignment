#!/usr/bin/env python3
"""Download monthly CBS manufacturing data for selected Dutch industries.

The default benchmark set is tailored to the question:
"How has Dutch pharmaceutical manufacturing performed relative to chemicals
and total manufacturing since 2021?"

Data source:
https://opendata.cbs.nl/ODataApi/OData/85806NED
"""

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen


DATASET_ID = "85806NED"
BASE_URL = f"https://opendata.cbs.nl/ODataApi/OData/{DATASET_ID}"
MONTHLY_PERIOD_RE = re.compile(r"^\d{4}MM\d{2}$")

DEFAULT_BENCHMARKS = {
    "pharma": "323200",
    "chemicals": "320700",
    "total_manufacturing": "307500",
}

ALL_BENCHMARKS = {
    **DEFAULT_BENCHMARKS,
    "chemicals_and_pharma": "320705",
    "refining_chemicals_rubber_plastics": "320005",
}

OUTPUT_COLUMNS = [
    "period",
    "industry_branch",
    "seasonally_adjusted_production",
    "calendar_corrected_production_change_year_on_year",
    "previous_period_seasonally_adjusted_production_change",
]

def parse_args():
    parser = argparse.ArgumentParser(
        description="Download monthly CBS manufacturing data for selected benchmarks."
    )
    parser.add_argument(
        "--start",
        default="2021-01",
        help="Start month as YYYY-MM or YYYY. Default: 2021-01",
    )
    parser.add_argument(
        "--full-history",
        action="store_true",
        help="Ignore --start and keep all available monthly rows.",
    )
    parser.add_argument(
        "--benchmarks",
        nargs="+",
        choices=sorted(ALL_BENCHMARKS),
        default=list(DEFAULT_BENCHMARKS),
        help=(
            "Benchmark labels to include. "
            f"Choices: {', '.join(sorted(ALL_BENCHMARKS))}"
        ),
    )
    parser.add_argument(
        "--output",
        default="cbs_manufacturing_monthly.csv",
        help="Output CSV path. Default: cbs_manufacturing_monthly.csv",
    )
    return parser.parse_args()


def parse_start_filter(raw_value):
    if re.fullmatch(r"\d{4}", raw_value):
        return f"{int(raw_value):04d}MM01"
    if re.fullmatch(r"\d{4}-\d{2}", raw_value):
        year_str, month_str = raw_value.split("-")
        year = int(year_str)
        month = int(month_str)
        if 1 <= month <= 12:
            return f"{year:04d}MM{month:02d}"
    raise ValueError("Expected --start in YYYY or YYYY-MM format.")


def fetch_json(url):
    with urlopen(url) as response:
        return json.load(response)


def paged_values(url):
    next_url = url
    while next_url:
        payload = fetch_json(next_url)
        yield from payload.get("value", [])
        next_url = payload.get("odata.nextLink")


def build_dataset_url(benchmark_codes):
    filters = [
        f"BedrijfstakkenBranchesSBI2008 eq '{code}'" for code in benchmark_codes
    ]
    select_clause = ",".join(
        [
            "BedrijfstakkenBranchesSBI2008",
            "Perioden",
            "SeizoengecorrigeerdeProductie_3",
            "KalendergecorrigeerdeProductie_14",
            "OntwSeizoengecorrigeerdeProductie_21",
        ]
    )
    filter_clause = " or ".join(filters)
    encoded_filter = quote(filter_clause, safe="()'")
    encoded_select = quote(select_clause, safe=",")
    return f"{BASE_URL}/TypedDataSet?$filter={encoded_filter}&$select={encoded_select}"


def is_monthly_period(period_key):
    return bool(MONTHLY_PERIOD_RE.fullmatch(period_key))


def to_iso_date(period_key):
    year = int(period_key[:4])
    month = int(period_key[-2:])
    return date(year, month, 1).isoformat()


def transform_rows(
    raw_rows,
    label_by_code,
    start_filter,
):
    rows = []
    for item in raw_rows:
        period_key = item["Perioden"]
        if not is_monthly_period(period_key):
            continue
        if start_filter and period_key < start_filter:
            continue

        code = item["BedrijfstakkenBranchesSBI2008"]
        rows.append(
            {
                "period": to_iso_date(period_key),
                "industry_branch": label_by_code.get(code, code),
                "seasonally_adjusted_production": item.get(
                    "SeizoengecorrigeerdeProductie_3"
                ),
                "calendar_corrected_production_change_year_on_year": item.get(
                    "KalendergecorrigeerdeProductie_14"
                ),
                "previous_period_seasonally_adjusted_production_change": item.get(
                    "OntwSeizoengecorrigeerdeProductie_21"
                ),
            }
        )

    rows.sort(key=lambda row: (row["period"], row["industry_branch"]))
    return rows


def write_csv(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run_download(
    start="2021",
    full_history=False,
    benchmarks=None,
    output="cbs_manufacturing_monthly.csv",
):
    if benchmarks is None:
        benchmarks = list(DEFAULT_BENCHMARKS)
    try:
        start_filter = None if full_history else parse_start_filter(start)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    unknown_benchmarks = [label for label in benchmarks if label not in ALL_BENCHMARKS]
    if unknown_benchmarks:
        print(
            "Error: Unknown benchmark(s): "
            + ", ".join(unknown_benchmarks)
            + ". Valid options are: "
            + ", ".join(sorted(ALL_BENCHMARKS)),
            file=sys.stderr,
        )
        return 2

    label_by_code = {ALL_BENCHMARKS[label]: label for label in benchmarks}
    url = build_dataset_url(label_by_code)
    raw_rows = list(paged_values(url))
    transformed_rows = transform_rows(raw_rows, label_by_code, start_filter)

    output_path = Path(output)
    write_csv(transformed_rows, output_path)

    first_date = transformed_rows[0]["period"] if transformed_rows else "n/a"
    last_date = transformed_rows[-1]["period"] if transformed_rows else "n/a"
    print(f"Saved {len(transformed_rows)} monthly rows to {output_path}")
    print(f"Benchmarks: {', '.join(benchmarks)}")
    print(f"Date range: {first_date} to {last_date}")
    print(f"Source: {BASE_URL}")
    return 0


def main():
    args = parse_args()
    return run_download(
        start=args.start,
        full_history=args.full_history,
        benchmarks=args.benchmarks,
        output=args.output,
    )


if __name__ == "__main__":
    # Easy settings:
    # 1. Change START_YEAR if needed.
    # 2. Set FULL_HISTORY = True to download every available month.
    # 3. Run: python3 "cbs_manufacturing_download.py"
    #
    # If you prefer command-line options, they still work, for example:
    # python3 "cbs_manufacturing_download.py" --start 2022-01 --full-history
    START_YEAR = 2021
    FULL_HISTORY = False
    BENCHMARKS = ["pharma", "chemicals", "total_manufacturing"]
    OUTPUT_FILE = "cbs_manufacturing_monthly.csv"

    if len(sys.argv) > 1:
        raise SystemExit(main())

    raise SystemExit(
        run_download(
            start=str(START_YEAR),
            full_history=FULL_HISTORY,
            benchmarks=BENCHMARKS,
            output=OUTPUT_FILE,
        )
    )
