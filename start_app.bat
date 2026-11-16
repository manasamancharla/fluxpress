@echo off
title FluxPress - FFmpeg Video Compressor
color 0b
echo ========================================================
echo        FluxPress - FFmpeg Video Compressor UI
echo ========================================================
echo.
echo Starting FastAPI server with web UI...
echo The app will automatically launch in your default browser!
echo.
echo URL: http://127.0.0.1:8000
echo.
echo (Keep this window open while using the application)
echo ========================================================
echo.

start "" "http://127.0.0.1:8000"
python -m uvicorn main:app --host 127.0.0.1 --port 8000

pause
