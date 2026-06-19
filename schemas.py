from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field


class ClinicBase(BaseModel):
    name: str
    store_manager: Optional[str] = None
    manager_phone: Optional[str] = None


class ClinicCreate(ClinicBase):
    pass


class Clinic(ClinicBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DoctorBase(BaseModel):
    clinic_id: int
    name: str
    title: Optional[str] = None
    phone: Optional[str] = None


class DoctorCreate(DoctorBase):
    pass


class Doctor(DoctorBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PatientBase(BaseModel):
    name: str
    phone: str
    patient_type: str = "常规洁治"


class PatientCreate(PatientBase):
    pass


class Patient(PatientBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CleaningRecordBase(BaseModel):
    clinic_id: int
    doctor_id: int
    patient_id: int
    cleaning_date: date
    notes: Optional[str] = None


class CleaningRecordCreate(CleaningRecordBase):
    pass


class CleaningRecordBatchItem(BaseModel):
    clinic_id: int
    doctor_name: str
    patient_name: str
    patient_phone: str
    patient_type: str = "常规洁治"
    cleaning_date: date
    notes: Optional[str] = None


class CleaningRecordBatchCreate(BaseModel):
    items: List[CleaningRecordBatchItem]


class FollowupBase(BaseModel):
    cleaning_record_id: int
    patient_id: int
    followup_time: datetime
    operator: str
    contact_method: Optional[str] = None
    patient_feedback: Optional[str] = None
    has_bleeding: bool = False
    has_sensitivity: bool = False
    has_pain: bool = False
    other_symptoms: Optional[str] = None
    next_step: Optional[str] = None


class FollowupCreate(FollowupBase):
    pass


class FollowupSubmit(BaseModel):
    cleaning_record_id: int
    followup_time: datetime
    operator: str
    contact_method: Optional[str] = None
    patient_feedback: Optional[str] = None
    has_bleeding: bool = False
    has_sensitivity: bool = False
    has_pain: bool = False
    other_symptoms: Optional[str] = None
    next_step: Optional[str] = None
    appointment_date: Optional[date] = None
    appointment_type: Optional[str] = None


class AppointmentBase(BaseModel):
    cleaning_record_id: int
    patient_id: int
    appointment_date: date
    appointment_type: Optional[str] = None
    status: str = "待就诊"
    notes: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentSubmit(BaseModel):
    cleaning_record_id: int
    appointment_date: date
    appointment_type: Optional[str] = None
    notes: Optional[str] = None


class AlertBase(BaseModel):
    clinic_id: int
    cleaning_record_id: int
    alert_type: str
    alert_level: str = "normal"
    title: str
    description: Optional[str] = None
    responsible_person: Optional[str] = None
    status: str = "待处理"


class AlertCreate(AlertBase):
    pass


class AlertResolve(BaseModel):
    resolved_note: Optional[str] = None


class Alert(AlertBase):
    id: int
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_note: Optional[str] = None

    class Config:
        from_attributes = True


class AlertDetail(Alert):
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    doctor_name: Optional[str] = None
    cleaning_date: Optional[date] = None
    last_followup_time: Optional[datetime] = None
    last_followup_operator: Optional[str] = None


class Followup(FollowupBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Appointment(AppointmentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CleaningRecord(CleaningRecordBase):
    id: int
    created_at: datetime
    patient: Optional[Patient] = None
    doctor: Optional[Doctor] = None
    followups: List[Followup] = []
    appointments: List[Appointment] = []
    alerts: List[Alert] = []

    class Config:
        from_attributes = True


class ClinicStats(BaseModel):
    clinic_id: int
    clinic_name: str
    total_cleanings: int = 0
    followed_up_count: int = 0
    followup_rate: float = 0.0
    appointed_count: int = 0
    appointment_rate: float = 0.0
    overdue_count: int = 0
    alert_pending_count: int = 0
    unfollowup_count: int = 0
    unconverted_count: int = 0
    high_value_overdue_count: int = 0


class CleaningRecordDetail(BaseModel):
    id: int
    cleaning_date: date
    patient_name: str
    patient_phone: str
    patient_type: str
    doctor_name: str
    clinic_name: str
    followups: List[Followup] = []
    appointments: List[Appointment] = []
    alerts: List[Alert] = []
    responsible_person: Optional[str] = None
    last_process_time: Optional[datetime] = None
