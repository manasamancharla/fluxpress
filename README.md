# 🎬 FluxPress — Video Compression UI (FastAPI + FFmpeg)

A desktop-ready web UI and FastAPI backend for compressing videos using FFmpeg with precision quality control and instant downloads.

---

## 🚀 How to Run (1-Click)

You don't need to type commands in the terminal!

1. Open your folder: `C:\Users\Agent\Desktop\ffempeg`
2. **Double-click** on:
   👉 **`start_app.bat`**
3. It will automatically launch your default browser and open the UI at:
   **http://127.0.0.1:8000**

---

## ✨ Features

- **Drag-and-Drop Video Uploader**: Supports `.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`, etc.
- **Exact Quality Control (CRF Slider & Presets)**:
  - **CRF 14–18**: Visually lossless / archival master quality.
  - **CRF 23**: Default balanced compression.
  - **CRF 28+**: High compression for web, messaging, and email.
- **Resolution Control**: Keep original, or scale down to 1080p, 720p HD, 480p, or 50% scale.
- **Encoder Selection**: H.264 (universal compatibility) or H.265 / HEVC (extra size reduction).
- **Audio Quality Control**: Crisp 128k/192k AAC or Stream Copy (Lossless Audio).
- **Real-Time Progress & FFmpeg Status**: Visual progress bar and live status stream.
- **Interactive In-Browser Player**: Compare and preview the compressed video immediately before downloading.
- **Direct 1-Click Download**: Download the compressed MP4 file at your chosen quality level.
