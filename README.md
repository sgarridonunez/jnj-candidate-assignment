# J&J Candidate Assignment for Sr. Associate Scientist position in MSAT Leiden Process Analytics Team

This project analyzes the question: **Has pharmaceutical manufacturing pulled away from chemicals since 2023, or is it simply following broader manufacturing conditions?**

I chose a manufacturing dataset because the role is in MSAT Process Analytics, so the analysis stays close to production performance and stability. Pharmaceuticals are compared against chemicals and total manufacturing because chemicals is a close process-industry peer, while total manufacturing provides broader context. This also connects to concerns around pharmaceutical supply-chain resilience and raw materials highlighted by the European Commission ([link](https://health.ec.europa.eu/medicinal-products/legal-framework-governing-medicinal-products-human-use-eu/pharmaceutical-strategy-europe/structured-dialogue-security-medicines-supply_en)). I use monthly seasonally adjusted production index data to preserve visibility of volatility, keep 2021 as the reference year because CBS defines each sector’s average 2021 production level as 100, and use 2023 as a breaking point because exploratory analysis identified a persistent divergence from that point onward. This timing is consistent with CBS reporting that Dutch industry weakened after 2022, with chemicals especially affected by weaker demand and high energy costs ([link](https://www.cbs.nl/nl-nl/longread/de-nederlandse-economie/2025/de-nederlandse-industrie-vanaf-2022/3-industrie-in-een-kwakkelende-economie-2022-2024)). The main insight is that pharma stayed mostly above its 2021 average while chemicals moved into sustained underperformance. The average pharma-chemicals gap widened from `+7.3` to `+26.2` index points; pharma remained highly volatile (`SD 12.6`), while chemicals became less volatile (`SD 4.6` to `3.1`). The takeaway is that benchmarking should track both production level and stability, because stronger average performance can still come with less stable month-to-month behavior.
## Quick Start (TLDR)

```bash
python3 -m pip install -r requirements.txt

# Fastest way to reproduce the exact delivered output
python3 main.py --no-refresh-data

# Optional: refresh directly from CBS and regenerate
python3 main.py --refresh-data
```

`--no-refresh-data` reproduces the result from the included CSV; `--refresh-data` re-downloads the source data from CBS and rebuilds the outputs.

## Files

- `cbs_manufacturing_download.py`: pulls the selected monthly CBS series from the OData API for pharmaceuticals, chemicals, and total manufacturing, then writes them to a local CSV
- `main.py`: main entry point that optionally refreshes the download, runs simple data-quality checks, aggregates to monthly, quarterly, or annual views, and creates the final plot and text outputs
- `cbs_manufacturing_monthly.csv`: the local monthly dataset produced by the downloader and used as the input for the analysis script
- `requirements.txt`: lists the Python packages needed to run the downloader and analysis workflow.

## Environment Setup

Use Python 3 and install the required analysis packages:

```bash
python3 -m pip install -r requirements.txt
```

When `main.py` starts, it checks whether the required packages are installed and exits with a clear install message if something is missing.

## How To Run

You can run the workflow in two reproducible ways.

Option 1: reproduce the delivered result from the included CSV

```bash
python3 main.py --no-refresh-data
```

This reuses `cbs_manufacturing_monthly.csv`, runs the data-quality checks, runs analysis, and saves the text outputs.

Option 2: refresh the source data from CBS and rebuild everything

```bash
python3 main.py --refresh-data
```

This downloads a fresh monthly CSV from the CBS OData API first, then runs the same analysis workflow.

You can choose the plot frequency in two ways.

Option 1: edit the file directly

```python
START_YEAR = 2021
REFRESH_DATA = True
TIME_LEVEL = "monthly"
```

Option 2: override from the command line

```bash
python3 "main.py" --time-level monthly
python3 "main.py" --time-level quarterly
python3 "main.py" --time-level annual
```

Supported `TIME_LEVEL` values are:

- `monthly` (default)
- `quarterly`
- `annual`

The data is always downloaded monthly first. Quarterly and annual views are simple averages aggregated from the monthly data inside `main.py`.

The simple data-quality checks include:

- expected branch coverage
- duplicate branch/period checks
- missing-value checks for the selected metrics
- monthly continuity checks on the downloaded data

## Data Source

The data comes from the CBS StatLine open data dataset `85806NED`:

- Dataset page: https://opendata.cbs.nl/#/CBS/nl/dataset/85806NED/table
- API base: `https://opendata.cbs.nl/ODataApi/OData/85806NED`

The code accesses the CBS OData API through `cbs_manufacturing_download.py`, downloads the monthly data for:

- pharmaceuticals
- chemicals
- total manufacturing

and saves the results to `cbs_manufacturing_monthly.csv`. The analysis then reads that monthly file and optionally aggregates it to quarterly or annual frequency inside `main.py`.

The downloaded dataset includes three production-related measures:

- `seasonally_adjusted_production`
- `calendar_corrected_production_change_year_on_year`
- `previous_period_seasonally_adjusted_production_change`

The main analysis uses `seasonally_adjusted_production`, because it is the most suitable series for benchmarking sector performance over time while preserving visibility of month-to-month volatility. The other two variables were downloaded as supporting measures, but the final slide stays focused on the seasonally adjusted production index for clarity.

## Outputs

After running `main.py`, the main outputs are saved in `outputs/`:

- `pharma_vs_benchmarks.png` - the plot used for the presentation
- `data_quality_report.txt` - a short data-check report covering branch coverage, duplicates, missing values, and monthly continuity in the downloaded data
- `analysis_summary.txt` - a short factual summary with reporting frequency plus start, latest, change, and average YoY values for each sector
