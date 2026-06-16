const heartbeatText = document.querySelector("#heartbeatText");
const statusDot = document.querySelector("#statusDot");

async function checkHeartbeat() {
  try {
    const response = await fetch("/api/heartbeat");

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

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

