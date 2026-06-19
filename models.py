from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from database import Base


class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    store_manager = Column(String(50))
    manager_phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    doctors = relationship("Doctor", back_populates="clinic")
    cleaning_records = relationship("CleaningRecord", back_populates="clinic")
    alerts = relationship("Alert", back_populates="clinic")
    config = relationship("ClinicConfig", back_populates="clinic", uselist=False)


class ClinicConfig(Base):
    __tablename__ = "clinic_configs"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, unique=True)
    followup_days_threshold = Column(Integer)
    implant_interval_days = Column(Integer)
    orthodontics_interval_days = Column(Integer)
    periodontal_interval_days = Column(Integer)
    regular_interval_days = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="config")


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    name = Column(String(50), nullable=False)
    title = Column(String(50))
    phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="doctors")
    cleaning_records = relationship("CleaningRecord", back_populates="doctor")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False, index=True)
    patient_type = Column(String(30), default="常规洁治")
    created_at = Column(DateTime, default=datetime.utcnow)

    cleaning_records = relationship("CleaningRecord", back_populates="patient")
    followups = relationship("Followup", back_populates="patient")
    appointments = relationship("Appointment", back_populates="patient")


class CleaningRecord(Base):
    __tablename__ = "cleaning_records"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    cleaning_date = Column(Date, nullable=False, index=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="cleaning_records")
    doctor = relationship("Doctor", back_populates="cleaning_records")
    patient = relationship("Patient", back_populates="cleaning_records")
    followups = relationship("Followup", back_populates="cleaning_record", order_by="Followup.followup_time")
    appointments = relationship("Appointment", back_populates="cleaning_record")
    alerts = relationship("Alert", back_populates="cleaning_record")


class Followup(Base):
    __tablename__ = "followups"

    id = Column(Integer, primary_key=True, index=True)
    cleaning_record_id = Column(Integer, ForeignKey("cleaning_records.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    followup_time = Column(DateTime, nullable=False)
    operator = Column(String(50), nullable=False)
    contact_method = Column(String(20))
    patient_feedback = Column(Text)
    has_bleeding = Column(Boolean, default=False)
    has_sensitivity = Column(Boolean, default=False)
    has_pain = Column(Boolean, default=False)
    other_symptoms = Column(String(200))
    next_step = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    cleaning_record = relationship("CleaningRecord", back_populates="followups")
    patient = relationship("Patient", back_populates="followups")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    cleaning_record_id = Column(Integer, ForeignKey("cleaning_records.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    appointment_date = Column(Date, nullable=False)
    appointment_type = Column(String(50))
    status = Column(String(20), default="待就诊")
    notes = Column(Text)
    operator = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    cleaning_record = relationship("CleaningRecord", back_populates="appointments")
    patient = relationship("Patient", back_populates="appointments")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    cleaning_record_id = Column(Integer, ForeignKey("cleaning_records.id"), nullable=False)
    alert_type = Column(String(30), nullable=False)
    alert_level = Column(String(20), default="normal")
    title = Column(String(200), nullable=False)
    description = Column(Text)
    responsible_person = Column(String(50))
    status = Column(String(20), default="待处理")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime)
    resolved_note = Column(Text)
    resolved_by = Column(String(50))
    auto_resolved = Column(Boolean, default=False)
    auto_resolved_reason = Column(String(100))
    resolved_detail = Column(String(200))
    assignee = Column(String(50))
    assigned_at = Column(DateTime)
    assigned_by = Column(String(50))
    deadline = Column(DateTime)

    clinic = relationship("Clinic", back_populates="alerts")
    cleaning_record = relationship("CleaningRecord", back_populates="alerts")
    actions = relationship("AlertAction", back_populates="alert", order_by="AlertAction.action_time.desc()")


class AlertAction(Base):
    __tablename__ = "alert_actions"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    action_type = Column(String(30), nullable=False)
    action_time = Column(DateTime, nullable=False, index=True)
    operator = Column(String(50), nullable=False)
    contact_method = Column(String(20))
    content = Column(Text)
    appointment_date = Column(Date)
    close_reason = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    alert = relationship("Alert", back_populates="actions")
    patient = relationship("Patient")


class ExportTemplateModel(Base):
    __tablename__ = "export_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(200))
    filter_clinic_id = Column(Integer)
    filter_alert_type = Column(String(30))
    filter_status = Column(String(20))
    filter_doctor_id = Column(Integer)
    filter_assignee = Column(String(50))
    filter_patient_type = Column(String(30))
    filter_start_date = Column(Date)
    filter_end_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
