# 🌊 Wave-Safe

> **A Unified Platform for Smarter Coastal Travel and Safety**

Wave-Safe is a unified web-based coastal safety and intelligence platform that combines real-time ocean and weather intelligence, trip planning, emergency coordination, and rescue tracking into one coastal travel experience.

<div align="center">
  <br />
  <p><b>🎬 Project Walkthrough & Demo (1 Minute)</b></p>
  <a href="https://youtu.be/AKZOnFFqXSo" target="_blank">
    <img src="https://img.youtube.com/vi/AKZOnFFqXSo/maxresdefault.jpg" alt="Demo Video" width="80%" style="border-radius: 8px;" />
  </a>
  <p><i>👆 Click image to watch the full 1-minute demo video!</i></p>
</div>

## 👥 Team

**Team Name:** LazyCoders

- **Arvind Kumar** — Team Leader
- **Om Kushwaha**
- **Rishabh Pal**

---

## 🚨 Problem Statement

India has over **7,500 km of coastline**, but there is no unified digital platform that provides tourists with real-time beach safety intelligence and coordinated emergency response.

### Current Challenges

- No simple real-time **Safe / Caution / Unsafe** signal for beaches.
- Visitors may lack current information about ocean conditions, rip-current risks, and official hazard advisories.
- Emergency assistance can depend on a chain of separate phone calls.
- Hospitals, lifeguards, police, coast guard, rescue posts, and jurisdictions operate through disconnected records.
- There is no single system to automatically identify and coordinate the appropriate responder for an incident.
- Existing ocean and weather data is available, but it is not converted into one simple decision for a beach visitor.

---

## 💡 Solution

**Wave-Safe** bridges the gap between **real-time risk awareness and emergency response**.

The platform is designed as a travel website first, with safety intelligence integrated throughout the user's journey.

### Predict → Plan → Protect → Track

- **Predict:** Calculate a live beach safety verdict from ocean and weather data.
- **Plan:** Identify risky travel windows and suggest safer alternatives.
- **Protect:** Provide one-tap SOS with location sharing and coordinated emergency dispatch.
- **Track:** Provide live rescue tracking, acknowledgements, and ETAs.

---

## ✨ Features

### 🟢 Live Beach Safety

Provides a live:

- **SAFE**
- **CAUTION**
- **UNSAFE**

verdict for beaches using real ocean and weather data.

### 🗓️ Smart Trip Planning

- Evaluates risk across planned time windows.
- Flags potentially dangerous slots.
- Suggests safer alternative beaches.

### 🆘 One-Tap SOS

A single SOS trigger can share the user's exact location with:

- 112 / emergency response
- Nearest hospital
- Coast guard / marine police
- Lifeguard post

### 🚑 Emergency Dispatch & Tracking

Tracks an incident through:

```text
Created → Dispatched → Acknowledged → En Route → Arrived → Resolved
```

### 🗺️ Hospital & Authority Routing

- Capability-filtered hospital matching.
- Jurisdiction-matched authority routing.
- Defined response roles.
- Parallel emergency dispatch.

### 📍 Live Rescue Tracking

- Location pings.
- ETA tracking.
- Stale-session detection.
- Rescue progress visibility.

### 🔔 Notifications

- SMS notifications.
- Web Push notifications.
- Localized templates.
- English fallback.

### 📴 Offline Support

- Offline-capable Progressive Web App.
- Local action queue.
- Automatic synchronization after reconnect.

### 🔐 Authentication

- Phone + OTP login.
- Defined OTP expiry.

### 🏢 Admin & Operations

- Beach management.
- Jurisdiction management.
- Hospital management.
- Incident dashboards.
- Acknowledgement dashboards.
- Risk-rule tuning.
- Log export.

### 🌊 Data Ingestion & Risk Engine

- INCOIS + SACHET connectors.
- Manual beach closures.
- Data normalization and unit conversion.
- Redis-based deduplication.
- Risk scoring.
- Time-series hazard outlook.

---

## 🧠 Risk Engine

The Risk Engine combines multiple inputs into an explainable risk score.

### Inputs

- Wave height
- Current speed
- Wind
- Tide
- Water quality
- Forecast trend
- Lifeguard coverage

### Risk Formula

```text
R = σ( Σ wᵢzᵢ + Σ wᵢⱼzᵢzⱼ + λ₁Δtrend + λ₂Δtide )
```

### Risk Classification

| Risk Score | Verdict |
|---:|---|
| `R < 0.33` | 🟢 SAFE |
| `0.33 – 0.66` | 🟡 CAUTION |
| `R ≥ 0.66` | 🔴 UNSAFE |

Active **tsunami, storm surge, or evacuation** conditions override normal scoring and force:

```text
R = 1 → UNSAFE
```

---

## 🛠️ Tech Stack

### Frontend

- **React**
- **Next.js (SSR)**
- **Mapbox GL JS / Google Maps API**
- **Progressive Web App (PWA)**

### Backend

- **Python**
- **FastAPI**
- **REST APIs**
- **WebSockets**
- **Celery**

### Database & Storage

- **PostgreSQL 16**
- **PostGIS**
- **Redis 7**
- **S3-compatible object storage**

### Infrastructure & DevOps

- **Docker**
- **Kubernetes**
- **Kafka / RabbitMQ**
- **GitHub Actions CI/CD**
- **AWS / GCP**

### External APIs & Data Sources

- **INCOIS** — Ocean & advisory data
- **SACHET** — CAP / RSS alerts
- **112 ERSS** — Emergency dispatch integration
- **Google Maps / Places API**
- **Firebase Cloud Messaging**
- **Twilio SMS**

---

## 🏗️ System Architecture

```text
Client Layer
Next.js / Web / Offline PWA
          │
          ▼
API Gateway
FastAPI REST + Internal Routing
          │
          ▼
Application Layer
SOS │ Trip │ Safezone │ Notifications
          │
          ▼
Domain Engines
Risk Scoring │ Forecasts │ Data Ingestion
          │
          ▼
Async Workers
Celery
          │
     ┌────┴────┐
     ▼         ▼
PostgreSQL   Redis
+ PostGIS    Cache/Broker
     │
     ▼
External Systems
INCOIS │ SACHET │ Maps │ SMS │ Push │ Emergency APIs
```

---

## ⚙️ Setup Instructions

> The provided project document specifies the technology stack and architecture, but it does **not** provide repository-specific commands, environment-variable names, database migrations, or exact source-tree structure. Therefore, the setup below is a standard development setup based on the documented stack rather than a claim about commands already implemented in the repository.

### 1. Prerequisites

Install:

- Node.js
- Python 3
- PostgreSQL 16
- PostGIS
- Redis 7
- Docker
- Git

For the complete infrastructure, Docker/Kubernetes and a queue such as Kafka or RabbitMQ may also be used.

### 2. Clone the Repository

```bash
git clone <repository-url>
cd <project-directory>
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend is based on **React / Next.js** and is designed to support PWA/offline functionality.

### 4. Backend Setup

Create and activate a Python virtual environment:

```bash
cd backend

python -m venv venv
```

**Windows:**

```bash
venv\Scripts\activate
```

**Linux/macOS:**

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the FastAPI application:

```bash
uvicorn main:app --reload
```

> Adjust the entry-point path if the repository uses a different FastAPI application module.

### 5. Database Setup

Create a PostgreSQL database with **PostGIS** enabled.

Example:

```sql
CREATE DATABASE wavesafe;
```

Then enable PostGIS:

```sql
CREATE EXTENSION postgis;
```

Configure the backend with the appropriate database connection string.

### 6. Redis

Start Redis locally:

```bash
redis-server
```

Redis is used for caching, pub/sub, and asynchronous task infrastructure.

### 7. Environment Variables

Create a `.env` file for environment-specific configuration.

Typical configuration areas include:

```env
DATABASE_URL=
REDIS_URL=

MAPS_API_KEY=

INCOIS_API_URL=
SACHET_API_URL=

TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=

FIREBASE_CONFIG=

JWT_SECRET=
```

> Exact variable names and credentials should match the implementation and service-provider configuration used by the project.

### 8. Run with Docker

If Docker configuration is provided in the repository:

```bash
docker compose up --build
```

This can be used to run the application's supporting services together.

---

## 🔄 Application Flow

```text
Ocean / Weather / Advisory Data
              │
              ▼
       Data Ingestion
              │
              ▼
    Normalization & Deduplication
              │
              ▼
       Risk Engine
              │
       ┌──────┴──────┐
       ▼             ▼
Beach Safety      Trip Planning
Verdict           Risk Windows
       │
       ▼
    User / PWA
       │
    Emergency?
       │
       ▼
    One-Tap SOS
       │
 ┌─────┼──────────┐
 ▼     ▼          ▼
112  Hospital   Lifeguard
 │     │          │
 └─────┼──────────┘
       ▼
Live Rescue Tracking
       │
       ▼
    Resolved
```

---

## 📌 Project Scope

Wave-Safe focuses on:

1. Real-time coastal risk awareness.
2. Safer travel planning.
3. Unified emergency coordination.
4. Geospatial hospital and authority routing.
5. Live rescue tracking.
6. Offline-capable coastal travel access.

---

## 🚀 Future Rollout

The proposed rollout follows a phased approach:

```text
Single Coast / State Pilot
          ↓
State-Wide Rollout
          ↓
Pan-India Expansion
          ↓
Government Integration
```

---

## 💼 Business Model

### B2G

Licensing for:

- State tourism boards
- Disaster-management authorities

### B2C

Freemium model with:

- Free safety verdicts
- Premium trip alerts
- Family tracking

### B2B

Partnerships with:

- Hospitals
- Insurers
- Travel platforms

---

## 🎯 Vision

> **Know the risk. Plan the trip. Trigger the response. Track the rescue.**

Wave-Safe aims to turn fragmented coastal safety, travel, ocean, weather, and emergency information into one simple and actionable platform.

---

## 👥 Team LazyCoders

**Built by LazyCoders**

- Arvind Kumar
- Om Kushwaha
- Rishabh Pal
