from datetime import date, datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import Clinic, Doctor, Patient, CleaningRecord, Followup, Appointment, Alert
from schemas import (
    ClinicCreate, Clinic as ClinicSchema,
    DoctorCreate, Doctor as DoctorSchema,
    PatientCreate, Patient as PatientSchema,
    CleaningRecordCreate, CleaningRecord as CleaningRecordSchema,
    CleaningRecordBatchCreate, CleaningRecordBatchItem,
    FollowupCreate, Followup as FollowupSchema, FollowupSubmit,
    AppointmentCreate, Appointment as AppointmentSchema, AppointmentSubmit,
    Alert as AlertSchema, AlertResolve, AlertDetail,
    ClinicStats, CleaningRecordDetail,
)
from alert_engine import AlertEngine
from stats_service import StatsService

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="洁治后流失预警后端服务",
    description="面向连锁口腔机构运营主管的洁治后服务闭环追踪系统",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "service": "洁治后流失预警后端服务",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.post("/clinics/", response_model=ClinicSchema, tags=["基础数据"])
def create_clinic(clinic: ClinicCreate, db: Session = Depends(get_db)):
    db_clinic = Clinic(**clinic.model_dump())
    db.add(db_clinic)
    db.commit()
    db.refresh(db_clinic)
    return db_clinic


@app.get("/clinics/", response_model=List[ClinicSchema], tags=["基础数据"])
def list_clinics(db: Session = Depends(get_db)):
    return db.query(Clinic).all()


@app.post("/doctors/", response_model=DoctorSchema, tags=["基础数据"])
def create_doctor(doctor: DoctorCreate, db: Session = Depends(get_db)):
    clinic = db.query(Clinic).filter(Clinic.id == doctor.clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="门店不存在")
    db_doctor = Doctor(**doctor.model_dump())
    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)
    return db_doctor


@app.get("/doctors/", response_model=List[DoctorSchema], tags=["基础数据"])
def list_doctors(clinic_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Doctor)
    if clinic_id:
        query = query.filter(Doctor.clinic_id == clinic_id)
    return query.all()


@app.post("/patients/", response_model=PatientSchema, tags=["基础数据"])
def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    existing = db.query(Patient).filter(Patient.phone == patient.phone).first()
    if existing:
        existing.name = patient.name
        existing.patient_type = patient.patient_type
        db.commit()
        db.refresh(existing)
        return existing
    db_patient = Patient(**patient.model_dump())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient


@app.get("/patients/", response_model=List[PatientSchema], tags=["基础数据"])
def list_patients(
    phone: Optional[str] = None,
    patient_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Patient)
    if phone:
        query = query.filter(Patient.phone.contains(phone))
    if patient_type:
        query = query.filter(Patient.patient_type == patient_type)
    return query.all()


def _get_or_create_doctor(db: Session, clinic_id: int, doctor_name: str) -> Doctor:
    doctor = db.query(Doctor).filter(
        Doctor.clinic_id == clinic_id, Doctor.name == doctor_name
    ).first()
    if doctor:
        return doctor
    doctor = Doctor(clinic_id=clinic_id, name=doctor_name)
    db.add(doctor)
    db.flush()
    return doctor


def _get_or_create_patient(
    db: Session, name: str, phone: str, patient_type: str
) -> Patient:
    patient = db.query(Patient).filter(Patient.phone == phone).first()
    if patient:
        patient.name = name
        patient.patient_type = patient_type
        db.flush()
        return patient
    patient = Patient(name=name, phone=phone, patient_type=patient_type)
    db.add(patient)
    db.flush()
    return patient


@app.post("/cleaning-records/batch", tags=["数据提交"])
def batch_submit_cleaning_records(
    batch: CleaningRecordBatchCreate, db: Session = Depends(get_db)
):
    created_ids = []
    for item in batch.items:
        clinic = db.query(Clinic).filter(Clinic.id == item.clinic_id).first()
        if not clinic:
            continue
        doctor = _get_or_create_doctor(db, item.clinic_id, item.doctor_name)
        patient = _get_or_create_patient(
            db, item.patient_name, item.patient_phone, item.patient_type
        )
        record = CleaningRecord(
            clinic_id=item.clinic_id,
            doctor_id=doctor.id,
            patient_id=patient.id,
            cleaning_date=item.cleaning_date,
            notes=item.notes,
        )
        db.add(record)
        db.flush()
        created_ids.append(record.id)
    db.commit()
    engine = AlertEngine(db)
    new_alerts = engine.run_all_checks()
    return {
        "created_count": len(created_ids),
        "created_ids": created_ids,
        "new_alerts_generated": len(new_alerts),
    }


@app.post("/cleaning-records/", response_model=CleaningRecordSchema, tags=["数据提交"])
def create_cleaning_record(
    record: CleaningRecordCreate, db: Session = Depends(get_db)
):
    clinic = db.query(Clinic).filter(Clinic.id == record.clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="门店不存在")
    doctor = db.query(Doctor).filter(Doctor.id == record.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="医生不存在")
    patient = db.query(Patient).filter(Patient.id == record.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    db_record = CleaningRecord(**record.model_dump())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


@app.get("/cleaning-records/", response_model=List[CleaningRecordSchema], tags=["数据提交"])
def list_cleaning_records(
    clinic_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(CleaningRecord)
    if clinic_id:
        query = query.filter(CleaningRecord.clinic_id == clinic_id)
    if doctor_id:
        query = query.filter(CleaningRecord.doctor_id == doctor_id)
    if start_date:
        query = query.filter(CleaningRecord.cleaning_date >= start_date)
    if end_date:
        query = query.filter(CleaningRecord.cleaning_date <= end_date)
    return query.order_by(CleaningRecord.cleaning_date.desc()).all()


@app.post("/followups/", tags=["数据提交"])
def submit_followup(followup: FollowupSubmit, db: Session = Depends(get_db)):
    record = db.query(CleaningRecord).filter(
        CleaningRecord.id == followup.cleaning_record_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="洁治记录不存在")
    db_followup = Followup(
        cleaning_record_id=followup.cleaning_record_id,
        patient_id=record.patient_id,
        followup_time=followup.followup_time,
        operator=followup.operator,
        contact_method=followup.contact_method,
        patient_feedback=followup.patient_feedback,
        has_bleeding=followup.has_bleeding,
        has_sensitivity=followup.has_sensitivity,
        has_pain=followup.has_pain,
        other_symptoms=followup.other_symptoms,
        next_step=followup.next_step,
    )
    db.add(db_followup)
    db.flush()
    if followup.appointment_date:
        appointment = Appointment(
            cleaning_record_id=followup.cleaning_record_id,
            patient_id=record.patient_id,
            appointment_date=followup.appointment_date,
            appointment_type=followup.appointment_type or "复查",
        )
        db.add(appointment)
    db.commit()
    db.refresh(db_followup)
    engine = AlertEngine(db)
    engine.run_all_checks()
    return {"followup_id": db_followup.id, "message": "随访记录已提交"}


@app.get("/followups/", response_model=List[FollowupSchema], tags=["数据提交"])
def list_followups(
    cleaning_record_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Followup)
    if cleaning_record_id:
        query = query.filter(Followup.cleaning_record_id == cleaning_record_id)
    if patient_id:
        query = query.filter(Followup.patient_id == patient_id)
    return query.order_by(Followup.followup_time.desc()).all()


@app.post("/appointments/", tags=["数据提交"])
def submit_appointment(appointment: AppointmentSubmit, db: Session = Depends(get_db)):
    record = db.query(CleaningRecord).filter(
        CleaningRecord.id == appointment.cleaning_record_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="洁治记录不存在")
    db_appointment = Appointment(
        cleaning_record_id=appointment.cleaning_record_id,
        patient_id=record.patient_id,
        appointment_date=appointment.appointment_date,
        appointment_type=appointment.appointment_type,
        notes=appointment.notes,
    )
    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment)
    engine = AlertEngine(db)
    engine.run_all_checks()
    return {"appointment_id": db_appointment.id, "message": "预约记录已提交"}


@app.get("/appointments/", response_model=List[AppointmentSchema], tags=["数据提交"])
def list_appointments(
    cleaning_record_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Appointment)
    if cleaning_record_id:
        query = query.filter(Appointment.cleaning_record_id == cleaning_record_id)
    if patient_id:
        query = query.filter(Appointment.patient_id == patient_id)
    if status:
        query = query.filter(Appointment.status == status)
    return query.order_by(Appointment.appointment_date.desc()).all()


@app.post("/alerts/run-checks", tags=["预警管理"])
def run_alert_checks(db: Session = Depends(get_db)):
    engine = AlertEngine(db)
    new_alerts = engine.run_all_checks()
    return {
        "new_alerts_count": len(new_alerts),
        "alerts": [
            {"id": a.id, "type": a.alert_type, "title": a.title, "level": a.alert_level}
            for a in new_alerts
        ],
    }


@app.get("/alerts/", response_model=List[AlertSchema], tags=["预警管理"])
def list_alerts(
    clinic_id: Optional[int] = None,
    alert_type: Optional[str] = Query(None, description="未随访/未转化/高价值维护"),
    status: Optional[str] = Query(None, description="待处理/已处理"),
    db: Session = Depends(get_db)
):
    engine = AlertEngine(db)
    return engine.get_alerts_by_clinic(clinic_id, status, alert_type)


@app.get("/alerts/details/", tags=["预警管理"])
def list_alert_details(
    clinic_id: Optional[int] = None,
    alert_type: Optional[str] = None,
    status: Optional[str] = "待处理",
    db: Session = Depends(get_db)
):
    stats = StatsService(db)
    return stats.get_records_by_alert_type(clinic_id, alert_type, status)


@app.post("/alerts/{alert_id}/resolve", response_model=AlertSchema, tags=["预警管理"])
def resolve_alert(
    alert_id: int, data: AlertResolve, db: Session = Depends(get_db)
):
    engine = AlertEngine(db)
    alert = engine.resolve_alert(alert_id, data.resolved_note)
    if not alert:
        raise HTTPException(status_code=404, detail="预警记录不存在")
    return alert


@app.get("/stats/clinics/", response_model=List[ClinicStats], tags=["运营统计"])
def get_clinics_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    stats = StatsService(db)
    return stats.get_all_clinics_stats(start_date, end_date)


@app.get("/stats/clinics/{clinic_id}", response_model=ClinicStats, tags=["运营统计"])
def get_clinic_stats(
    clinic_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    stats = StatsService(db)
    return stats.get_clinic_stats(clinic_id, start_date, end_date)


@app.get("/stats/doctors/", tags=["运营统计"])
def get_doctors_stats(
    clinic_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    stats = StatsService(db)
    return stats.get_doctor_stats(clinic_id, start_date, end_date)


@app.get(
    "/cleaning-records/{record_id}/detail",
    response_model=CleaningRecordDetail,
    tags=["运营统计"]
)
def get_cleaning_record_detail(record_id: int, db: Session = Depends(get_db)):
    stats = StatsService(db)
    detail = stats.get_cleaning_record_detail(record_id)
    if not detail:
        raise HTTPException(status_code=404, detail="记录不存在")
    return detail
