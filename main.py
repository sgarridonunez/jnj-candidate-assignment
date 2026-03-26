#!/usr/bin/env python3

import argparse
from pathlib import Path
import sys

MISSING_PACKAGES = []

try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError:
    plt = None
    MISSING_PACKAGES.append("matplotlib")

try:
    import numpy as np
except ModuleNotFoundError:
    np = None
    MISSING_PACKAGES.append("numpy")

try:
    import pandas as pd
except ModuleNotFoundError:
    pd = None
    MISSING_PACKAGES.append("pandas")

try:
    from cbs_manufacturing_download import run_download
except ModuleNotFoundError:
    run_download = None


# Edit these settings if needed.
START_YEAR = 2021
REFRESH_DATA = True
TIME_LEVEL = "monthly"  # choose: "monthly", "quarterly", or "annual"
INPUT_FILE = "cbs_manufacturing_monthly.csv"
OUTPUT_FOLDER = "outputs"
OUTPUT_CHART = "pharma_vs_benchmarks.png"


EXPECTED_BRANCHES = ["pharma", "chemicals", "total_manufacturing"]
REQUIRED_COLUMNS = [
    "period",
    "industry_branch",
    "seasonally_adjusted_production",
    "calendar_corrected_production_change_year_on_year",
    "previous_period_seasonally_adjusted_production_change",
]
DISPLAY_NAMES = {
    "pharma": "Pharmaceuticals",
    "chemicals": "Chemicals",
    "total_manufacturing": "Total manufacturing",
}
COLORS = {
    "pharma": "#c23b22",
    "chemicals": "#1f77b4",
    "total_manufacturing": "#555555",
}
CHART_TITLE = "Seasonally adjusted production index"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the CBS manufacturing benchmark analysis."
    )
    parser.add_argument(
        "--time-level",
        choices=["monthly", "quarterly", "annual"],
        help="Override TIME_LEVEL without editing the file.",
    )
    parser.add_argument(
        "--refresh-data",
        dest="refresh_data",
        action="store_true",
        help="Force a fresh CBS download before analysis.",
    )
    parser.add_argument(
        "--no-refresh-data",
        dest="refresh_data",
        action="store_false",
        help="Reuse the existing local CSV instead of downloading again.",
    )
    parser.set_defaults(refresh_data=None)
    return parser.parse_args()


def check_requirements():
    if MISSING_PACKAGES:
        package_list = ", ".join(MISSING_PACKAGES)
        print(
            "Missing required package(s): " + package_list,
            file=sys.stderr,
        )
        print(
            "Install them with: python3 -m pip install pandas numpy matplotlib",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if run_download is None:
        print(
            "Could not import 'run_download' from 'cbs_manufacturing_download.py'.",
            file=sys.stderr,
        )
        print(
            "Make sure 'cbs_manufacturing_download.py' is in the same folder as 'main.py'.",
            file=sys.stderr,
        )
        raise SystemExit(1)


def refresh_data(should_refresh):
    if not should_refresh:
        return

    result = run_download(
        start=str(START_YEAR),
        full_history=False,
        benchmarks=EXPECTED_BRANCHES,
        output=INPUT_FILE,
    )
    if result != 0:
        raise ValueError("Data download failed.")


def load_data(path):
    if not Path(path).exists():
        raise ValueError(
            f"Input file not found: {path}. "
            "Run the downloader first or keep REFRESH_DATA = True."
        )

    df = pd.read_csv(path)

    if df.empty:
        raise ValueError("The input file is empty.")

    if list(df.columns) != REQUIRED_COLUMNS:
        raise ValueError(
            "Unexpected columns. Expected: " + ", ".join(REQUIRED_COLUMNS)
        )

    df["period"] = pd.to_datetime(df["period"])

    numeric_columns = REQUIRED_COLUMNS[2:]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["industry_branch"] = pd.Categorical(
        df["industry_branch"],
        categories=EXPECTED_BRANCHES,
        ordered=True,
    )

    df = df.sort_values(["industry_branch", "period"]).reset_index(drop=True)
    return df


def run_quality_checks(df):
    found_branches = sorted(df["industry_branch"].dropna().astype(str).unique().tolist())
    if found_branches != sorted(EXPECTED_BRANCHES):
        raise ValueError(f"Unexpected branches found: {found_branches}")

    duplicate_count = int(df.duplicated(subset=["industry_branch", "period"]).sum())
    if duplicate_count:
        raise ValueError(f"Found {duplicate_count} duplicate branch/period rows.")

    missing_counts = df[REQUIRED_COLUMNS].isna().sum()
    missing_columns = missing_counts[missing_counts > 0]
    if not missing_columns.empty:
        raise ValueError(
            "Missing values found in: "
            + ", ".join(f"{col} ({count})" for col, count in missing_columns.items())
        )

    quality_lines = ["Data quality checks passed:"]
    expected_periods = pd.date_range(df["period"].min(), df["period"].max(), freq="MS")

    for branch in EXPECTED_BRANCHES:
        branch_df = df[df["industry_branch"] == branch]
        branch_periods = branch_df["period"].sort_values()

        if branch_df.empty:
            raise ValueError(f"No rows found for {branch}")

        missing_periods = expected_periods.difference(branch_periods)
        if len(missing_periods) > 0:
            raise ValueError(
                f"Missing monthly periods for {branch}: "
                + ", ".join(period.strftime("%Y-%m-%d") for period in missing_periods[:5])
            )

        quality_lines.append(
            f"- {DISPLAY_NAMES[branch]}: {len(branch_df)} monthly observations"
        )

    quality_lines.append("- No duplicate branch/period rows")
    quality_lines.append("- No missing values in the selected metrics")
    return quality_lines


def prepare_analysis_data(df, time_level):
    if time_level == "monthly":
        return df.copy()

    period_map = {
        "quarterly": "Q",
        "annual": "Y",
    }
    if time_level in period_map:
        return (
            df.assign(period=df["period"].dt.to_period(period_map[time_level]).dt.start_time)
            .groupby(["industry_branch", "period"], as_index=False)
            .agg(
                {
                    "seasonally_adjusted_production": "mean",
                    "calendar_corrected_production_change_year_on_year": "mean",
                    "previous_period_seasonally_adjusted_production_change": "mean",
                }
            )
        )

    raise ValueError('time_level must be "monthly", "quarterly", or "annual".')


def build_split_stats(df):
    periods = {
        "2021-2022": [2021, 2022],
        "2023-2025": [2023, 2024, 2025],
    }
    stats = {}

    for branch in EXPECTED_BRANCHES:
        branch_df = df[df["industry_branch"] == branch]
        stats[branch] = {}
        for period_label, years in periods.items():
            period_df = branch_df[branch_df["period"].dt.year.isin(years)]
            stats[branch][period_label] = {
                "mean": period_df["seasonally_adjusted_production"].mean(),
                "std": np.std(period_df["seasonally_adjusted_production"], ddof=0),
            }

    return stats


def to_display_value(value):
    return float(f"{value:.1f}")


def build_summary_lines(df):
    stats = build_split_stats(df)
    summary_lines = [
        "Supporting benchmark summary (monthly source data; 2026 excluded from period comparisons):",
        "",
        "All values are production indexes from CBS dataset 85806NED, where each sector has 2021 = 100.",
        "Sector statistics below show the same period means and Std. Dev. used in the chart box.",
        "",
        "Sector means and volatility:",
    ]

    for branch in EXPECTED_BRANCHES:
        early = stats[branch]["2021-2022"]
        late = stats[branch]["2023-2025"]
        summary_lines.append(
            f"- {DISPLAY_NAMES[branch]}: 2021-2022 mean {to_display_value(early['mean']):.1f}, "
            f"Std. Dev. {to_display_value(early['std']):.1f}; "
            f"2023-2025 mean {to_display_value(late['mean']):.1f}, Std. Dev. {to_display_value(late['std']):.1f}"
        )

    summary_lines.extend(
        [
            "",
            "Pairwise mean gaps:",
            "- Gap values are first sector minus second sector.",
        ]
    )

    comparisons = [
        ("pharma", "chemicals"),
        ("pharma", "total_manufacturing"),
        ("chemicals", "total_manufacturing"),
    ]
    for left_branch, right_branch in comparisons:
        early_gap = to_display_value(
            to_display_value(stats[left_branch]["2021-2022"]["mean"])
            - to_display_value(stats[right_branch]["2021-2022"]["mean"])
        )
        late_gap = to_display_value(
            to_display_value(stats[left_branch]["2023-2025"]["mean"])
            - to_display_value(stats[right_branch]["2023-2025"]["mean"])
        )
        summary_lines.append(
            f"- {DISPLAY_NAMES[left_branch]} - {DISPLAY_NAMES[right_branch]} mean gap: "
            f"2021-2022 {early_gap:+.1f}, 2023-2025 {late_gap:+.1f}, "
            f"change {to_display_value(late_gap - early_gap):+.1f}"
        )

    return summary_lines


def save_text(lines, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_chart_subtitle(time_level):
    labels = {
        "monthly": "Monthly data",
        "quarterly": "Quarterly data",
        "annual": "Annual data",
    }
    if time_level not in labels:
        raise ValueError('TIME_LEVEL must be "monthly", "quarterly", or "annual".')
    return f"{labels[time_level]}; each sector is indexed to its own 2021 average (=100)"


def build_chart_title():
    return CHART_TITLE


def build_split_stats_table(df):
    labels = {
        "pharma": "Pharma",
        "chemicals": "Chemicals",
        "total_manufacturing": "Total manufacturing",
    }
    stats = build_split_stats(df)
    rows = []

    for branch in EXPECTED_BRANCHES:
        early = stats[branch]["2021-2022"]
        late = stats[branch]["2023-2025"]

        rows.append(
            [
                labels[branch],
                f"{early['mean']:>5.1f} | {early['std']:>4.1f}",
                f"{late['mean']:>5.1f} | {late['std']:>4.1f}",
            ]
        )

    return rows


def create_chart(df, path, title, subtitle, stats_source_df, time_level):
    try:
        plt.style.use("seaborn-whitegrid")
    except OSError:
        plt.style.use("default")

    figure_height = 6.8 if time_level in {"quarterly", "annual"} else 6
    fig, ax = plt.subplots(figsize=(10, figure_height))
    ax.grid(True, alpha=0.20, linewidth=0.6)

    for branch in EXPECTED_BRANCHES:
        branch_df = df[df["industry_branch"] == branch].sort_values("period")
        line_width = 3.0 if branch == "pharma" else 2.0
        line_alpha = 1.0 if branch == "pharma" else 0.8
        ax.plot(
            branch_df["period"],
            branch_df["seasonally_adjusted_production"],
            linewidth=line_width,
            color=COLORS[branch],
            alpha=line_alpha,
        )

    ax.axhline(100, color="black", linestyle="--", linewidth=1, alpha=0.7)
    if time_level in {"quarterly", "annual"}:
        # Leave extra headroom so the stats box stays clear of the lines.
        _, y_max = ax.get_ylim()
        ax.set_ylim(top=y_max + 10)
    ax.set_title(title + "\n" + subtitle, fontsize=13)
    ax.set_ylabel("Production index (2021=100)")
    ax.set_xlabel("")

    ax.add_patch(
        plt.Rectangle(
            (0.02, 0.79),
            0.60,
            0.145,
            transform=ax.transAxes,
            facecolor="white",
            edgecolor="none",
            alpha=1.0,
            zorder=2,
        )
    )

    table = ax.table(
        cellText=build_split_stats_table(stats_source_df),
        colLabels=[
            "Sector",
            "  2021-2022\n Mean | Std. Dev.",
            "  2023-2025\n Mean | Std. Dev.",
        ],
        cellLoc="center",
        colLoc="center",
        colWidths=[0.34, 0.29, 0.29],
        bbox=[0.02, 0.80, 0.54, 0.16],
    )
    table.set_zorder(3)
    table.auto_set_font_size(False)
    table.set_fontsize(9)

    for (row, col), cell in table.get_celld().items():
        cell.PAD = 0.008
        cell.set_edgecolor("white")
        cell.set_linewidth(0.0)
        if row == 0:
            cell.set_height(cell.get_height() * 1.35)
            cell.set_facecolor("#f3f3f3")
            cell.get_text().set_weight("bold")
        else:
            cell.set_facecolor("white")
        if col in (1, 2):
            cell.get_text().set_fontfamily("monospace")
            cell.get_text().set_ha("left")

    for row_number, branch in enumerate(EXPECTED_BRANCHES, start=1):
        sector_cell = table[(row_number, 0)]
        sector_cell.get_text().set_color(COLORS[branch])
        sector_cell.get_text().set_weight("bold")
        sector_cell.get_text().set_ha("left")

    fig.text(
        0.01,
        0.01,
        "Source: CBS dataset 85806NED. Chart shows seasonally adjusted production.",
        ha="left",
        fontsize=9,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=300)
    plt.close(fig)


def main():
    args = parse_args()
    time_level = args.time_level or TIME_LEVEL
    should_refresh = REFRESH_DATA if args.refresh_data is None else args.refresh_data

    check_requirements()
    refresh_data(should_refresh)

    df = load_data(INPUT_FILE)
    quality_lines = run_quality_checks(df)
    analysis_df = prepare_analysis_data(df, time_level)
    summary_lines = build_summary_lines(df)

    output_folder = Path(OUTPUT_FOLDER)
    chart_path = output_folder / OUTPUT_CHART
    quality_path = output_folder / "data_quality_report.txt"
    summary_path = output_folder / "analysis_summary.txt"

    create_chart(
        analysis_df,
        chart_path,
        build_chart_title(),
        build_chart_subtitle(time_level),
        df,
        time_level,
    )
    save_text(quality_lines, quality_path)
    save_text(summary_lines, summary_path)

    print("\n".join(quality_lines))
    print()
    print("\n".join(summary_lines))
    print()
    print(f"Chart saved to: {chart_path}")
    print(f"Data quality report saved to: {quality_path}")
    print(f"Summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
