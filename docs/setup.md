# Setup & Environment Guide

## Prerequisites

- **OS:** Windows 10/11 or Windows Server.
- **Python:** 3.11+ (64-bit).
- **Node.js:** v20+ (Node.js v24+ supported).
- **ODBC Driver:** Microsoft ODBC Driver 18 for SQL Server.
- **SQL Server:** Microsoft SQL Server 2017+ (Local default instance: `MSSQLSERVER`).

---

## Backend Setup

1. **Create and Activate Virtual Environment:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install Dependencies:**
   ```powershell
   python -m pip install -r backend\requirements.txt
   ```

3. **Configure Environment Variables:**
   Copy `backend/.env.example` to `backend/.env`:
   ```powershell
   copy backend\.env.example backend\.env
   ```

   **Key Settings in `.env`:**
   - `SQL_SERVER`: SQL Server host or instance name (default: `localhost`).
   - `SQL_DATABASE`: Target database name (default: `master`).
   - `SQL_DRIVER`: Must be `ODBC Driver 18 for SQL Server`.
   - `SQL_TRUSTED_CONNECTION`: Set to `true` for Windows Authentication.
   - `SQL_ENCRYPT`: Set to `true` (ODBC 18 standard).
   - `SQL_TRUST_SERVER_CERTIFICATE`: Defaults to `false`. For local development against an instance without a signed enterprise CA certificate, set to `true`.
   - `SQLITE_DB_PATH`: Path to SQLite metadata database (default: `data/metadata.db`).
   - `SQLITE_BUSY_TIMEOUT_MS`: SQLite busy timeout in milliseconds (default: `30000`).

---

## Running the Application

### 1. Start the Backend API
From the repository root:
```powershell
cd backend
..\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```
API Swagger documentation is accessible at `http://127.0.0.1:8000/docs`.

### 2. Start the Background Export Worker
In a separate PowerShell terminal:
```powershell
cd backend
..\.venv\Scripts\python.exe -m app.workers.export_worker --interval 2.0
```

### 3. Start the Frontend React Portal
In a third PowerShell terminal:
```powershell
cd frontend
npm run dev
```
Open `http://localhost:5173` in your browser. All API requests are proxied automatically to the FastAPI backend at port 8000.

---

## Running Tests

### Unit Tests Only (Does not require SQL Server to be running)
```powershell
cd backend
..\.venv\Scripts\pytest.exe -m "not integration" -v
```

### Full Test Suite (Including Live SQL Server Integration)
Ensure `MSSQLSERVER` service is running first:
```powershell
Start-Service MSSQLSERVER
cd backend
..\.venv\Scripts\pytest.exe -v
```

