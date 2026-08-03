# HARIKA — Futuristic AI Operating System

HARIKA is a futuristic AI Operating System featuring a cinematic 3D AI Core and modular app ecosystem.

## Architecture Overview

```
HARIKA/
├── backend/            # Python FastAPI backend server
│   ├── app/
│   │   ├── api/        # Versioned API routes (v1)
│   │   ├── core/       # App configuration & logging
│   │   ├── schemas/    # Pydantic data schemas
│   │   ├── services/   # Business logic modules
│   │   └── main.py     # FastAPI application entrypoint
│   ├── .env.example
│   └── requirements.txt
├── frontend/           # React + TypeScript + Vite frontend UI
│   ├── src/
│   │   ├── app/        # React Router setup & providers
│   │   ├── components/ # Reusable UI & layout components
│   │   ├── config/     # Environment configuration
│   │   ├── features/   # Feature-based application modules
│   │   ├── services/   # Axios API client & endpoints
│   │   ├── store/      # Zustand global state slices
│   │   └── types/      # TypeScript interfaces
│   ├── .env.example
│   └── package.json
└── docs/               # Project documentation & specs
```

## Quick Start

### 1. Backend Setup (FastAPI)

```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

FastAPI server runs at `http://localhost:8000`.  
Swagger API Documentation: `http://localhost:8000/docs`

### 2. Frontend Setup (React + Vite)

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Vite Dev Server runs at `http://localhost:5173`.
