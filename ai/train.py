"""
train.py
========
Trains a small neural network on the generated (or real) CSV data.

Uses PyTorch with the MPS backend so training runs on the M1 Max GPU cores.
Also trains a Random Forest baseline for comparison.

Run:
    python ai/train.py                  # uses ai/data/training_data.csv
    python ai/train.py --csv path/to/real_data.csv   # retrain on Blynk export

Outputs:
    ai/model/nursery_nn.pt          – PyTorch state dict
    ai/model/scaler.joblib          – input StandardScaler
    ai/model/label_names.json       – output label order  ["heater","ac","window"]
    ai/model/rf_baseline.joblib     – Random Forest baseline
"""

import argparse
import json
import os
import time

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputClassifier
from sklearn.preprocessing import StandardScaler

# ── Paths ────────────────────────────────────────────────────────────────────
BASE      = os.path.dirname(__file__)
DATA_FILE = os.path.join(BASE, "data", "training_data.csv")
MODEL_DIR = os.path.join(BASE, "model")

FEATURES = ["temperature", "humidity", "co2"]
LABELS   = ["heater", "ac", "window"]


# ── Neural Network ────────────────────────────────────────────────────────────
class NurseryNet(nn.Module):
    """
    Simple 3-layer MLP.
    Input  : 3 normalised sensor readings
    Output : 3 independent sigmoid logits (one per appliance)
    """
    def __init__(self, hidden=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(3, hidden),
            nn.ReLU(),
            nn.BatchNorm1d(hidden),
            nn.Dropout(0.2),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.BatchNorm1d(hidden),
            nn.Dropout(0.2),
            nn.Linear(hidden, 3),
        )

    def forward(self, x):
        return self.net(x)          # raw logits; BCEWithLogitsLoss handles sigmoid


def train_nn(X_train, y_train, X_val, y_val, device, epochs=40, batch=512, lr=1e-3):
    model = NurseryNet(hidden=64).to(device)
    opt   = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    loss_fn = nn.BCEWithLogitsLoss()

    X_tr = torch.tensor(X_train, dtype=torch.float32).to(device)
    y_tr = torch.tensor(y_train, dtype=torch.float32).to(device)
    X_vl = torch.tensor(X_val,   dtype=torch.float32).to(device)
    y_vl = torch.tensor(y_val,   dtype=torch.float32).to(device)

    dataset = torch.utils.data.TensorDataset(X_tr, y_tr)
    loader  = torch.utils.data.DataLoader(dataset, batch_size=batch, shuffle=True)

    best_val_loss = float("inf")
    best_state    = None

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        for xb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
            epoch_loss += loss.item() * len(xb)

        sched.step()

        model.eval()
        with torch.no_grad():
            val_loss = loss_fn(model(X_vl), y_vl).item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.cpu() for k, v in model.state_dict().items()}

        if epoch % 5 == 0:
            print(f"  epoch {epoch:3d}/{epochs}  train={epoch_loss/len(X_train):.4f}  val={val_loss:.4f}")

    model.load_state_dict(best_state)
    return model


def evaluate_nn(model, X_test, y_test, device):
    model.eval()
    X = torch.tensor(X_test, dtype=torch.float32).to(device)
    with torch.no_grad():
        logits = model(X).cpu().numpy()
    preds = (logits > 0.0).astype(int)
    print("\n── Neural Network test report ──────────────────────────────")
    print(classification_report(y_test, preds, target_names=LABELS, zero_division=0))
    return preds


def main(csv_path: str):
    os.makedirs(MODEL_DIR, exist_ok=True)

    # ── Select device ────────────────────────────────────────────────────────
    if torch.backends.mps.is_available():
        device = torch.device("mps")
        print("🟢  Using Apple MPS (M1 Max GPU)")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
        print("🟢  Using CUDA GPU")
    else:
        device = torch.device("cpu")
        print("🟡  Using CPU (MPS not available)")

    # ── Load data ────────────────────────────────────────────────────────────
    print(f"\nLoading data from {csv_path} …")
    df = pd.read_csv(csv_path)
    print(f"  {len(df):,} rows, columns: {list(df.columns)}")

    X = df[FEATURES].values.astype(np.float32)
    y = df[LABELS].values.astype(np.float32)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
    X_train, X_val,  y_train, y_val  = train_test_split(X_train, y_train, test_size=0.12, random_state=42)

    # ── Scale ────────────────────────────────────────────────────────────────
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val   = scaler.transform(X_val)
    X_test  = scaler.transform(X_test)

    joblib.dump(scaler, os.path.join(MODEL_DIR, "scaler.joblib"))
    print("  Scaler saved.")

    # ── Random Forest baseline ────────────────────────────────────────────────
    print("\nTraining Random Forest baseline …")
    t0 = time.time()
    rf = MultiOutputClassifier(
        RandomForestClassifier(n_estimators=200, max_depth=12, n_jobs=-1, random_state=42)
    )
    rf.fit(X_train, y_train)
    rf_preds = rf.predict(X_test)
    print(f"  Done in {time.time()-t0:.1f}s")
    print("\n── Random Forest test report ───────────────────────────────")
    print(classification_report(y_test, rf_preds, target_names=LABELS, zero_division=0))
    joblib.dump(rf, os.path.join(MODEL_DIR, "rf_baseline.joblib"))

    # ── Neural Network ────────────────────────────────────────────────────────
    print("\nTraining Neural Network …")
    t0 = time.time()
    model = train_nn(X_train, y_train, X_val, y_val, device)
    print(f"  Done in {time.time()-t0:.1f}s")

    evaluate_nn(model, X_test, y_test, device)

    # Save model to CPU state dict so it can be loaded anywhere
    torch.save(model.state_dict(), os.path.join(MODEL_DIR, "nursery_nn.pt"))
    json.dump(LABELS, open(os.path.join(MODEL_DIR, "label_names.json"), "w"))

    print("\n✅  All models saved to", MODEL_DIR)
    print("   nursery_nn.pt  |  scaler.joblib  |  rf_baseline.joblib")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=DATA_FILE)
    args = parser.parse_args()
    main(args.csv)
