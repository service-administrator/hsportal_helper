const STORAGE_KEYS = {
  timetable: "hsportal:timetable",
  sourceFile: "hsportal:source-file",
  recommendations: "hsportal:recommendations",
};

const DAYS = [
  ["MON", "월"],
  ["TUE", "화"],
  ["WED", "수"],
  ["THU", "목"],
  ["FRI", "금"],
  ["SAT", "토"],
  ["SUN", "일"],
];
const BOARD_START = 8 * 60;
const BOARD_END = 22 * 60;
const SNAP_MINUTES = 30;
const HOUR_HEIGHT = 34;
const MINUTE_HEIGHT = HOUR_HEIGHT / 60;

const scheduleBoard = document.querySelector("#scheduleBoard");
const sourceFile = document.querySelector("#sourceFile");
const courseCount = document.querySelector("#courseCount");
const editorStatus = document.querySelector("#editorStatus");
const addCourseButton = document.querySelector("#addCourseButton");
const recommendButton = document.querySelector("#recommendButton");
const toggleJsonButton = document.querySelector("#toggleJsonButton");
const jsonDrawer = document.querySelector("#jsonDrawer");
const jsonOutput = document.querySelector("#jsonOutput");
const copyJsonButton = document.querySelector("#copyJsonButton");

const courseDialog = document.querySelector("#courseDialog");
const courseForm = document.querySelector("#courseForm");
const dialogTitle = document.querySelector("#dialogTitle");
const closeDialogButton = document.querySelector("#closeDialogButton");
const cancelDialogButton = document.querySelector("#cancelDialogButton");
const deleteCourseButton = document.querySelector("#deleteCourseButton");
const courseNameInput = document.querySelector("#courseNameInput");
const dayInput = document.querySelector("#dayInput");
const startInput = document.querySelector("#startInput");
const endInput = document.querySelector("#endInput");

let timetable = loadTimetable();
let editingIndex = null;
let creatingCourse = false;

initDayOptions();
renderSourceFile();
renderBoard();
renderJson();
setInitialStatus();

addCourseButton.addEventListener("click", () => {
  const slot = findFirstFreeSlot(60);
  if (!slot) {
    setEditorStatus("비어 있는 1시간 구간을 찾지 못했습니다.", "error");
    return;
  }
  const index = addCourse({
    course_name: "새 수업",
    day_of_week: slot.day,
    start_time: timeFromMinutes(slot.start),
    end_time: timeFromMinutes(slot.end),
  });
  openDialog(index, { isNew: true });
});

toggleJsonButton.addEventListener("click", () => {
  jsonDrawer.hidden = !jsonDrawer.hidden;
  toggleJsonButton.textContent = jsonDrawer.hidden ? "JSON 보기" : "JSON 닫기";
});

copyJsonButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(JSON.stringify(timetable, null, 2));
  setEditorStatus("최종 시간표 JSON을 복사했습니다.", "ok");
});

recommendButton.addEventListener("click", async () => {
  const validationMessage = validateCourses();
  if (validationMessage) {
    setEditorStatus(validationMessage, "error");
    return;
  }

  persistTimetable();
  recommendButton.disabled = true;
  recommendButton.textContent = "추천 계산 중";
  setEditorStatus("수업 시간과 비교과 프로그램 일정을 비교하는 중입니다.", "");

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
        limit: 100,
      }),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail ?? `HTTP ${response.status}`);
    }

    sessionStorage.setItem(STORAGE_KEYS.recommendations, JSON.stringify(data));
    window.location.href = "/recommendations/";
  } catch (error) {
    setEditorStatus(error instanceof Error ? error.message : String(error), "error");
  } finally {
    recommendButton.disabled = false;
    recommendButton.textContent = "추천 받기";
  }
});

courseForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (editingIndex === null) {
    return;
  }

  if (startInput.value >= endInput.value) {
    setEditorStatus("종료 시간은 시작 시간보다 늦어야 합니다.", "error");
    return;
  }

  const nextCourse = normalizeCourse({
    course_name: courseNameInput.value.trim(),
    day_of_week: dayInput.value,
    start_time: startInput.value,
    end_time: endInput.value,
  });

  if (hasCourseConflict(nextCourse, editingIndex)) {
    setEditorStatus("같은 요일에 겹치는 수업이 있습니다. 시간을 다시 조정하세요.", "error");
    return;
  }

  timetable.courses[editingIndex] = nextCourse;
  closeDialog({ preserveNew: true });
  renderBoard();
  persistTimetable();
  setEditorStatus("수업 정보가 저장되었습니다.", "ok");
});

deleteCourseButton.addEventListener("click", () => {
  if (editingIndex === null) {
    return;
  }
  timetable.courses.splice(editingIndex, 1);
  creatingCourse = false;
  closeDialog({ preserveNew: true });
  renderBoard();
  persistTimetable();
  setEditorStatus("수업을 삭제했습니다.", "ok");
});

closeDialogButton.addEventListener("click", closeDialog);
cancelDialogButton.addEventListener("click", closeDialog);
courseDialog.addEventListener("click", (event) => {
  if (event.target === courseDialog) {
    closeDialog();
  }
});

function loadTimetable() {
  const stored = sessionStorage.getItem(STORAGE_KEYS.timetable);
  if (!stored) {
    setEditorStatus("시간표 데이터가 없습니다. 메인 페이지에서 이미지를 먼저 업로드하세요.", "error");
    return { courses: [], warnings: [] };
  }

  try {
    const parsed = JSON.parse(stored);
    return {
      courses: Array.isArray(parsed.courses) ? parsed.courses.map(normalizeCourse) : [],
      warnings: Array.isArray(parsed.warnings) ? parsed.warnings : [],
    };
  } catch (error) {
    console.error(error);
    setEditorStatus("저장된 시간표 데이터를 읽을 수 없습니다.", "error");
    return { courses: [], warnings: [] };
  }
}

function renderSourceFile() {
  const stored = sessionStorage.getItem(STORAGE_KEYS.sourceFile);
  if (!stored) {
    return;
  }

  try {
    const file = JSON.parse(stored);
    sourceFile.textContent = `${file.name ?? "시간표 이미지"} · ${formatBytes(file.size ?? 0)}`;
  } catch (error) {
    console.error(error);
  }
}

function renderBoard() {
  const hours = [];
  for (let minute = BOARD_START; minute <= BOARD_END; minute += 60) {
    hours.push(minute);
  }

  scheduleBoard.innerHTML = `
    <div class="board-grid" style="--board-height: ${((BOARD_END - BOARD_START) / 60) * HOUR_HEIGHT}px; --day-count: ${DAYS.length}">
      <div class="day-header gutter"></div>
      ${DAYS.map(([, label]) => `<div class="day-header">${label}</div>`).join("")}
      <div class="time-rail">
        ${hours
          .slice(0, -1)
          .map(
            (minute) => `
              <span style="top: ${(minute - BOARD_START) * MINUTE_HEIGHT + 10}px">
                ${formatTime(minute)}
              </span>
            `,
          )
          .join("")}
      </div>
      ${DAYS.map(
        ([day]) => `
          <div class="day-lane" data-day="${day}">
            ${hours
              .slice(0, -1)
              .map(
                (minute) => `
                  <span class="hour-line" style="top: ${(minute - BOARD_START) * MINUTE_HEIGHT}px"></span>
                `,
              )
              .join("")}
          </div>
        `,
      ).join("")}
    </div>
  `;

  timetable.courses.forEach((course, index) => {
    const lane = scheduleBoard.querySelector(`[data-day="${course.day_of_week}"]`);
    if (!lane) {
      return;
    }
    lane.insertAdjacentHTML("beforeend", renderCourseBlock(course, index));
  });

  scheduleBoard.querySelectorAll(".day-lane").forEach((lane) => {
    lane.addEventListener("pointerdown", handleLanePointerDown);
  });
  scheduleBoard.querySelectorAll(".course-block").forEach((block) => {
    block.addEventListener("pointerdown", handleBlockPointerDown);
  });

  courseCount.textContent = `${timetable.courses.length}개`;
  renderJson();
}

function setInitialStatus() {
  const conflicts = findCourseConflictPairs();
  if (conflicts.length) {
    setEditorStatus("겹치는 수업이 있습니다. 빨간 표시된 블록의 시간을 수정하세요.", "error");
    return;
  }
  if (timetable.courses.length) {
    setEditorStatus("블록을 드래그하거나 클릭해 수업 정보를 수정하세요.", "ok");
    return;
  }
  setEditorStatus("수업이 없습니다. 빈 시간대를 드래그하거나 수업 추가 버튼을 누르세요.", "error");
}

function renderCourseBlock(course, index) {
  const start = minutesFromTime(course.start_time);
  const end = minutesFromTime(course.end_time);
  const visibleStart = clamp(start, BOARD_START, BOARD_END);
  const visibleEnd = clamp(end, BOARD_START, BOARD_END);
  const boardHeight = (BOARD_END - BOARD_START) * MINUTE_HEIGHT;
  const height = Math.max((visibleEnd - visibleStart) * MINUTE_HEIGHT, 32);
  const top = clamp((visibleStart - BOARD_START) * MINUTE_HEIGHT, 0, boardHeight - height);

  const conflictClass = hasCourseConflict(course, index) ? " conflict" : "";
  const outOfRangeClass = start < BOARD_START || end > BOARD_END ? " out-of-range" : "";

  return `
    <article
      class="course-block${conflictClass}${outOfRangeClass}"
      data-index="${index}"
      style="top: ${top}px; height: ${height}px"
      tabindex="0"
      aria-label="${escapeAttribute(course.course_name)} ${course.start_time}-${course.end_time}"
    >
      <strong>${escapeHtml(course.course_name || "새 수업")}</strong>
      <span>${escapeHtml(course.start_time)}-${escapeHtml(course.end_time)}</span>
    </article>
  `;
}

function handleLanePointerDown(event) {
  if (event.target.closest(".course-block")) {
    return;
  }

  const lane = event.currentTarget;
  const start = snapMinuteFromEvent(event, lane);
  const selection = document.createElement("div");
  selection.className = "time-selection";
  lane.appendChild(selection);
  updateSelection(selection, start, start + SNAP_MINUTES);

  const onMove = (moveEvent) => {
    const current = snapMinuteFromEvent(moveEvent, lane);
    updateSelection(selection, Math.min(start, current), Math.max(start + SNAP_MINUTES, current));
  };

  const onUp = (upEvent) => {
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onUp);

    const end = snapMinuteFromEvent(upEvent, lane);
    const startMinute = Math.min(start, end);
    const endMinute = Math.max(start + SNAP_MINUTES, end);
    selection.remove();

    const index = addCourse({
      course_name: "새 수업",
      day_of_week: lane.dataset.day,
      start_time: timeFromMinutes(startMinute),
      end_time: timeFromMinutes(endMinute),
    }, { rejectConflict: true });
    if (index === null) {
      setEditorStatus("해당 시간에는 이미 수업이 있습니다. 빈 시간대를 선택하세요.", "error");
      return;
    }
    openDialog(index, { isNew: true });
  };

  document.addEventListener("pointermove", onMove);
  document.addEventListener("pointerup", onUp);
}

function handleBlockPointerDown(event) {
  event.preventDefault();
  const block = event.currentTarget;
  const index = Number(block.dataset.index);
  const course = timetable.courses[index];
  const duration = minutesFromTime(course.end_time) - minutesFromTime(course.start_time);
  const initialDay = course.day_of_week;
  const initialStart = course.start_time;
  const initialEnd = course.end_time;
  let moved = false;
  block.classList.add("dragging");
  block.style.pointerEvents = "none";

  const onMove = (moveEvent) => {
    moved = true;
    const lane = document.elementFromPoint(moveEvent.clientX, moveEvent.clientY)?.closest(".day-lane");
    if (!lane) {
      return;
    }
    const start = clamp(
      snapMinuteFromEvent(moveEvent, lane),
      BOARD_START,
      BOARD_END - Math.max(duration, SNAP_MINUTES),
    );
    const end = start + Math.max(duration, SNAP_MINUTES);
    lane.appendChild(block);
    block.style.top = `${(start - BOARD_START) * MINUTE_HEIGHT}px`;
    block.style.height = `${Math.max((end - start) * MINUTE_HEIGHT, 42)}px`;
    block.querySelector("span").textContent = `${timeFromMinutes(start)}-${timeFromMinutes(end)}`;
    block.dataset.nextDay = lane.dataset.day;
    block.dataset.nextStart = timeFromMinutes(start);
    block.dataset.nextEnd = timeFromMinutes(end);
  };

  const onUp = () => {
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onUp);
    block.classList.remove("dragging");
    block.style.pointerEvents = "";

    if (!moved) {
      openDialog(index);
      return;
    }

    const nextCourse = normalizeCourse({
      ...course,
      day_of_week: block.dataset.nextDay || initialDay,
      start_time: block.dataset.nextStart || initialStart,
      end_time: block.dataset.nextEnd || initialEnd,
    });

    if (hasCourseConflict(nextCourse, index)) {
      renderBoard();
      setEditorStatus("이동한 위치가 다른 수업과 겹쳐서 변경하지 않았습니다.", "error");
      return;
    }

    timetable.courses[index] = nextCourse;
    persistTimetable();
    renderBoard();
    setEditorStatus("수업 시간이 변경되었습니다.", "ok");
  };

  document.addEventListener("pointermove", onMove);
  document.addEventListener("pointerup", onUp);
}

function updateSelection(selection, start, end) {
  const clippedStart = clamp(start, BOARD_START, BOARD_END - SNAP_MINUTES);
  const clippedEnd = clamp(end, clippedStart + SNAP_MINUTES, BOARD_END);
  selection.style.top = `${(clippedStart - BOARD_START) * MINUTE_HEIGHT}px`;
  selection.style.height = `${(clippedEnd - clippedStart) * MINUTE_HEIGHT}px`;
}

function addCourse(course, options = {}) {
  const normalized = normalizeCourse(course);
  if (options.rejectConflict && hasCourseConflict(normalized, null)) {
    return null;
  }
  timetable.courses.push(normalized);
  persistTimetable();
  renderBoard();
  return timetable.courses.length - 1;
}

function openDialog(index, options = {}) {
  editingIndex = index;
  creatingCourse = Boolean(options.isNew);
  const course = timetable.courses[index];
  dialogTitle.textContent = course.course_name && course.course_name !== "새 수업" ? "수업 수정" : "수업 추가";
  courseNameInput.value = course.course_name || "";
  dayInput.value = course.day_of_week || "MON";
  startInput.value = course.start_time || "09:00";
  endInput.value = course.end_time || "10:00";
  courseDialog.hidden = false;
  courseNameInput.focus();
}

function closeDialog(options = {}) {
  if (creatingCourse && !options.preserveNew && editingIndex !== null) {
    timetable.courses.splice(editingIndex, 1);
    persistTimetable();
    renderBoard();
    setEditorStatus("수업 추가를 취소했습니다.", "ok");
  }
  courseDialog.hidden = true;
  editingIndex = null;
  creatingCourse = false;
}

function initDayOptions() {
  dayInput.innerHTML = DAYS.map(
    ([value, label]) => `<option value="${value}">${label}요일</option>`,
  ).join("");
}

function normalizeCourse(course) {
  const start = normalizeTime(course.start_time || "09:00");
  const end = normalizeTime(course.end_time || "10:00");
  return {
    course_name: String(course.course_name || "새 수업"),
    day_of_week: DAYS.some(([day]) => day === course.day_of_week) ? course.day_of_week : "MON",
    start_time: start,
    end_time: end > start ? end : timeFromMinutes(minutesFromTime(start) + 60),
  };
}

function validateCourses() {
  if (!timetable.courses.length) {
    return "추천을 받으려면 수업을 한 개 이상 입력하세요.";
  }

  for (const [index, course] of timetable.courses.entries()) {
    if (!course.course_name.trim()) {
      return `${index + 1}번째 수업명을 입력하세요.`;
    }
    if (course.start_time >= course.end_time) {
      return `${course.course_name}의 종료 시간이 시작 시간보다 늦어야 합니다.`;
    }
    if (hasCourseConflict(course, index)) {
      return `${course.course_name} 시간이 다른 수업과 겹칩니다.`;
    }
  }

  return "";
}

function findFirstFreeSlot(durationMinutes) {
  for (const [day] of DAYS) {
    for (let start = BOARD_START; start + durationMinutes <= BOARD_END; start += SNAP_MINUTES) {
      const course = normalizeCourse({
        course_name: "새 수업",
        day_of_week: day,
        start_time: timeFromMinutes(start),
        end_time: timeFromMinutes(start + durationMinutes),
      });
      if (!hasCourseConflict(course, null)) {
        return {
          day,
          start,
          end: start + durationMinutes,
        };
      }
    }
  }
  return null;
}

function findCourseConflictPairs() {
  const pairs = [];
  for (let i = 0; i < timetable.courses.length; i += 1) {
    for (let j = i + 1; j < timetable.courses.length; j += 1) {
      if (coursesOverlap(timetable.courses[i], timetable.courses[j])) {
        pairs.push([i, j]);
      }
    }
  }
  return pairs;
}

function hasCourseConflict(course, ownIndex) {
  return timetable.courses.some((existing, index) => {
    if (ownIndex !== null && index === ownIndex) {
      return false;
    }
    return coursesOverlap(course, existing);
  });
}

function coursesOverlap(a, b) {
  if (a.day_of_week !== b.day_of_week) {
    return false;
  }
  const startA = minutesFromTime(a.start_time);
  const endA = minutesFromTime(a.end_time);
  const startB = minutesFromTime(b.start_time);
  const endB = minutesFromTime(b.end_time);
  return startA < endB && startB < endA;
}

function persistTimetable() {
  sessionStorage.setItem(STORAGE_KEYS.timetable, JSON.stringify(timetable));
  renderJson();
}

function renderJson() {
  jsonOutput.value = JSON.stringify(timetable, null, 2);
}

function setEditorStatus(message, type) {
  editorStatus.textContent = message;
  editorStatus.className = type ? `status-inline ${type}` : "status-inline";
}

function snapMinuteFromEvent(event, lane) {
  const rect = lane.getBoundingClientRect();
  const raw = BOARD_START + (event.clientY - rect.top) / MINUTE_HEIGHT;
  return clamp(Math.round(raw / SNAP_MINUTES) * SNAP_MINUTES, BOARD_START, BOARD_END);
}

function normalizeTime(value) {
  const [hour = "09", minute = "00"] = String(value).split(":");
  return `${String(Number(hour)).padStart(2, "0")}:${String(Number(minute)).padStart(2, "0")}`;
}

function minutesFromTime(value) {
  const [hour, minute] = normalizeTime(value).split(":").map(Number);
  return hour * 60 + minute;
}

function timeFromMinutes(value) {
  const clipped = clamp(value, 0, 24 * 60 - SNAP_MINUTES);
  const hour = Math.floor(clipped / 60);
  const minute = clipped % 60;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function formatTime(value) {
  return `${String(Math.floor(value / 60)).padStart(2, "0")}:00`;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function formatBytes(bytes) {
  if (!bytes) {
    return "크기 알 수 없음";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
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
