"""
predict_server.py
=================
Tiny FastAPI server — React app calls this every second to get AI decisions.

Run:
    uvicorn ai.predict_server:app --port 8000 --reload

Then the React app fetches:
    POST http://localhost:8000/predict
    Body: { "temperature": 24.5, "humidity": 38.0, "co2": 950 }

Response:
    { "heater": false, "ac": true, "window": true,
      "confidence": { "heater": 0.02, "ac": 0.97, "window": 0.88 } }
"""

import json
import os

import joblib
import numpy as np
import torch
import torch.nn as nn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Paths ────────────────────────────────────────────────────────────────────
BASE      = os.path.dirname(__file__)
MODEL_DIR = os.path.join(BASE, "model")


# ── Load model (same architecture as train.py) ────────────────────────────────
class NurseryNet(nn.Module):
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
        return self.net(x)


scaler      = joblib.load(os.path.join(MODEL_DIR, "scaler.joblib"))
label_names = json.load(open(os.path.join(MODEL_DIR, "label_names.json")))

model = NurseryNet()
model.load_state_dict(torch.load(os.path.join(MODEL_DIR, "nursery_nn.pt"), map_location="cpu"))
model.eval()

app = FastAPI(title="Nursery AI", version="1.0")

# Allow the Vite dev server (localhost:5173) to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SensorReading(BaseModel):
    temperature: float
    humidity: float
    co2: float


@app.post("/predict")
def predict(reading: SensorReading):
    x = np.array([[reading.temperature, reading.humidity, reading.co2]], dtype=np.float32)
    x_scaled = scaler.transform(x)
    x_tensor = torch.tensor(x_scaled, dtype=torch.float32)

    with torch.no_grad():
        logits = model(x_tensor)
        probs  = torch.sigmoid(logits).numpy()[0]

    decisions = {name: bool(prob > 0.5) for name, prob in zip(label_names, probs)}
    confidence = {name: round(float(prob), 3) for name, prob in zip(label_names, probs)}

    return {**decisions, "confidence": confidence}


@app.get("/health")
def health():
    return {"status": "ok", "model": "nursery_nn.pt"}
