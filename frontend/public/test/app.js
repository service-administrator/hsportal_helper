const form = document.querySelector("#uploadForm");
const imageInput = document.querySelector("#imageInput");
const fileName = document.querySelector("#fileName");
const previewImage = document.querySelector("#previewImage");
const previewPlaceholder = document.querySelector("#previewPlaceholder");
const submitButton = document.querySelector("#submitButton");
const statusText = document.querySelector("#statusText");
const resultOutput = document.querySelector("#resultOutput");
const copyButton = document.querySelector("#copyButton");

imageInput.addEventListener("change", () => {
  const file = imageInput.files?.[0];
  if (!file) {
    fileName.textContent = "PNG, JPG, WEBP 파일을 업로드하세요.";
    previewImage.hidden = true;
    previewPlaceholder.hidden = false;
    return;
  }

  fileName.textContent = `${file.name} (${formatBytes(file.size)})`;
  previewImage.src = URL.createObjectURL(file);
  previewImage.hidden = false;
  previewPlaceholder.hidden = true;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = imageInput.files?.[0];
  if (!file) {
    setStatus("이미지를 먼저 선택하세요.", "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  submitButton.disabled = true;
  setStatus("VLM이 시간표를 분석하는 중입니다.", "");

  try {
    const response = await fetch("/api/timetable/extract", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail ?? `HTTP ${response.status}`);
    }

    resultOutput.textContent = JSON.stringify(data, null, 2);
    setStatus("변환 완료", "ok");
  } catch (error) {
    resultOutput.textContent = JSON.stringify(
      {
        error: error instanceof Error ? error.message : String(error),
      },
      null,
      2,
    );
    setStatus("변환 실패", "error");
  } finally {
    submitButton.disabled = false;
  }
});

copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(resultOutput.textContent);
  setStatus("결과를 클립보드에 복사했습니다.", "ok");
});

function setStatus(message, type) {
  statusText.textContent = message;
  statusText.className = type ? `status-text ${type}` : "status-text";
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
