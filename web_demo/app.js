"use strict";

const preview = document.getElementById("preview");
const startButton = document.getElementById("start-camera");
const captureButton = document.getElementById("capture");
const placeholder = document.getElementById("camera-placeholder");
const cameraState = document.getElementById("camera-state");
const resultState = document.getElementById("result-state");
const statusLabel = document.getElementById("status-label");
const statusMessage = document.getElementById("status-message");
const progressBar = document.getElementById("progress-bar");
const resultImage = document.getElementById("result-image");
const resultEmpty = document.getElementById("result-empty");
const countdown = document.getElementById("countdown");
const countdownInput = document.getElementById("countdown-seconds");
const report = document.getElementById("report");
const timingLabels = [
  ["image_load_ms", "影像讀取"],
  ["resize_ms", "影像縮放"],
  ["quality_ms", "品質檢查"],
  ["roi_ms", "ROI 擷取"],
  ["seg_ms", "舌部分割"],
  ["model_load_ms", "模型載入（分割內）", true],
  ["seg_preprocess_ms", "分割前處理（分割內）", true],
  ["seg_forward_ms", "模型推論（分割內）", true],
  ["seg_postprocess_ms", "分割後處理（分割內）", true],
  ["feat_ms", "特徵擷取"],
  ["deid_ms", "去識別化"],
  ["privacy_ms", "隱私檢查耗時"],
  ["artifact_write_ms", "輸出寫入"],
  ["unaccounted_ms", "其他時間"],
  ["total_ms", "Pipeline 總時間"],
];
let stream = null;
let working = false;
let mode = null;

function showStatus(label, message, progress, error = false) {
  statusLabel.textContent = label;
  statusMessage.textContent = message;
  progressBar.style.width = `${progress}%`;
  resultState.textContent = label;
  resultState.className = error ? "pill error" : "pill muted";
}

function milliseconds(value) {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(2)} ms` : "—";
}

function showReport(meta, requestMs) {
  const timing = meta.timing_ms || {};
  const quality = meta.quality_gate || {};
  const list = document.getElementById("timing-list");
  list.replaceChildren();
  for (const [key, label, sub] of timingLabels) {
    const row = document.createElement("div");
    row.className = sub ? "timing-row sub" : "timing-row";
    const name = document.createElement("span");
    const value = document.createElement("strong");
    name.textContent = label;
    value.textContent = milliseconds(timing[key]);
    row.append(name, value);
    list.append(row);
  }
  document.getElementById("processing-time").textContent = milliseconds(timing.total_ms);
  document.getElementById("request-time").textContent = milliseconds(requestMs);
  document.getElementById("seg-backend").textContent = meta.seg_backend || "—";
  document.getElementById("roi-method").textContent = meta.roi_method_used || "—";
  document.getElementById("feature-version").textContent = meta.feature_version || "—";
  document.getElementById("quality-result").textContent = typeof quality.pass === "boolean" ? (quality.pass ? "通過" : "未通過") : "—";
  const displayMeta = {...meta};
  delete displayMeta.privacy_metrics;
  document.getElementById("metadata-json").textContent = JSON.stringify(displayMeta, null, 2);
  report.hidden = false;
}

async function initialize() {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) throw new Error("無法讀取伺服器設定。");
    const config = await response.json();
    if (!["pc", "pi", "docker"].includes(config.mode)) throw new Error("無法辨識執行模式。");
    mode = config.mode;
    if (mode === "pi") {
      document.getElementById("mode-label").textContent = "RASPBERRY PI · Docker / TFLite";
      document.getElementById("placeholder-title").textContent = "Pi 相機預覽";
      document.getElementById("placeholder-message").textContent = "按下拍照後，預覽會在 Pi 桌面另開視窗。";
      document.getElementById("preview-label").textContent = "● PI 桌面預覽";
      cameraState.textContent = "Pi 相機";
      startButton.hidden = true;
      captureButton.disabled = false;
      showStatus("準備拍攝", "按下按鈕後，Pi 相機會依設定時間預覽並拍照。", 0);
    } else {
      document.getElementById("mode-label").textContent = mode === "docker"
        ? "電腦相機 · Docker / TFLite"
        : "本機電腦 DEMO · PyTorch pipeline";
      startButton.disabled = false;
    }
  } catch (error) {
    showStatus("無法啟動", `請確認伺服器正常執行：${error.message}`, 0, true);
  }
}

initialize();

startButton.addEventListener("click", async () => {
  if (stream) return;
  if (!navigator.mediaDevices?.getUserMedia) {
    showStatus("無法啟用", "此瀏覽器不支援相機，請用 Chrome 或 Edge 開啟本機網址。", 0, true);
    return;
  }
  startButton.disabled = true;
  try {
    stream = await navigator.mediaDevices.getUserMedia({video: {width: {ideal: 640}, height: {ideal: 480}}, audio: false});
    preview.srcObject = stream;
    await preview.play();
    preview.classList.add("visible");
    placeholder.hidden = true;
    cameraState.textContent = "● 相機已開啟";
    captureButton.disabled = false;
    startButton.textContent = "相機已開啟";
    showStatus("準備拍攝", "請調整位置，再按「拍照並處理」。", 0);
    stream.getVideoTracks()[0].addEventListener("ended", () => {
      stream = null;
      captureButton.disabled = true;
      startButton.disabled = false;
      startButton.textContent = "重新開啟相機";
      cameraState.textContent = "相機已中斷";
      showStatus("相機已中斷", "請重新開啟相機。", 0, true);
    });
  } catch (error) {
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    startButton.disabled = false;
    showStatus("相機無法開啟", `請確認相機已連接，並允許瀏覽器使用：${error.message}`, 0, true);
  }
});

captureButton.addEventListener("click", async () => {
  if ((!stream && mode !== "pi") || working) return;
  const waitSeconds = countdownInput.valueAsNumber;
  if (!Number.isInteger(waitSeconds) || waitSeconds < 1 || waitSeconds > 60) {
    showStatus("設定錯誤", "倒數時間必須是 1 至 60 秒的整數。", 0, true);
    countdownInput.focus();
    return;
  }
  working = true;
  captureButton.disabled = true;
  countdownInput.disabled = true;
  resultImage.hidden = true;
  resultImage.removeAttribute("src");
  resultEmpty.hidden = false;
  report.hidden = true;
  for (const id of ["processing-time", "request-time", "seg-backend"]) {
    document.getElementById(id).textContent = "—";
  }
  try {
    let response;
    let requestStarted;
    if (mode === "pi") {
      showStatus("拍攝及處理中", `Pi 預覽 ${waitSeconds} 秒後拍照，再由 Docker 執行處理；請稍候。`, 35);
      requestStarted = performance.now();
      response = await fetch("/api/capture", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({countdown_seconds: waitSeconds}),
      });
    } else {
      for (let seconds = waitSeconds; seconds > 0; seconds--) {
        if (!stream) throw new Error("相機已中斷。");
        countdown.textContent = seconds;
        showStatus("倒數拍攝", `請保持姿勢，${seconds} 秒後拍照。`, (waitSeconds - seconds) / waitSeconds * 50);
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      if (!stream || !preview.videoWidth) throw new Error("無法取得相機影像。");
      countdown.textContent = "";
      const canvas = document.getElementById("frame");
      canvas.getContext("2d").drawImage(preview, 0, 0, 640, 480);
      const image = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.9));
      if (!image) throw new Error("無法建立照片。");
      showStatus("處理中", mode === "docker"
        ? "正在執行 Docker pipeline，第一次可能需要較長時間。"
        : "正在執行本機 PyTorch pipeline，第一次可能需要較長時間。", 65);
      requestStarted = performance.now();
      response = await fetch("/api/capture", {
        method: "POST",
        headers: {"Content-Type": "image/jpeg"},
        body: image,
      });
    }
    const result = await response.json();
    const requestMs = performance.now() - requestStarted;
    if (!response.ok) throw new Error(result.error || `處理失敗 (${response.status})`);
    if (!result.metadata || typeof result.metadata !== "object") throw new Error("處理結果缺少 metadata。");
    await new Promise((resolve, reject) => {
      resultImage.onload = resolve;
      resultImage.onerror = () => reject(new Error("無法載入處理結果影像。"));
      resultImage.src = result.image_url;
    });
    resultImage.hidden = false;
    resultEmpty.hidden = true;
    showReport(result.metadata, requestMs);
    showStatus("處理完成", "請查看影像結果與處理明細。", 100);
  } catch (error) {
    countdown.textContent = "";
    showStatus("處理失敗", error.message, 0, true);
  } finally {
    working = false;
    countdownInput.disabled = false;
    captureButton.disabled = mode !== "pi" && !stream;
  }
});

window.addEventListener("pagehide", () => {
  if (stream) {
    stream.getTracks().forEach(track => track.stop());
    stream = null;
    preview.srcObject = null;
    preview.classList.remove("visible");
    placeholder.hidden = false;
    captureButton.disabled = true;
    startButton.disabled = false;
    startButton.textContent = "重新開啟相機";
    cameraState.textContent = "相機已關閉";
  }
});
