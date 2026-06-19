import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'dental.db')}")

FOLLOWUP_DAYS_THRESHOLD = 3

HIGH_VALUE_PATIENT_TYPES = ["种植", "正畸", "牙周维护"]

FOLLOWUP_INTERVAL_DAYS = {
    "种植": 30,
    "正畸": 21,
    "牙周维护": 14,
    "常规洁治": 7,
}

SYMPTOMS_REQUIRING_REVIEW = ["牙龈出血", "牙齿敏感", "牙龈肿痛"]
