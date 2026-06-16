// 서버 상태 확인
const heartbeatText = document.querySelector("#heartbeatText");
const statusDot = document.querySelector("#statusDot");

async function checkHeartbeat() {
  try {
    const response = await fetch("/api/heartbeat");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    statusDot.className = "status-dot ok";
    heartbeatText.textContent = `${data.service} 서버 연결됨 (${data.llm_model})`;
  } catch (error) {
    statusDot.className = "status-dot error";
    heartbeatText.textContent = "서버 연결 실패";
    console.error(error);
  }
}

checkHeartbeat();

// 파일 업로드
const fileInput = document.querySelector("#fileInput");
const browseBtn = document.querySelector("#browseBtn");
const uploadZone = document.querySelector("#uploadZone");
const uploadPlaceholder = document.querySelector("#uploadPlaceholder");
const uploadPreview = document.querySelector("#uploadPreview");
const previewImg = document.querySelector("#previewImg");
const removeBtn = document.querySelector("#removeBtn");
const analyzeBtn = document.querySelector("#analyzeBtn");
const resultSection = document.querySelector("#resultSection");
const resultMeta = document.querySelector("#resultMeta");
const programList = document.querySelector("#programList");

browseBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) loadFile(fileInput.files[0]);
});

uploadZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  uploadZone.classList.add("drag-over");
});

uploadZone.addEventListener("dragleave", () => {
  uploadZone.classList.remove("drag-over");
});

uploadZone.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) loadFile(file);
});

function loadFile(file) {
  const url = URL.createObjectURL(file);
  previewImg.src = url;
  uploadPlaceholder.classList.add("hidden");
  uploadPreview.classList.remove("hidden");
  analyzeBtn.disabled = false;
}

removeBtn.addEventListener("click", () => {
  fileInput.value = "";
  previewImg.src = "";
  uploadPlaceholder.classList.remove("hidden");
  uploadPreview.classList.add("hidden");
  analyzeBtn.disabled = true;
  resultSection.classList.add("hidden");
});

// 추천 요청
analyzeBtn.addEventListener("click", async () => {
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "분석 중...";
  resultSection.classList.add("hidden");

  try {
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    // TODO: 실제 엔드포인트로 교체
    // const response = await fetch("/api/recommend", { method: "POST", body: formData });
    // const data = await response.json();

    // 더미 데이터
    const data = {
      count: 3,
      programs: [
        {
          title: "캡스톤 디자인 특강",
          category: "학술",
          date: "2025-06-20",
          deadline: "2025-06-15",
          url: "https://hsportal.hansung.ac.kr",
        },
        {
          title: "취업 역량 강화 워크숍",
          category: "취업·창업",
          date: "2025-06-25",
          deadline: "2025-06-18",
          url: "https://hsportal.hansung.ac.kr",
        },
        {
          title: "글로벌 문화 교류 프로그램",
          category: "국제",
          date: "2025-07-01",
          deadline: "2025-06-22",
          url: "https://hsportal.hansung.ac.kr",
        },
      ],
    };

    renderResults(data);
  } catch (error) {
    alert("추천 요청 중 오류가 발생했습니다.");
    console.error(error);
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "추천 받기";
  }
});

function renderResults(data) {
  resultMeta.textContent = `참여 가능한 프로그램 ${data.count}건이 조회되었습니다.`;
  programList.innerHTML = "";

  data.programs.forEach((p) => {
    const li = document.createElement("li");
    li.className = "program-card";
    li.innerHTML = `
      <div class="program-header">
        <span class="program-category">${p.category}</span>
        <span class="program-deadline">마감 ${p.deadline}</span>
      </div>
      <p class="program-title">${p.title}</p>
      <div class="program-footer">
        <span class="program-date">운영일 ${p.date}</span>
        <a href="${p.url}" target="_blank" class="program-link">상세 보기 →</a>
      </div>
    `;
    programList.appendChild(li);
  });

  resultSection.classList.remove("hidden");
}
