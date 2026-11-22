"""Fetch public hourly ISO New England demand for the city status card."""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


ROUTE = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
SOURCE = "https://www.eia.gov/electricity/930-content/about.html"


def read_grid(key, now):
    query = urlencode({
        "api_key": key,
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": "ISNE",
        "facets[type][]": "D",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 168,
    })
    with urlopen(ROUTE + "?" + query, timeout=20) as response:
        rows = json.load(response)["response"]["data"]

    values = {}
    for row in rows:
        if row["respondent"] != "ISNE" or row["type"] != "D":
            raise ValueError("Unexpected balancing authority or metric")
        if row["value"] is None:
            continue
        # EIA reports MWh per one-hour period, numerically equal to average MW.
        period = datetime.strptime(row["period"], "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
        demand = int(row["value"])
        if demand > 0:
            values[period] = demand

    latest = max(values)
    if now - latest > timedelta(hours=6) or latest - now > timedelta(hours=1):
        raise ValueError("EIA demand period is stale or outside the current UTC hour")
    cutoff = latest - timedelta(hours=167)
    week = [demand for period, demand in values.items() if period >= cutoff]
    if len(week) < 2:
        raise ValueError("Insufficient weekly demand data")
    return {
        "load_mw": values[latest],
        "period_utc": latest.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "week_min_mw": min(week),
        "week_max_mw": max(week),
        "source": SOURCE,
        "fetched_utc": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ.get("EIA_API_KEY")
    if not key:
        print("EIA demand is unavailable because the deployment secret is missing.")
        return
    try:
        data = read_grid(key, datetime.now(timezone.utc))
    except (OSError, ValueError, KeyError, TypeError) as error:
        # Do not include the request URL or API key in workflow output.
        raise SystemExit("Could not read current EIA demand (" + type(error).__name__ + ").") from None
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
