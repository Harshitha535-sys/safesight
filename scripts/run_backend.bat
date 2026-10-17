@echo off
cd /d "%~dp0..\backend"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -r requirements.txt
if not exist models\yolox_nano.onnx python -m app.cv.fetch_model
uvicorn app.main:app --host 127.0.0.1 --port 8000
