const form = document.querySelector("#uploadForm");
const imageInput = document.querySelector("#imageInput");
const fileName = document.querySelector("#fileName");
const previewImage = document.querySelector("#previewImage");
const previewPlaceholder = document.querySelector("#previewPlaceholder");
const submitButton = document.querySelector("#submitButton");
const statusText = document.querySelector("#statusText");
const resultOutput = document.querySelector("#resultOutput");
const copyButton = document.querySelector("#copyButton");
const sampleButton = document.querySelector("#sampleButton");
const recommendButton = document.querySelector("#recommendButton");
const recommendSummary = document.querySelector("#recommendSummary");
const recommendList = document.querySelector("#recommendList");

const sampleTimetable = {
  courses: [
    {
      course_name: "자료구조",
      day_of_week: "FRI",
      start_time: "09:00",
      end_time: "10:30",
      location: "탐구관",
      instructor: null,
      confidence: 1,
    },
    {
      course_name: "웹프로그래밍",
      day_of_week: "FRI",
      start_time: "15:00",
      end_time: "16:30",
      location: "상상관",
      instructor: null,
      confidence: 1,
    },
  ],
  warnings: [],
};

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

    resultOutput.value = JSON.stringify(data, null, 2);
    setStatus("변환 완료", "ok");
  } catch (error) {
    resultOutput.value = JSON.stringify(
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
  await navigator.clipboard.writeText(resultOutput.value);
  setStatus("결과를 클립보드에 복사했습니다.", "ok");
});

sampleButton.addEventListener("click", () => {
  resultOutput.value = JSON.stringify(sampleTimetable, null, 2);
  setStatus("샘플 시간표를 입력했습니다.", "ok");
});

recommendButton.addEventListener("click", async () => {
  let timetable;

  try {
    timetable = JSON.parse(resultOutput.value);
  } catch (error) {
    renderRecommendationError("시간표 JSON 형식이 올바르지 않습니다.");
    return;
  }

  if (!Array.isArray(timetable.courses)) {
    renderRecommendationError("courses 배열이 필요합니다.");
    return;
  }

  recommendButton.disabled = true;
  recommendButton.textContent = "추천 중";
  renderRecommendationLoading();

  try {
    const response = await fetch("/api/recommendations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        courses: timetable.courses,
        include_needs_review: true,
        include_unavailable: true,
        limit: 50,
      }),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail ?? `HTTP ${response.status}`);
    }

    renderRecommendations(data);
  } catch (error) {
    renderRecommendationError(error instanceof Error ? error.message : String(error));
  } finally {
    recommendButton.disabled = false;
    recommendButton.textContent = "추천 실행";
  }
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

function renderRecommendationLoading() {
  recommendSummary.innerHTML = `
    <span>available ...</span>
    <span>needs_review ...</span>
    <span>unavailable ...</span>
  `;
  recommendList.innerHTML = '<p class="empty-state">비교과 프로그램을 평가하는 중입니다.</p>';
}

function renderRecommendationError(message) {
  recommendSummary.innerHTML = `
    <span>available 0</span>
    <span>needs_review 0</span>
    <span>unavailable 0</span>
  `;
  recommendList.innerHTML = `<p class="empty-state error">${escapeHtml(message)}</p>`;
}

function renderRecommendations(data) {
  const counts = data.counts ?? {};
  recommendSummary.innerHTML = `
    <span>available ${counts.available ?? 0}</span>
    <span>needs_review ${counts.needs_review ?? 0}</span>
    <span>unavailable ${counts.unavailable ?? 0}</span>
    <span>returned ${counts.returned ?? 0}</span>
  `;

  const items = data.recommendations ?? [];
  if (items.length === 0) {
    recommendList.innerHTML = '<p class="empty-state">추천 결과가 없습니다.</p>';
    return;
  }

  recommendList.innerHTML = items.map(renderRecommendationCard).join("");
}

function renderRecommendationCard(item) {
  const category = item.category ?? {};
  const warnings = item.warnings ?? [];
  const conflicts = item.conflicts ?? [];
  const program = item.program ?? {};
  const scheduleText = formatSchedules(program.schedules ?? []);
  const warningText = warnings.length
    ? `<ul class="meta-list">${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>`
    : "";
  const conflictText = conflicts.length
    ? `<ul class="meta-list">${conflicts.map(renderConflict).join("")}</ul>`
    : "";

  return `
    <article class="recommend-card ${escapeHtml(item.availability)}">
      <div class="card-head">
        <div>
          <span class="badge ${escapeHtml(item.availability)}">${escapeHtml(item.availability)}</span>
          <span class="badge muted">${escapeHtml(item.schedule_kind)}</span>
        </div>
        <strong>${Math.round(item.score ?? 0)}점</strong>
      </div>
      <h3>${escapeHtml(item.title)}</h3>
      <p class="category-line">
        ${escapeHtml(category.main ?? "분류 없음")} / ${escapeHtml(category.sub ?? "세부 없음")}
      </p>
      <p class="reason">${escapeHtml(item.matched_reason ?? "")}</p>
      ${scheduleText ? `<p class="schedule-line">${escapeHtml(scheduleText)}</p>` : ""}
      ${warningText}
      ${conflictText}
      ${item.url ? `<a class="program-link" href="${escapeAttribute(item.url)}" target="_blank" rel="noreferrer">상세 보기</a>` : ""}
    </article>
  `;
}

function renderConflict(conflict) {
  return `
    <li>
      ${escapeHtml(conflict.course_name)}
      ${escapeHtml(conflict.course_start_time)}-${escapeHtml(conflict.course_end_time)}
      충돌
    </li>
  `;
}

function formatSchedules(schedules) {
  if (!schedules.length) {
    return "";
  }

  return schedules
    .slice(0, 2)
    .map((schedule) => {
      const start = formatDateTime(schedule.start_at);
      const end = formatDateTime(schedule.end_at);
      const location = schedule.location ? ` · ${schedule.location}` : "";
      return `${start} ~ ${end}${location}`;
    })
    .join(" / ");
}

function formatDateTime(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}
