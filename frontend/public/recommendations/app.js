const STORAGE_KEYS = {
  recommendations: "hsportal:recommendations",
};

const availableCount = document.querySelector("#availableCount");
const needsReviewCount = document.querySelector("#needsReviewCount");
const unavailableCount = document.querySelector("#unavailableCount");
const shownCount = document.querySelector("#shownCount");
const searchInput = document.querySelector("#searchInput");
const filterSelect = document.querySelector("#filterSelect");
const rankingList = document.querySelector("#rankingList");
const programModal = document.querySelector("#programModal");
const programDetailBody = document.querySelector("#programDetailBody");
const closeProgramButton = document.querySelector("#closeProgramButton");

const data = loadRecommendations();
let activeFilter = "all";

renderMetrics();
renderList();

searchInput.addEventListener("input", () => {
  renderList();
});

filterSelect.addEventListener("change", () => {
  activeFilter = filterSelect.value;
  renderList();
});

rankingList.addEventListener("click", (event) => {
  const item = event.target.closest("[data-program-id]");
  if (!item) {
    return;
  }
  openProgramDetail(item.dataset.programId);
});

closeProgramButton.addEventListener("click", closeProgramDetail);
programModal.addEventListener("click", (event) => {
  if (event.target === programModal) {
    closeProgramDetail();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeProgramDetail();
  }
});

function loadRecommendations() {
  const stored = sessionStorage.getItem(STORAGE_KEYS.recommendations);
  if (!stored) {
    return {
      recommendations: [],
      counts: {},
      warnings: ["추천 결과가 없습니다. 시간표 수정 페이지에서 추천 받기를 먼저 실행하세요."],
    };
  }

  try {
    const parsed = JSON.parse(stored);
    return {
      recommendations: Array.isArray(parsed.recommendations) ? parsed.recommendations : [],
      counts: parsed.counts ?? {},
      warnings: Array.isArray(parsed.warnings) ? parsed.warnings : [],
    };
  } catch (error) {
    console.error(error);
    return {
      recommendations: [],
      counts: {},
      warnings: ["저장된 추천 결과를 읽을 수 없습니다."],
    };
  }
}

function renderMetrics() {
  const counts = data.counts ?? {};
  availableCount.textContent = counts.available ?? 0;
  needsReviewCount.textContent = counts.needs_review ?? 0;
  unavailableCount.textContent = counts.unavailable ?? 0;
}

function renderList() {
  const items = filteredItems();
  shownCount.textContent = `전체 ${items.length}개`;

  if (!items.length) {
    rankingList.innerHTML = `
      <div class="list-empty">
        <strong>표시할 프로그램이 없습니다.</strong>
        <span>검색어를 지우거나 다른 필터를 선택하세요.</span>
      </div>
    `;
    return;
  }

  rankingList.innerHTML = items.map(renderRankingItem).join("");
}

function renderRankingItem(item, index) {
  const category = item.category ?? {};
  const program = item.program ?? {};
  const scheduleText = formatSchedules(program.schedules ?? []) || "일정 확인 필요";
  const points = getProgramPoints(item);

  return `
    <button class="ranking-item" type="button" data-program-id="${escapeAttribute(item.program_id)}">
      <span class="rank-number">${index + 1}</span>
      <span class="ranking-main">
        <strong>${escapeHtml(item.title || "제목 없음")}</strong>
        <span>${escapeHtml(category.sub || category.main || "분류 없음")}</span>
        <small>${escapeHtml(scheduleText)}</small>
      </span>
      <span class="ranking-badges">
        <span class="result-badge ${escapeHtml(item.availability)}">${availabilityLabel(item.availability)}</span>
        <span class="point-pill">${escapeHtml(formatProgramPoints(points, "포인트 없음"))}</span>
      </span>
    </button>
  `;
}

function openProgramDetail(programId) {
  const item = data.recommendations.find((recommendation) => recommendation.program_id === programId);
  if (!item) {
    return;
  }

  const program = item.program ?? {};
  const category = item.category ?? {};
  const organization = formatOrganization(program.organization);
  const schedules = program.schedules ?? [];
  const applicationPeriod = formatApplicationPeriod(program.application_period ?? {});
  const participants = formatParticipants(program.participants ?? {});
  const warnings = item.warnings ?? [];
  const conflicts = item.conflicts ?? [];
  const points = getProgramPoints(item);

  programDetailBody.innerHTML = `
    <div class="detail-head">
      <span class="result-badge ${escapeHtml(item.availability)}">${availabilityLabel(item.availability)}</span>
      <h2>${escapeHtml(item.title || "제목 없음")}</h2>
      <p>${escapeHtml(category.main || "분류 없음")} · ${escapeHtml(category.sub || "세부 없음")}</p>
    </div>

    <div class="detail-score">
      <strong>${Math.round(item.score ?? 0)}</strong>
      <span>추천 점수</span>
      <p>${escapeHtml(item.matched_reason ?? "")}</p>
    </div>

    <dl class="detail-meta">
      <div><dt>비교과 포인트</dt><dd>${escapeHtml(formatProgramPoints(points, "포인트 정보 없음"))}</dd></div>
      ${applicationPeriod ? `<div><dt>신청 기간</dt><dd>${escapeHtml(applicationPeriod)}</dd></div>` : ""}
      ${participants ? `<div><dt>신청 현황</dt><dd>${escapeHtml(participants)}</dd></div>` : ""}
      ${organization ? `<div><dt>운영 부서</dt><dd>${escapeHtml(organization)}</dd></div>` : ""}
      <div><dt>일정 유형</dt><dd>${escapeHtml(scheduleKindLabel(item.schedule_kind))}</dd></div>
    </dl>

    <section class="detail-section">
      <h3>교육 일정</h3>
      ${schedules.length ? renderScheduleTimeline(schedules) : "<p>등록된 교육 일정이 없습니다.</p>"}
    </section>

    ${warnings.length ? renderNoticeSection("확인 사항", warnings) : ""}
    ${conflicts.length ? renderNoticeSection("충돌 수업", conflicts.map(formatConflict)) : ""}

    <div class="detail-actions">
      ${item.url ? `<a class="primary-button link-button" href="${escapeAttribute(item.url)}" target="_blank" rel="noreferrer">포털에서 보기</a>` : ""}
    </div>
  `;
  programModal.hidden = false;
  document.body.classList.add("modal-open");
}

function closeProgramDetail() {
  programModal.hidden = true;
  document.body.classList.remove("modal-open");
}

function filteredItems() {
  const query = searchInput.value.trim().toLowerCase();
  return data.recommendations.filter((item) => {
    if (activeFilter !== "all" && item.availability !== activeFilter) {
      return false;
    }
    if (!query) {
      return true;
    }
    const program = item.program ?? {};
    const category = item.category ?? {};
    const haystack = [
      item.title,
      category.main,
      category.sub,
      formatOrganization(program.organization),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function renderScheduleTimeline(schedules) {
  return `
    <ol class="schedule-timeline">
      ${schedules
        .slice(0, 6)
        .map(
          (schedule) => `
            <li>
              <strong>${escapeHtml(formatDateTime(schedule.start_at))}</strong>
              <span>${escapeHtml(formatDateTime(schedule.end_at))}</span>
              ${schedule.location ? `<small>${escapeHtml(schedule.location)}</small>` : ""}
            </li>
          `,
        )
        .join("")}
      ${schedules.length > 6 ? `<li><strong>외 ${schedules.length - 6}개 일정</strong></li>` : ""}
    </ol>
  `;
}

function renderNoticeSection(title, items) {
  return `
    <section class="detail-section notice">
      <h3>${escapeHtml(title)}</h3>
      <ul>
        ${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </section>
  `;
}

function availabilityLabel(value) {
  return {
    available: "참여 가능",
    needs_review: "확인 필요",
    unavailable: "참여 불가",
  }[value] ?? value;
}

function getProgramPoints(item) {
  const rawPoints = item.points ?? item.program?.points;
  const points = Number(rawPoints);
  return Number.isInteger(points) ? points : null;
}

function formatProgramPoints(points, emptyText) {
  return points === null ? emptyText : `${points}P`;
}

function scheduleKindLabel(value) {
  return {
    same_day: "당일 일정",
    short_period: "단기 기간",
    long_period: "장기 기간",
    no_schedule: "일정 미등록",
    invalid_schedule: "일정 해석 불가",
  }[value] ?? value;
}

function formatSchedules(schedules) {
  if (!schedules.length) {
    return "";
  }
  const first = schedules[0];
  const text = `${formatDateTime(first.start_at)} ~ ${formatDateTime(first.end_at)}`;
  return schedules.length > 1 ? `${text} 외 ${schedules.length - 1}건` : text;
}

function formatApplicationPeriod(period) {
  const start = formatDateTime(period.start_at);
  const end = formatDateTime(period.end_at);
  if (!start && !end) {
    return "";
  }
  return `${start || "시작일 미상"} ~ ${end || "종료일 미상"}`;
}

function formatParticipants(participants) {
  if (participants.is_unlimited) {
    return "인원 제한 없음";
  }
  const current = Number.isInteger(participants.current) ? participants.current : null;
  const capacity = Number.isInteger(participants.capacity) ? participants.capacity : null;
  if (current === null && capacity === null) {
    return "";
  }
  return `${current ?? "-"} / ${capacity ?? "-"}명`;
}

function formatOrganization(organization) {
  if (!organization) {
    return "";
  }
  if (typeof organization === "string") {
    return organization;
  }
  const name = organization.name || "";
  const department = organization.department || "";
  if (name && department && name !== department) {
    return `${name} · ${department}`;
  }
  return name || department;
}

function formatConflict(conflict) {
  return `${conflict.course_name} ${weekdayLabel(conflict.day_of_week)} ${conflict.course_start_time}-${conflict.course_end_time}`;
}

function weekdayLabel(value) {
  return {
    MON: "월",
    TUE: "화",
    WED: "수",
    THU: "목",
    FRI: "금",
    SAT: "토",
    SUN: "일",
  }[value] ?? value;
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
