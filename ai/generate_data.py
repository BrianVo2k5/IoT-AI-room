"""
generate_data.py
================
Produces synthetic training rows by simulating the virtual room physics
(mirrors the useEffect logic in App.tsx) and labelling each state with
the *optimal* appliance action using nursery-safe thresholds.

Safe nursery ranges used for labelling
---------------------------------------
  Temperature : 18 – 22 °C
  Humidity    : 40 – 60 % RH
  CO₂         : < 800 ppm   (alert above 1000 ppm)

Run:  python ai/generate_data.py
Output: ai/data/training_data.csv
"""

import random
import csv
import os

ROWS = 50_000
OUT_FILE = os.path.join(os.path.dirname(__file__), "data", "training_data.csv")

# ── Nursery comfort thresholds ───────────────────────────────────────────────
TEMP_LOW   = 18.0   # °C  – below this → heater needed
TEMP_HIGH  = 22.0   # °C  – above this → AC needed
HUM_LOW    = 40.0   # %RH – below this → avoid AC / ventilation
HUM_HIGH   = 60.0   # %RH – above this → ventilate or AC
CO2_HIGH   = 800    # ppm – above this → open window
CO2_OK     = 600    # ppm – below this → window not needed for CO₂


def label(temp: float, humidity: float, co2: int) -> tuple[int, int, int]:
    """
    Given a sensor reading return the optimal (heater, ac, window) booleans.

    Priority order when goals conflict:
      1. CO₂ safety   → window open if CO₂ high
      2. Temperature  → heater XOR ac
      3. Humidity     → avoid actions that worsen humidity extremes
    """
    window = 0
    heater = 0
    ac     = 0

    # ── CO₂ rule ─────────────────────────────────────────────────────────────
    if co2 > CO2_HIGH:
        window = 1          # ventilate regardless of other factors

    # ── Temperature rule ─────────────────────────────────────────────────────
    if temp < TEMP_LOW:
        heater = 1
        # opening window while heating is wasteful – override only if CO₂ is
        # dangerously high (already handled above, so don't close it here)
    elif temp > TEMP_HIGH:
        ac = 1
        # if humidity is already low, prefer window over AC (AC dries the air)
        if humidity < HUM_LOW and co2 > CO2_HIGH:
            ac = 0          # window already open, skip AC
        elif humidity < HUM_LOW:
            ac = 0          # temp slightly high but humidity low – do nothing
            # opening window is the gentler option
            window = 1

    # ── Humidity correction ───────────────────────────────────────────────────
    # High humidity: ventilation helps (already covered by window logic above)
    if humidity > HUM_HIGH and not window:
        # prefer window over AC unless temperature is already in range
        if temp <= TEMP_HIGH:
            window = 1
        else:
            ac = 1          # hot + humid → AC is correct

    # ── Sanity: heater and AC shouldn't both be on ────────────────────────────
    if heater and ac:
        ac = 0              # heater takes priority if temp is low

    return heater, ac, window


def simulate_step(temp, humidity, co2, heater, ac, window):
    """One-second physics tick (mirrors App.tsx useEffect)."""
    if heater:
        temp += 0.5
    if ac:
        temp -= 0.5
    if window:
        temp += (20.0 - temp) * 0.05   # ambient pull toward 20 °C

    if heater:
        humidity -= 0.3
    if ac:
        humidity -= 0.2
    if window:
        humidity += 0.4

    if window:
        co2 -= 5
    else:
        co2 += 2

    temp     = max(15.0,  min(35.0,  round(temp,    1)))
    humidity = max(20.0,  min(80.0,  round(humidity, 1)))
    co2      = max(350,   min(1500,  round(co2)))

    return temp, humidity, co2


def main():
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)

    rows = []

    # ── Strategy 1: random independent samples ────────────────────────────────
    for _ in range(ROWS // 2):
        temp     = round(random.uniform(15.0, 35.0), 1)
        humidity = round(random.uniform(20.0, 80.0), 1)
        co2      = random.randint(350, 1500)
        h, a, w  = label(temp, humidity, co2)
        rows.append((temp, humidity, co2, h, a, w))

    # ── Strategy 2: simulate trajectories so the model sees realistic sequences
    for _ in range(ROWS // 2):
        temp     = round(random.uniform(15.0, 35.0), 1)
        humidity = round(random.uniform(20.0, 80.0), 1)
        co2      = random.randint(350, 1500)
        h, a, w  = label(temp, humidity, co2)

        for _ in range(random.randint(5, 30)):
            temp, humidity, co2 = simulate_step(temp, humidity, co2, h, a, w)
            h, a, w = label(temp, humidity, co2)
            rows.append((temp, humidity, co2, h, a, w))

    random.shuffle(rows)

    with open(OUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["temperature", "humidity", "co2", "heater", "ac", "window"])
        writer.writerows(rows)

    print(f"✅  Wrote {len(rows):,} rows → {OUT_FILE}")


if __name__ == "__main__":
    main()
