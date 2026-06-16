from pathlib import Path

BASE_URL = "https://hsportal.hansung.ac.kr"
PROGRAM_STATUS_FILTER = "wait"
PROGRAM_STATUS_FILTER_LABEL = "접수(대기)중"
PROGRAM_INCLUDED_STATUS_CODES = ["scheduled", "open", "waiting"]
PROGRAM_DATA_SCHEMA_VERSION = "hsportal_programs_v2"
ALL_PROGRAMS_LIST_URL = (
    f"{BASE_URL}/ko/program/all/list/all/1?status={PROGRAM_STATUS_FILTER}&sort=date"
)

DATA_FILE = Path(__file__).resolve().parent / "programs.json"

REQUEST_TIMEOUT_SECONDS = 20.0
REQUEST_DELAY_SECONDS = 0.15
DETAIL_FETCH_CONCURRENCY = 5
USER_AGENT = "hsportal-helper/0.1 (+https://hsportal.hansung.ac.kr)"
