"""
convert_blynk_export.py
=======================
Converts a Blynk historical data export (CSV) into the training format.

Blynk exports one file per datastream. Export three files:
  - temperature.csv  (virtual pin V0)
  - humidity.csv     (virtual pin V1)
  - co2.csv          (virtual pin V2)

Each Blynk CSV has columns:  timestamp, value

Usage:
    python ai/convert_blynk_export.py \
        --temp data/blynk_temp.csv \
        --hum  data/blynk_humidity.csv \
        --co2  data/blynk_co2.csv \
        --out  data/real_training_data.csv

Then retrain:
    python ai/train.py --csv ai/data/real_training_data.csv
"""

import argparse
import pandas as pd
import os

BASE = os.path.dirname(__file__)


def load_blynk(path: str, col_name: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.rename(columns={"value": col_name})
    df[col_name] = pd.to_numeric(df[col_name], errors="coerce")
    return df.set_index("timestamp")


def label(row) -> dict:
    """Rule-based optimal labels — same logic as generate_data.py."""
    temp, humidity, co2 = row["temperature"], row["humidity"], row["co2"]
    window = heater = ac = 0

    if co2 > 800:
        window = 1
    if temp < 18:
        heater = 1
    elif temp > 22:
        if humidity < 40:
            window = 1
        else:
            ac = 1
    if humidity > 60 and not window:
        window = 1 if temp <= 22 else 0
        if not window:
            ac = 1
    if heater and ac:
        ac = 0

    return {"heater": heater, "ac": ac, "window": window}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--temp", required=True)
    parser.add_argument("--hum",  required=True)
    parser.add_argument("--co2",  required=True)
    parser.add_argument("--out",  default=os.path.join(BASE, "data", "real_training_data.csv"))
    args = parser.parse_args()

    temp_df = load_blynk(args.temp, "temperature")
    hum_df  = load_blynk(args.hum,  "humidity")
    co2_df  = load_blynk(args.co2,  "co2")

    # Merge on timestamp with 1-minute tolerance
    merged = temp_df.join(hum_df, how="outer").join(co2_df, how="outer")
    merged = merged.resample("1min").mean().dropna()

    labels_df = merged.apply(label, axis=1, result_type="expand")
    out = pd.concat([merged, labels_df], axis=1)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out.to_csv(args.out)
    print(f"✅  {len(out):,} rows written → {args.out}")


if __name__ == "__main__":
    main()
