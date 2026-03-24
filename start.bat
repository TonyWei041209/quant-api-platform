@echo off
title Quant API Platform
color 0A

echo ============================================
echo   Quant API Platform - Quick Launcher
echo ============================================
echo.

cd /d "%~dp0"

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11+
    pause
    exit /b 1
)

:: Check .env
if not exist ".env" (
    echo [INFO] .env not found, copying from .env.example ...
    copy .env.example .env >nul
    echo [INFO] .env created. Edit it to add your API keys.
    echo.
)

:: Check PostgreSQL is running
echo [1/5] Checking PostgreSQL ...
python -c "from libs.db.session import get_sync_engine; e=get_sync_engine(); c=e.connect(); c.close(); print('  PostgreSQL OK')" 2>nul
if %errorlevel% neq 0 (
    echo   PostgreSQL not reachable. Attempting to start via pg_ctl ...
    net start postgresql-x64-16 >nul 2>&1
    timeout /t 3 /nobreak >nul
    python -c "from libs.db.session import get_sync_engine; e=get_sync_engine(); c=e.connect(); c.close(); print('  PostgreSQL OK')" 2>nul
    if %errorlevel% neq 0 (
        echo   [ERROR] Cannot connect to PostgreSQL.
        echo   Make sure PostgreSQL 16 is running on localhost:5432
        echo   with user=quant password=quant_dev_password db=quant_platform
        pause
        exit /b 1
    )
)

:: Run migrations
echo [2/5] Running database migrations ...
python -m alembic -c infra/alembic.ini upgrade head 2>nul
if %errorlevel% neq 0 (
    echo   [WARN] Migration failed - database may already be up to date
) else (
    echo   Migrations applied.
)

:: Check if instruments exist
echo [3/5] Checking data ...
python -c "from libs.db.session import get_sync_engine; from sqlalchemy import text; e=get_sync_engine(); c=e.connect(); r=c.execute(text('SELECT COUNT(*) FROM instrument')).scalar(); c.close(); print(f'  {r} instruments in database')"
echo.

:: Run DQ
echo [4/5] Running data quality checks ...
python -m apps.cli.main run-dq 2>nul
echo.

:: Start API server
echo [5/5] Starting API server on http://localhost:8000 ...
echo.
echo ============================================
echo   API is running at http://localhost:8000
echo   Docs at http://localhost:8000/docs
echo   Press Ctrl+C to stop
echo ============================================
echo.

python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload

pause
