# HARIKA System Architecture

## Core Architectural Design

HARIKA is architected as a modular, high-performance monorepo separated into a **React + TypeScript + Vite frontend** presentation layer and a **Python FastAPI backend** orchestration layer.

```
+-------------------------------------------------------------+
|                      HARIKA FRONTEND                        |
|  React 19 / TypeScript / Vite / Tailwind CSS / Zustand / Axios |
+-------------------------------------------------------------+
                              |
                     REST APIs / WebSockets
                              |
+-------------------------------------------------------------+
|                      HARIKA BACKEND                         |
|      FastAPI / Pydantic v2 / Uvicorn / Async Services        |
+-------------------------------------------------------------+
```

### Frontend Architecture
- **Framework**: Vite + React + TypeScript
- **State Management**: Zustand (Global state, UI state, system telemetry)
- **Networking**: Axios instance with centralized interceptors & error handlers
- **Routing**: React Router v7 with lazy loading and layout wrappers
- **Styling**: Tailwind CSS with dark futuristic design token variables

### Backend Architecture
- **Framework**: FastAPI (Asynchronous Python)
- **Validation**: Pydantic v2 schemas
- **Configuration**: Pydantic-Settings (`.env` validation)
- **API Versioning**: `app/api/v1` router structure
