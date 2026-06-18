const STORAGE_KEYS = {
  timetable: "hsportal:timetable",
  sourceFile: "hsportal:source-file",
  recommendations: "hsportal:recommendations",
};

const startButton = document.querySelector("#startButton");
const devJsonButton = document.querySelector("#devJsonButton");
const uploadModal = document.querySelector("#uploadModal");
const jsonModal = document.querySelector("#jsonModal");
const closeUploadButton = document.querySelector("#closeUploadButton");
const closeJsonButton = document.querySelector("#closeJsonButton");
const uploadForm = document.querySelector("#uploadForm");
const jsonForm = document.querySelector("#jsonForm");
const jsonInput = document.querySelector("#jsonInput");
const jsonStatus = document.querySelector("#jsonStatus");
const imageInput = document.querySelector("#imageInput");
const dropZone = document.querySelector("#dropZone");
const fileName = document.querySelector("#fileName");
const selectedImage = document.querySelector("#selectedImage");
const previewImage = document.querySelector("#previewImage");
const loadingState = document.querySelector("#loadingState");
const uploadStatus = document.querySelector("#uploadStatus");
const submitButton = document.querySelector("#submitButton");
const heartbeatStatus = document.querySelector("#heartbeatStatus");
const crawlStatus = document.querySelector("#crawlStatus");

let selectedUploadFile = null;
let selectedOriginalFile = null;
let selectedPreviewUrl = null;
let selectedCrop = null;

checkSystemStatus();

startButton.addEventListener("click", () => openModal(uploadModal));
devJsonButton.addEventListener("click", () => openModal(jsonModal));
closeUploadButton.addEventListener("click", () => closeModal(uploadModal));
closeJsonButton.addEventListener("click", () => closeModal(jsonModal));

[uploadModal, jsonModal].forEach((modal) => {
  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeModal(modal);
    }
  });
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeModal(uploadModal);
    closeModal(jsonModal);
  }
});

imageInput.addEventListener("change", async () => {
  await handleSelectedFile(imageInput.files?.[0]);
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("dragging");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragging");
});

dropZone.addEventListener("drop", async (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragging");

  const file = event.dataTransfer?.files?.[0];
  if (!file) {
    return;
  }

  const transfer = new DataTransfer();
  transfer.items.add(file);
  imageInput.files = transfer.files;
  await handleSelectedFile(file);
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = selectedUploadFile;
  if (!file) {
    setUploadStatus("시간표 이미지를 먼저 선택하세요.", "error");
    return;
  }

  sessionStorage.removeItem(STORAGE_KEYS.recommendations);
  setUploadStatus("시간표 이미지를 분석하는 중입니다.", "");
  loadingState.hidden = false;
  submitButton.disabled = true;
  submitButton.textContent = "분석 중";

  try {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch("/api/timetable/extract", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail ?? `HTTP ${response.status}`);
    }

    const sourceFile = {
      name: file.name,
      size: file.size,
      type: file.type,
      analyzedAt: new Date().toISOString(),
      source: "image",
    };

    if (selectedOriginalFile && selectedOriginalFile !== file) {
      sourceFile.originalName = selectedOriginalFile.name;
      sourceFile.originalSize = selectedOriginalFile.size;
      sourceFile.originalType = selectedOriginalFile.type;
    }
    if (selectedCrop) {
      sourceFile.crop = selectedCrop;
    }

    saveTimetable(data, sourceFile);
    window.location.href = "/timetable/";
  } catch (error) {
    setUploadStatus(error instanceof Error ? error.message : String(error), "error");
  } finally {
    loadingState.hidden = true;
    submitButton.disabled = false;
    submitButton.textContent = "분석 시작";
  }
});

jsonForm.addEventListener("submit", (event) => {
  event.preventDefault();

  try {
    const data = JSON.parse(jsonInput.value);
    if (!Array.isArray(data.courses)) {
      throw new Error("courses 배열이 필요합니다.");
    }
    saveTimetable(
      {
        courses: data.courses,
        warnings: Array.isArray(data.warnings) ? data.warnings : [],
      },
      {
        name: "dev-json-input",
        size: jsonInput.value.length,
        type: "application/json",
        analyzedAt: new Date().toISOString(),
        source: "json",
      },
    );
    window.location.href = "/timetable/";
  } catch (error) {
    jsonStatus.textContent = error instanceof Error ? error.message : String(error);
    jsonStatus.className = "status-text error";
  }
});

function saveTimetable(timetable, sourceFile) {
  sessionStorage.removeItem(STORAGE_KEYS.recommendations);
  sessionStorage.setItem(STORAGE_KEYS.timetable, JSON.stringify(timetable));
  sessionStorage.setItem(STORAGE_KEYS.sourceFile, JSON.stringify(sourceFile));
}

function openModal(modal) {
  modal.hidden = false;
  document.body.classList.add("modal-open");
  const focusable = modal.querySelector("input, textarea, button");
  focusable?.focus({ preventScroll: true });
}

function closeModal(modal) {
  modal.hidden = true;
  const hasOpenModal = document.querySelector(".modal-backdrop:not([hidden]), .dialog-backdrop:not([hidden])");
  if (!hasOpenModal) {
    document.body.classList.remove("modal-open");
  }
}

async function handleSelectedFile(file) {
  if (!file) {
    clearSelectedUploadFile();
    fileName.textContent = "PNG, JPG, WEBP 파일을 선택하세요.";
    selectedImage.hidden = true;
    previewImage.removeAttribute("src");
    return;
  }

  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
    clearSelectedUploadFile();
    setUploadStatus("PNG, JPG, WEBP 형식만 업로드할 수 있습니다.", "error");
    return;
  }

  setUploadStatus("시간표 영역을 선택하세요.", "");

  const cropResult =
    typeof window.openImageCropper === "function"
      ? await window.openImageCropper(file)
      : {
          file,
          previewUrl: URL.createObjectURL(file),
          crop: null,
        };

  if (!cropResult) {
    imageInput.value = "";
    clearSelectedUploadFile();
    fileName.textContent = "PNG, JPG, WEBP 파일을 선택하세요.";
    selectedImage.hidden = true;
    previewImage.removeAttribute("src");
    setUploadStatus("이미지 선택이 취소되었습니다.", "");
    return;
  }

  setSelectedUploadFile(cropResult, file);
}

function setSelectedUploadFile(result, originalFile) {
  clearSelectedUploadFile();

  selectedUploadFile = result.file;
  selectedOriginalFile = originalFile;
  selectedPreviewUrl = result.previewUrl;
  selectedCrop = result.crop;

  fileName.textContent = `${result.file.name} - ${formatBytes(result.file.size)}`;
  previewImage.src = result.previewUrl;
  selectedImage.hidden = false;
  setUploadStatus(
    result.crop ? "크롭된 시간표 이미지가 준비되었습니다." : "원본 이미지가 준비되었습니다.",
    "ok",
  );
}

function clearSelectedUploadFile() {
  if (selectedPreviewUrl) {
    URL.revokeObjectURL(selectedPreviewUrl);
  }

  selectedUploadFile = null;
  selectedOriginalFile = null;
  selectedPreviewUrl = null;
  selectedCrop = null;
}

async function checkSystemStatus() {
  await Promise.all([checkHeartbeat(), checkCrawlStatus()]);
}

async function checkHeartbeat() {
  try {
    const response = await fetch("/api/heartbeat");
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail ?? `HTTP ${response.status}`);
    }

    heartbeatStatus.className = "status-chip ok";
    heartbeatStatus.textContent = `${data.environment} · ${data.llm_model}`;
    if (data.environment === "dev") {
      devJsonButton.hidden = false;
    }
  } catch (error) {
    heartbeatStatus.className = "status-chip error";
    heartbeatStatus.textContent = "서버 연결 실패";
    console.error(error);
  }
}

async function checkCrawlStatus() {
  try {
    const response = await fetch("/api/hsportal/crawl-status");
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail ?? `HTTP ${response.status}`);
    }

    const labels = {
      scheduled: "비교과 데이터 준비 예약",
      running: "비교과 데이터 갱신 중",
      ready: "비교과 데이터 준비됨",
      failed: "데이터 준비 실패",
      cancelled: "데이터 준비 중단",
      unknown: "데이터 상태 알 수 없음",
    };

    crawlStatus.className = `status-chip ${data.status === "ready" ? "ok" : "muted"}`;
    crawlStatus.textContent = labels[data.status] ?? data.status;
  } catch (error) {
    crawlStatus.className = "status-chip error";
    crawlStatus.textContent = "데이터 상태 확인 실패";
    console.error(error);
  }
}

function setUploadStatus(message, type) {
  uploadStatus.textContent = message;
  uploadStatus.className = type ? `status-text ${type}` : "status-text";
}

function formatBytes(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
