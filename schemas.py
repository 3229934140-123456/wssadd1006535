from datetime import datetime, date
from typing import Optional, List, Dict, Any
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


class ClinicConfigBase(BaseModel):
    clinic_id: int
    followup_days_threshold: Optional[int] = None
    implant_interval_days: Optional[int] = None
    orthodontics_interval_days: Optional[int] = None
    periodontal_interval_days: Optional[int] = None
    regular_interval_days: Optional[int] = None


class ClinicConfigCreate(ClinicConfigBase):
    pass


class ClinicConfigUpdate(BaseModel):
    followup_days_threshold: Optional[int] = None
    implant_interval_days: Optional[int] = None
    orthodontics_interval_days: Optional[int] = None
    periodontal_interval_days: Optional[int] = None
    regular_interval_days: Optional[int] = None


class ClinicConfig(ClinicConfigBase):
    id: int
    created_at: datetime
    updated_at: datetime

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
    operator: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentSubmit(BaseModel):
    cleaning_record_id: int
    appointment_date: date
    appointment_type: Optional[str] = None
    notes: Optional[str] = None
    operator: Optional[str] = None


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


class AlertAssign(BaseModel):
    assignee: str = Field(..., description="负责人姓名")
    deadline: Optional[datetime] = Field(None, description="跟进截止时间")
    assigned_by: Optional[str] = Field(None, description="分派人")


class Alert(AlertBase):
    id: int
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_note: Optional[str] = None
    resolved_by: Optional[str] = None
    auto_resolved: bool = False
    auto_resolved_reason: Optional[str] = None
    resolved_detail: Optional[str] = None
    assignee: Optional[str] = None
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[str] = None
    deadline: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertActionBase(BaseModel):
    alert_id: int
    action_type: str
    action_time: datetime
    operator: str
    contact_method: Optional[str] = None
    content: Optional[str] = None
    appointment_date: Optional[date] = None
    close_reason: Optional[str] = None


class AlertActionCreate(BaseModel):
    alert_id: int
    action_type: str = Field(..., description="跟进类型: 电话/微信/短信/预约/关闭")
    action_time: datetime
    operator: str
    contact_method: Optional[str] = None
    content: Optional[str] = None
    appointment_date: Optional[date] = None
    close_reason: Optional[str] = None


class AlertAction(AlertActionBase):
    id: int
    clinic_id: int
    patient_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class AlertDetail(Alert):
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    doctor_name: Optional[str] = None
    cleaning_date: Optional[date] = None
    last_followup_time: Optional[datetime] = None
    last_followup_operator: Optional[str] = None
    actions: List[AlertAction] = []
    is_overdue_deadline: Optional[bool] = None


class AlertDetailWithTimeline(AlertDetail):
    actions: List[AlertAction] = []


class TrendDataPoint(BaseModel):
    period: str
    start_date: date
    end_date: date
    new_alerts: int = 0
    resolved_alerts: int = 0
    auto_resolved_count: int = 0
    auto_resolve_rate: float = 0.0
    avg_resolve_hours: float = 0.0
    pending_alerts: int = 0


class TrendResponse(BaseModel):
    period_type: str
    clinic_id: Optional[int] = None
    data_points: List[TrendDataPoint] = []
    by_clinic: Optional[Dict[int, List[TrendDataPoint]]] = None


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


class OverviewRankingItem(BaseModel):
    id: int
    name: str
    total_cleanings: int = 0
    followed_up_count: int = 0
    appointed_count: int = 0
    followup_rate: float = 0.0
    appointment_rate: float = 0.0
    overdue_count: int = 0
    unfollowup_count: int = 0
    unconverted_count: int = 0
    high_value_overdue_count: int = 0
    alert_pending_count: int = 0
    alert_count: int = 0


class OverviewSummary(BaseModel):
    total_clinics: int = 0
    total_doctors: int = 0
    total_patients: int = 0
    total_cleanings: int = 0
    overall_followup_rate: float = 0.0
    overall_appointment_rate: float = 0.0
    total_overdue: int = 0
    total_alerts_pending: int = 0
    unfollowup_count: int = 0
    unconverted_count: int = 0
    high_value_overdue_count: int = 0


class PatientActionHistory(BaseModel):
    action_id: int
    alert_id: int
    alert_type: str
    alert_title: str
    action_type: str
    action_time: datetime
    operator: str
    contact_method: Optional[str] = None
    content: Optional[str] = None
    close_reason: Optional[str] = None


class PatientAlertHistory(BaseModel):
    patient_id: int
    patient_name: str
    patient_phone: str
    patient_type: str
    total_alerts: int = 0
    pending_alerts: int = 0
    resolved_alerts: int = 0
    actions: List[PatientActionHistory] = []


class OverviewResponse(BaseModel):
    summary: OverviewSummary
    clinic_ranking: List[OverviewRankingItem] = []
    doctor_ranking: List[OverviewRankingItem] = []
    patient_type_breakdown: List[Dict[str, Any]] = []
    date_range: Optional[Dict[str, Optional[date]]] = None


class HighValueExportItem(BaseModel):
    clinic_name: str
    patient_name: str
    patient_phone: str
    patient_type: str
    doctor_name: str
    cleaning_date: date
    overdue_days: int
    alert_type: str
    alert_title: str
    status: str
    responsible_person: Optional[str] = None
    assignee: Optional[str] = None
    deadline: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_detail: Optional[str] = None
    auto_resolved: Optional[bool] = None
    last_followup_time: Optional[datetime] = None
    last_followup_content: Optional[str] = None


class HighValueExportResponse(BaseModel):
    clinic_id: Optional[int] = None
    clinic_name: Optional[str] = None
    export_time: datetime
    total_count: int = 0
    high_value_count: int = 0
    unconverted_count: int = 0
    items: List[HighValueExportItem] = []


OverviewResponse.model_rebuild()
PatientAlertHistory.model_rebuild()
TrendResponse.model_rebuild()
