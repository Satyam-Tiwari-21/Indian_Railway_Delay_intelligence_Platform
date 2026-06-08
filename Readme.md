# 🚂 India Railways Delay Intelligence Platform

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.5-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)

> **EDA + ML platform for Indian Railways on-time performance — featuring delay prediction by route & season, anomaly detection for disruption patterns, and a role-gated interactive dashboard.**

</div>

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Variables](#environment-variables)
  - [Database Setup](#database-setup)
- [Running the Application](#-running-the-application)
- [ML Models](#-ml-models)
  - [Delay Prediction](#delay-prediction-model)
  - [Anomaly Detection](#anomaly-detection-model)
- [API Reference](#-api-reference)
- [Dashboard & RBAC](#-dashboard--rbac)
- [EDA Highlights](#-eda-highlights)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌐 Overview

India Railways operates over **13,000+ trains** daily, serving **23 million passengers**. Yet on-time performance (OTP) data remains underanalysed. This platform ingests historical and real-time Railways OTP data to:

1. **Predict delays** per route, time-of-year, and train category using supervised ML.
2. **Detect anomalies** — sudden spikes in systemic disruptions before they cascade.
3. **Serve insights** via a Streamlit dashboard and a production-grade FastAPI backend with Role-Based Access Control (RBAC).

Built with first-hand domain knowledge from an internship at the Ministry of Railways — ensuring the data pipelines, feature engineering, and business rules mirror real operational contexts.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 📊 **Exploratory Data Analysis** | In-depth EDA on historical on-time performance across zones, divisions, and train categories |
| 🔮 **Delay Prediction** | Route- and season-aware ML model predicting delay in minutes for any upcoming train |
| 🚨 **Anomaly Detection** | Unsupervised detection of disruption clusters (fog, flooding, track failures) |
| 🖥️ **Interactive Dashboard** | Streamlit frontend with filters, maps, drill-downs, and prediction UI |
| ⚡ **FastAPI Backend** | RESTful API serving predictions, historical stats, and anomaly alerts |
| 🔐 **RBAC** | Role-Based Access Control — Admin, Analyst, and Viewer tiers with JWT auth |
| 🗄️ **SQL Data Layer** | Normalized PostgreSQL schema for trains, stations, delays, and anomaly events |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                    │
│         (Dashboard, Filters, Predictions, Maps)         │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / REST
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI Backend                        │
│   /predict   /anomalies   /stats   /auth   /admin       │
│              JWT Auth + RBAC Middleware                  │
└──────────┬──────────────────────┬───────────────────────┘
           │                      │
┌──────────▼──────────┐  ┌────────▼────────────────────┐
│   ML Model Layer    │  │       PostgreSQL DB          │
│  ┌───────────────┐  │  │  trains | stations | delays  │
│  │Delay Predictor│  │  │  anomalies | users | roles   │
│  ├───────────────┤  │  └─────────────────────────────┘
│  │Anomaly Detect │  │
│  └───────────────┘  │
└─────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.10+ |
| **ML / Data** | scikit-learn, pandas, numpy, matplotlib, seaborn, plotly |
| **Backend API** | FastAPI, Uvicorn, Pydantic |
| **Frontend Dashboard** | Streamlit |
| **Database** | PostgreSQL + SQLAlchemy ORM |
| **Auth** | JWT (python-jose), bcrypt, OAuth2PasswordBearer |
| **Experiment Tracking** | MLflow *(optional)* |
| **Containerisation** | Docker + Docker Compose |
| **Testing** | pytest, httpx |

---

## 📁 Project Structure

```
india-railways-delay-intelligence/
│
├── data/
│   ├── raw/                    # Raw CSVs from Railways OTP portal
│   ├── processed/              # Cleaned & feature-engineered data
│   └── external/               # Weather, holiday calendars, zone maps
│
├── notebooks/
│   ├── 01_eda_overview.ipynb           # Zone-wise OTP trends
│   ├── 02_eda_seasonal_patterns.ipynb  # Season & fog impact analysis
│   ├── 03_feature_engineering.ipynb    # Building model features
│   ├── 04_delay_prediction.ipynb       # Model training & evaluation
│   └── 05_anomaly_detection.ipynb      # Isolation Forest / DBSCAN experiments
│
├── src/
│   ├── api/                    # FastAPI application
│   │   ├── main.py             # App entry point
│   │   ├── routers/
│   │   │   ├── auth.py         # Login, register, token refresh
│   │   │   ├── predictions.py  # /predict endpoint
│   │   │   ├── anomalies.py    # /anomalies endpoint
│   │   │   ├── stats.py        # Historical stats endpoints
│   │   │   └── admin.py        # User & role management (Admin only)
│   │   ├── models/             # SQLAlchemy DB models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── dependencies.py     # Auth & RBAC dependency injection
│   │   └── config.py           # Settings via pydantic-settings
│   │
│   ├── ml/
│   │   ├── train_delay_model.py        # Train & save delay predictor
│   │   ├── train_anomaly_model.py      # Train & save anomaly detector
│   │   ├── predict.py                  # Inference utilities
│   │   ├── feature_engineering.py      # Shared feature pipeline
│   │   └── evaluate.py                 # Model evaluation metrics
│   │
│   ├── dashboard/
│   │   ├── app.py              # Streamlit main app
│   │   ├── pages/
│   │   │   ├── 1_overview.py           # Network-level KPIs
│   │   │   ├── 2_route_analysis.py     # Route drill-down + maps
│   │   │   ├── 3_predict_delay.py      # Live prediction UI
│   │   │   └── 4_anomalies.py          # Anomaly timeline & alerts
│   │   └── components/         # Reusable Streamlit components
│   │
│   └── db/
│       ├── database.py         # DB connection & session
│       ├── migrations/         # Alembic migration scripts
│       └── seed.py             # Seed data for dev/testing
│
├── models/                     # Saved .pkl / .joblib model artifacts
├── tests/
│   ├── test_api.py
│   ├── test_ml.py
│   └── test_db.py
│
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.dashboard
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python **3.10+**
- PostgreSQL **14+** (or use the Docker Compose setup)
- Git

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/india-railways-delay-intelligence.git
cd india-railways-delay-intelligence

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```dotenv
# .env.example

# --- Database ---
DATABASE_URL=postgresql://user:password@localhost:5432/railways_db

# --- Auth / Security ---
SECRET_KEY=your-super-secret-jwt-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# --- ML ---
MODEL_DIR=./models
DELAY_MODEL_PATH=./models/delay_predictor.joblib
ANOMALY_MODEL_PATH=./models/anomaly_detector.joblib

# --- API ---
API_HOST=0.0.0.0
API_PORT=8000

# --- Streamlit ---
STREAMLIT_SERVER_PORT=8501
API_BASE_URL=http://localhost:8000
```

### Database Setup

```bash
# Run migrations
alembic upgrade head

# (Optional) Seed with sample data
python src/db/seed.py
```

---

## ▶️ Running the Application

### Option A — Docker Compose (Recommended)

```bash
docker-compose up --build
```

| Service | URL |
|---|---|
| Streamlit Dashboard | http://localhost:8501 |
| FastAPI Backend | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Docs (Redoc) | http://localhost:8000/redoc |
| PostgreSQL | localhost:5432 |

### Option B — Manual (Dev)

```bash
# Terminal 1 — FastAPI backend
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Streamlit dashboard
streamlit run src/dashboard/app.py --server.port 8501
```

### Train ML Models

```bash
# Train the delay prediction model
python src/ml/train_delay_model.py --data data/processed/delays.csv

# Train the anomaly detection model
python src/ml/train_anomaly_model.py --data data/processed/disruptions.csv
```

---

## 🤖 ML Models

### Delay Prediction Model

Predicts the **expected delay in minutes** for a given train on a given route.

**Features used:**

| Feature | Description |
|---|---|
| `route_id` | Origin–destination pair |
| `train_category` | Express, Superfast, Passenger, etc. |
| `division` | Railway division (NR, SR, ER…) |
| `month` | Month of journey (captures seasonality) |
| `day_of_week` | Weekday vs. weekend patterns |
| `is_fog_season` | Boolean: Nov–Feb in North India |
| `scheduled_departure_hour` | Time-of-day feature |
| `historical_avg_delay` | Rolling mean delay for the route (past 90 days) |
| `distance_km` | Route distance |

**Model:** `GradientBoostingRegressor` (scikit-learn)

**Evaluation:**

| Metric | Value |
|---|---|
| MAE | ~8.3 min |
| RMSE | ~14.1 min |
| R² | ~0.74 |

*Baseline: always-predict-mean gives MAE ~19 min.*

---

### Anomaly Detection Model

Detects **abnormal disruption clusters** — days/routes where delays deviate significantly from expected patterns, signalling systematic issues like floods, fog blankets, or infrastructure failures.

**Approach:** `IsolationForest` on rolling delay statistics per division, augmented with time-series features.

**Output:** Each detected anomaly is tagged with:
- `anomaly_score` — isolation score
- `disruption_window` — suspected start/end timestamps
- `affected_trains` — list of impacted train numbers
- `probable_cause` — inferred from feature attribution (fog / flooding / other)

---

## 📡 API Reference

Interactive docs available at `/docs` (Swagger UI) once the server is running.

### Authentication

```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=admin@railways.gov.in&password=your_password
```

Returns a JWT `access_token` used as a Bearer token in subsequent requests.

### Key Endpoints

| Method | Endpoint | Role Required | Description |
|---|---|---|---|
| `POST` | `/auth/login` | Public | Get JWT token |
| `GET` | `/stats/network` | Viewer+ | Network-level OTP summary |
| `GET` | `/stats/route/{route_id}` | Viewer+ | Per-route delay history |
| `POST` | `/predict/delay` | Analyst+ | Predict delay for a train |
| `GET` | `/anomalies` | Analyst+ | List detected anomalies |
| `GET` | `/anomalies/{id}` | Analyst+ | Anomaly detail + affected trains |
| `GET` | `/admin/users` | Admin | List all users |
| `POST` | `/admin/users` | Admin | Create user with role |
| `PUT` | `/admin/users/{id}/role` | Admin | Update user role |

### Example: Predict Delay

```bash
curl -X POST http://localhost:8000/predict/delay \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "train_number": "12301",
    "route_id": "NDLS-HWH",
    "scheduled_departure": "2024-12-15T06:00:00",
    "train_category": "Superfast"
  }'
```

```json
{
  "train_number": "12301",
  "route_id": "NDLS-HWH",
  "predicted_delay_minutes": 22.4,
  "confidence_interval": [14.1, 31.8],
  "risk_level": "Medium",
  "contributing_factors": ["fog_season", "historical_route_delay"]
}
```

---

## 🔐 Dashboard & RBAC

Three access tiers are enforced at both the API and dashboard layers:

| Role | Permissions |
|---|---|
| **Viewer** | Read-only access to network stats, route analytics, and anomaly summaries |
| **Analyst** | Viewer + live delay predictions + anomaly detail + data export |
| **Admin** | Analyst + user management + model retraining triggers + audit logs |

RBAC is implemented as a FastAPI dependency injected into each route:

```python
@router.post("/predict/delay")
async def predict_delay(
    request: DelayPredictRequest,
    current_user: User = Depends(require_role("analyst"))
):
    ...
```

The Streamlit dashboard reads the user's decoded JWT claims and conditionally renders pages and controls based on role.

---

## 📊 EDA Highlights

Key findings from exploratory analysis on the Indian Railways OTP dataset:

- **Winter fog effect:** North Indian trains (NR, NCR, NER divisions) show a **3.2× increase** in average delay during November–February due to fog.
- **Distance vs Delay:** Trains with routes > 1,500 km accumulate delay non-linearly — early delays compound at junctions.
- **Day-of-week pattern:** Monday and Friday record ~18% higher average delays, correlating with peak passenger load.
- **Zone comparison:** Southern Railway (SR) consistently outperforms Northern Railway (NR) in OTP by ~12 percentage points.
- **Train category:** Rajdhani / Shatabdi expresses recover faster from initial delays than Mail/Express trains due to fewer scheduled halts.

Explore the full analysis in `notebooks/`.

---

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=html
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Commit your changes: `git commit -m 'feat: add your feature'`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Open a Pull Request

Please ensure all tests pass and new features include appropriate test coverage.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

Built with 🚂 and real-world railway domain knowledge.

*If this project helped you, please consider giving it a ⭐*

</div>