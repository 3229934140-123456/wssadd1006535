import os
from typing import Optional, Dict
from sqlalchemy.orm import Session

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

ACTION_TYPES = ["电话", "微信", "短信", "预约", "关闭"]


def get_followup_threshold(db: Session, clinic_id: Optional[int]) -> int:
    if clinic_id:
        from models import ClinicConfig
        config = db.query(ClinicConfig).filter(ClinicConfig.clinic_id == clinic_id).first()
        if config and config.followup_days_threshold is not None:
            return config.followup_days_threshold
    return FOLLOWUP_DAYS_THRESHOLD


def get_interval_days(db: Session, clinic_id: Optional[int], patient_type: str) -> int:
    default = FOLLOWUP_INTERVAL_DAYS.get(patient_type, 30)
    if clinic_id:
        from models import ClinicConfig
        config = db.query(ClinicConfig).filter(ClinicConfig.clinic_id == clinic_id).first()
        if config:
            mapping = {
                "种植": config.implant_interval_days,
                "正畸": config.orthodontics_interval_days,
                "牙周维护": config.periodontal_interval_days,
                "常规洁治": config.regular_interval_days,
            }
            if mapping.get(patient_type) is not None:
                return mapping[patient_type]
    return default
