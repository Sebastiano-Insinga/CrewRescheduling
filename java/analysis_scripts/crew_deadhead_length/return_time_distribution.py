#!/usr/bin/env python3
import argparse
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import distribution_report as report

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_DEFAULT = os.path.join(os.path.dirname(ROOT), "manuel_chain", "crew_deadhead_length")

CLASSES = [
    ("zero", 0.0),
    ("<=30", 30.0),
    ("30-60", 60.0),
    ("60-90", 90.0),
    ("90-120", 120.0),
    ("120-180", 180.0),
    ("180-240", 240.0),
    (">240", float("inf")),
]
MISSING_CLASS = "missing"
MISSING_STATUSES = {"missing", "mapping_error"}
EPS = 1e-9

LABELS = [label for label, _ in CLASSES] + [MISSING_CLASS]

LEGEND_LABELS = {
    "zero": "0 min (duty ends where it started)",
    "<=30": "0-30 min",
    "30-60": "30-60 min",
    "60-90": "60-90 min",
    "90-120": "90-120 min",
    "120-180": "120-180 min",
    "180-240": "180-240 min",
    ">240": "> 240 min",
    MISSING_CLASS: "no distance available",
}


def class_of(time_minutes, status):
    if status in MISSING_STATUSES or pd.isna(time_minutes):
        return MISSING_CLASS
    for label, upper in CLASSES:
        if time_minutes <= upper + EPS:
            return label
    return CLASSES[-1][0]


def read_instance(path):
    df = pd.read_csv(path, dtype=str).fillna("")
    df["time_minutes"] = pd.to_numeric(df["time_minutes"], errors="coerce")
    df["class"] = [class_of(t, s) for t, s in zip(df["time_minutes"], df["status"])]
    return df


def check_zero(name, df):
    same_station = df["start_station"] == df["end_station"]
    zero_time = df["time_minutes"] == 0.0
    mismatched = df[same_station != zero_time]
    mismatched = mismatched[~mismatched["status"].isin(MISSING_STATUSES)]
    if not mismatched.empty:
        print(f"[warning] {name}: {len(mismatched)} duties where "
              f"'start_station == end_station' and 'time == 0' disagree: "
              f"{', '.join(mismatched['duty_id'].head(5))}")


def summary_row(name, df):
    times = df["time_minutes"].dropna()
    return {
        "instance": name,
        "duties": len(df),
        "min": round(times.min(), 2) if not times.empty else None,
        "median": round(times.median(), 2) if not times.empty else None,
        "mean": round(times.mean(), 2) if not times.empty else None,
        "max": round(times.max(), 2) if not times.empty else None,
        "missing": int(df["class"].eq(MISSING_CLASS).sum()),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Frequency tables and chart of the crew return travel times.")
    parser.add_argument("-input", default=INPUT_DEFAULT,
                        help="folder holding one csv per instance")
    parser.add_argument("-output", default=None,
                        help="output folder (default: <input>/analysis)")
    args = parser.parse_args()

    out_dir = args.output or os.path.join(args.input, "analysis")
    os.makedirs(out_dir, exist_ok=True)

    csv_files = sorted(glob.glob(os.path.join(args.input, "*.csv")))
    if not csv_files:
        sys.exit(f"no csv in {args.input}")

    report.write_report(
        csv_files, out_dir, LABELS, LEGEND_LABELS, read_instance, summary_row,
        xlsx_name="crew_return_trip.xlsx",
        chart_name="return_time_by_instance",
        chart_title="Crew return trip from end-of-duty station to start-of-duty station",
        legend_title="Return travel time",
        table_title="Crew return trip: share of duties per travel time class",
        per_instance_check=check_zero,
        table_drop_columns=(MISSING_CLASS,),
        strip_from_header=" (duty ends where it started)",
        colormap="YlOrRd",
        last_class_grey=True)


if __name__ == "__main__":
    main()
