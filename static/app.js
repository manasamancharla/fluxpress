// DOM Elements
const videoInput = document.getElementById("video-input");
const dropzone = document.getElementById("dropzone");
const dropPrompt = document.getElementById("drop-prompt");
const fileInfoBar = document.getElementById("file-info-bar");
const infoName = document.getElementById("info-name");
const infoSize = document.getElementById("info-size");
const btnRemoveFile = document.getElementById("btn-remove-file");

const crfSlider = document.getElementById("crf-slider");
const crfVal = document.getElementById("crf-val");
const crfDesc = document.getElementById("crf-desc");
const chipButtons = document.querySelectorAll(".chip-btn");

const resolutionSelect = document.getElementById("resolution-select");
const codecSelect = document.getElementById("codec-select");
const presetSelect = document.getElementById("preset-select");
const audioSelect = document.getElementById("audio-select");

const btnCompress = document.getElementById("btn-compress");
const btnCompressText = document.getElementById("btn-compress-text");
const uploadSpinner = document.getElementById("upload-spinner");

// States
const placeholderState = document.getElementById("results-placeholder");
const processingState = document.getElementById("processing-state");
const completedState = document.getElementById("completed-state");
const errorState = document.getElementById("error-state");

const procFilename = document.getElementById("proc-filename");
const procStatusText = document.getElementById("proc-status-text");
const procPct = document.getElementById("proc-pct");
const procProgressFill = document.getElementById("proc-progress-fill");
const terminalLog = document.getElementById("terminal-log");

const statOrigSize = document.getElementById("stat-orig-size");
const statCompSize = document.getElementById("stat-comp-size");
const statSavedPct = document.getElementById("stat-saved-pct");
const statCodecPill = document.getElementById("stat-codec-pill");
const previewVideo = document.getElementById("preview-video");
const btnDownload = document.getElementById("btn-download");
const errorMessage = document.getElementById("error-message");

let selectedFile = null;
let pollInterval = null;

// CRF descriptions mapping
const crfMap = {
  14: "Near Lossless / Master",
  16: "Extremely High Quality",
  18: "Visually Near-Lossless (Archival)",
  20: "Superb Quality",
  23: "Balanced (Recommended Default)",
  26: "Good Quality, Smaller Size",
  28: "High Compression (Web / Email)",
  32: "Aggressive Compression",
  36: "Maximum Compression (Tiny)"
};

function getCrfDescription(val) {
  const v = parseInt(val, 10);
  if (v <= 15) return "Virtually Lossless (High Bitrate)";
  if (v <= 19) return "Visually Near-Lossless";
  if (v <= 23) return "Balanced (Recommended)";
  if (v <= 27) return "Moderate Compression";
  if (v <= 31) return "High Compression";
  return "Maximum Compression";
}

function formatBytes(bytes, decimals = 2) {
  if (!+bytes) return "0 Bytes";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

// CRF Slider handling
crfSlider.addEventListener("input", (e) => {
  const val = e.target.value;
  crfVal.textContent = val;
  crfDesc.textContent = getCrfDescription(val);

  // Update active chip
  chipButtons.forEach(btn => {
    btn.classList.toggle("active", btn.dataset.crf === val);
  });
});

// Quick preset chips
chipButtons.forEach(btn => {
  btn.addEventListener("click", () => {
    const val = btn.dataset.crf;
    crfSlider.value = val;
    crfVal.textContent = val;
    crfDesc.textContent = btn.dataset.desc || getCrfDescription(val);
    chipButtons.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
  });
});

// File Selection handling
dropzone.addEventListener("click", (e) => {
  if (e.target !== btnRemoveFile && !btnRemoveFile.contains(e.target)) {
    videoInput.click();
  }
});

videoInput.addEventListener("change", (e) => {
  if (e.target.files && e.target.files[0]) {
    handleFile(e.target.files[0]);
  }
});

// Drag and drop
["dragenter", "dragover"].forEach(name => {
  dropzone.addEventListener(name, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach(name => {
  dropzone.addEventListener(name, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  });
});

dropzone.addEventListener("drop", (e) => {
  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
    const file = e.dataTransfer.files[0];
    if (file.type.startsWith("video/") || file.name.match(/\.(mp4|mov|mkv|avi|webm|flv|wmv|m4v)$/i)) {
      handleFile(file);
    } else {
      alert("Please drop a valid video file.");
    }
  }
});

btnRemoveFile.addEventListener("click", (e) => {
  e.stopPropagation();
  clearSelectedFile();
});

function handleFile(file) {
  selectedFile = file;
  infoName.textContent = file.name;
  infoSize.textContent = formatBytes(file.size);
  dropPrompt.classList.add("hidden");
  fileInfoBar.classList.remove("hidden");
  btnCompress.disabled = false;
}

function clearSelectedFile() {
  selectedFile = null;
  videoInput.value = "";
  dropPrompt.classList.remove("hidden");
  fileInfoBar.classList.add("hidden");
  btnCompress.disabled = true;
}

function showState(state) {
  placeholderState.classList.add("hidden");
  processingState.classList.add("hidden");
  completedState.classList.add("hidden");
  errorState.classList.add("hidden");

  if (state === "placeholder") placeholderState.classList.remove("hidden");
  else if (state === "processing") processingState.classList.remove("hidden");
  else if (state === "completed") completedState.classList.remove("hidden");
  else if (state === "error") errorState.classList.remove("hidden");
}

// Compress Action
btnCompress.addEventListener("click", async () => {
  if (!selectedFile) return;

  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("crf", crfSlider.value);
  formData.append("preset", presetSelect.value);
  formData.append("resolution", resolutionSelect.value);
  formData.append("codec", codecSelect.value);
  formData.append("audio_bitrate", audioSelect.value);

  // Set UI to loading
  btnCompress.disabled = true;
  uploadSpinner.classList.remove("hidden");
  btnCompressText.textContent = "Uploading & Preparing...";

  showState("processing");
  procFilename.textContent = selectedFile.name;
  procStatusText.textContent = "Uploading to FastAPI server...";
  procPct.textContent = "0%";
  procProgressFill.style.width = "0%";
  terminalLog.textContent = `[Upload] Transmitting ${selectedFile.name} (${formatBytes(selectedFile.size)})...\n[Config] CRF=${crfSlider.value}, Preset=${presetSelect.value}, Codec=${codecSelect.value}`;

  try {
    const res = await fetch("/api/compress", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to start compression job");
    }

    const data = await res.json();
    const jobId = data.job_id;

    btnCompressText.textContent = "Compressing...";
    procStatusText.textContent = "Encoding with FFmpeg...";
    terminalLog.textContent += `\n[Job Created] ID: ${jobId}\n[FFmpeg] Process spawned successfully. Encoding video stream...`;

    startPolling(jobId);
  } catch (err) {
    showError(err.message || "Upload failed");
    btnCompress.disabled = false;
    uploadSpinner.classList.add("hidden");
    btnCompressText.textContent = "Compress Video";
  }
});

function startPolling(jobId) {
  if (pollInterval) clearInterval(pollInterval);

  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${jobId}`);
      if (!res.ok) throw new Error("Status check failed");

      const data = await res.json();

      if (data.status === "processing" || data.status === "pending") {
        const pct = data.progress || 5;
        procPct.textContent = `${pct}%`;
        procProgressFill.style.width = `${pct}%`;
        procStatusText.textContent = `FFmpeg active: ${pct}% processed`;
        terminalLog.textContent = `[FFmpeg Encoder Active]\nProgress: ${pct}%\nCodec: ${codecSelect.value} | CRF: ${crfSlider.value}\nProcessing frames...`;
      } else if (data.status === "completed") {
        clearInterval(pollInterval);
        handleCompletion(data);
      } else if (data.status === "failed") {
        clearInterval(pollInterval);
        showError(data.error || "FFmpeg encountered an encoding error.");
      }
    } catch (err) {
      console.error("Polling error:", err);
    }
  }, 1000);
}

function handleCompletion(jobData) {
  btnCompress.disabled = false;
  uploadSpinner.classList.add("hidden");
  btnCompressText.textContent = "Compress Another";

  showState("completed");

  const inBytes = jobData.input_info?.file_size || selectedFile.size;
  const outBytes = jobData.output_info?.file_size || 0;
  const savedPct = jobData.reduction_pct || 0;

  statOrigSize.textContent = formatBytes(inBytes);
  statCompSize.textContent = formatBytes(outBytes);
  statSavedPct.textContent = savedPct > 0 ? `-${savedPct}%` : `0%`;
  statCodecPill.textContent = `${codecSelect.options[codecSelect.selectedIndex].text.split(" ")[0]} / CRF ${crfSlider.value}`;

  // Update preview video player
  previewVideo.src = jobData.preview_url;
  previewVideo.load();

  // Setup download button
  btnDownload.href = jobData.download_url;
  btnDownload.setAttribute("download", `compressed_${selectedFile ? selectedFile.name : 'video.mp4'}`);
}

function showError(msg) {
  btnCompress.disabled = false;
  uploadSpinner.classList.add("hidden");
  btnCompressText.textContent = "Compress Video";
  errorMessage.textContent = msg;
  showState("error");
}
