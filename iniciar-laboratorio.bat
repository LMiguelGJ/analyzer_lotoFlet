@echo off
setlocal
set "EXIT_CODE=1"
pushd "%~dp0"
if errorlevel 1 (
    echo No se pudo abrir la carpeta del laboratorio. Revisa la ruta y los permisos.
    goto finish
)

set "PYTHON=py"
set "PYTHON_ARGS=-3"
if exist "webapp\backend\.venv\Scripts\python.exe" (
    set "PYTHON=%CD%\webapp\backend\.venv\Scripts\python.exe"
    set "PYTHON_ARGS="
)
if not exist "webapp\backend\.venv\Scripts\python.exe" (
    where py >nul 2>nul
    if errorlevel 1 (
        echo Falta Python. Prepara webapp\backend\.venv con Python 3.12 o superior.
        goto cleanup
    )
)
"%PYTHON%" %PYTHON_ARGS% -B -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if errorlevel 1 (
    echo Se necesita Python 3.12 o superior. Revisa la version del interprete.
    goto cleanup
)
"%PYTHON%" %PYTHON_ARGS% -B -c "import fastapi, uvicorn, pydantic, numpy" >nul 2>nul
if errorlevel 1 (
    echo Faltan dependencias Python del backend. Preparalas segun webapp\README.md.
    goto cleanup
)
if not exist "webapp\frontend\dist\index.html" (
    echo Falta el frontend compilado. En webapp\frontend ejecuta npm ci y npm run build.
    goto cleanup
)
if not exist "webapp\backend\laboratorio\app.py" (
    echo No se encontro el backend. Revisa que el laboratorio este completo.
    goto cleanup
)
cd /d "webapp\backend"
if errorlevel 1 (
    echo No se pudo abrir webapp\backend.
    goto cleanup
)
echo Iniciando en 127.0.0.1. Para detener el servidor presiona Ctrl+C en esta ventana.
"%PYTHON%" %PYTHON_ARGS% -B -m laboratorio.app
set "EXIT_CODE=%errorlevel%"
if not "%EXIT_CODE%"=="0" echo No se pudo iniciar o finalizar correctamente el laboratorio.
:cleanup
popd
:finish
if not "%EXIT_CODE%"=="0" (
    echo Consulta el error anterior y webapp\README.md antes de reintentar.
    pause
)
exit /b %EXIT_CODE%
