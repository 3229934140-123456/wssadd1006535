from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from models import (
    CleaningRecord, Followup, Appointment, Alert,
    Clinic, Doctor, Patient
)
from schemas import ClinicStats, CleaningRecordDetail
from config import FOLLOWUP_DAYS_THRESHOLD, HIGH_VALUE_PATIENT_TYPES, FOLLOWUP_INTERVAL_DAYS


class StatsService:
    def __init__(self, db: Session):
        self.db = db

    def get_all_clinics_stats(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[ClinicStats]:
        clinics = self.db.query(Clinic).all()
        stats_list = []
        for clinic in clinics:
            stats = self.get_clinic_stats(clinic.id, start_date, end_date)
            stats_list.append(stats)
        return stats_list

    def get_clinic_stats(
        self, clinic_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> ClinicStats:
        clinic = self.db.query(Clinic).filter(Clinic.id == clinic_id).first()
        if not clinic:
            return ClinicStats(clinic_id=clinic_id, clinic_name="未知门店")

        query = self.db.query(CleaningRecord).filter(CleaningRecord.clinic_id == clinic_id)
        if start_date:
            query = query.filter(CleaningRecord.cleaning_date >= start_date)
        if end_date:
            query = query.filter(CleaningRecord.cleaning_date <= end_date)
        records = query.all()

        total_cleanings = len(records)
        followed_up_count = 0
        appointed_count = 0
        unfollowup_count = 0
        unconverted_count = 0
        high_value_overdue_count = 0
        overdue_count = 0

        today = date.today()
        threshold_date = today - timedelta(days=FOLLOWUP_DAYS_THRESHOLD)

        for record in records:
            has_followup = self.db.query(Followup).filter(
                Followup.cleaning_record_id == record.id
            ).first() is not None

            has_valid_appointment = self.db.query(Appointment).filter(
                and_(
                    Appointment.cleaning_record_id == record.id,
                    Appointment.status.in_(["待就诊", "已就诊"])
                )
            ).first() is not None

            if has_followup:
                followed_up_count += 1
            elif record.cleaning_date <= threshold_date:
                unfollowup_count += 1
                overdue_count += 1

            if has_valid_appointment:
                appointed_count += 1

            if has_followup and not has_valid_appointment:
                symptomatic_followup = self.db.query(Followup).filter(
                    and_(
                        Followup.cleaning_record_id == record.id,
                        (Followup.has_bleeding == True) |
                        (Followup.has_sensitivity == True) |
                        (Followup.has_pain == True)
                    )
                ).first()
                if symptomatic_followup:
                    unconverted_count += 1

            patient = self.db.query(Patient).filter(Patient.id == record.patient_id).first()
            if patient and patient.patient_type in HIGH_VALUE_PATIENT_TYPES:
                interval_days = FOLLOWUP_INTERVAL_DAYS.get(patient.patient_type, 30)
                hv_threshold = today - timedelta(days=interval_days)
                if record.cleaning_date <= hv_threshold and not has_valid_appointment:
                    high_value_overdue_count += 1
                    overdue_count += 1

        pending_alerts = self.db.query(Alert).filter(
            and_(Alert.clinic_id == clinic_id, Alert.status == "待处理")
        ).count()

        followup_rate = round(followed_up_count / total_cleanings * 100, 1) if total_cleanings > 0 else 0.0
        appointment_rate = round(appointed_count / total_cleanings * 100, 1) if total_cleanings > 0 else 0.0

        return ClinicStats(
            clinic_id=clinic.id,
            clinic_name=clinic.name,
            total_cleanings=total_cleanings,
            followed_up_count=followed_up_count,
            followup_rate=followup_rate,
            appointed_count=appointed_count,
            appointment_rate=appointment_rate,
            overdue_count=overdue_count,
            alert_pending_count=pending_alerts,
            unfollowup_count=unfollowup_count,
            unconverted_count=unconverted_count,
            high_value_overdue_count=high_value_overdue_count
        )

    def get_cleaning_record_detail(self, record_id: int) -> Optional[CleaningRecordDetail]:
        record = self.db.query(CleaningRecord).filter(CleaningRecord.id == record_id).first()
        if not record:
            return None

        patient = self.db.query(Patient).filter(Patient.id == record.patient_id).first()
        doctor = self.db.query(Doctor).filter(Doctor.id == record.doctor_id).first()
        clinic = self.db.query(Clinic).filter(Clinic.id == record.clinic_id).first()

        latest_followup = self.db.query(Followup).filter(
            Followup.cleaning_record_id == record.id
        ).order_by(Followup.followup_time.desc()).first()

        latest_alert = self.db.query(Alert).filter(
            Alert.cleaning_record_id == record.id
        ).order_by(Alert.created_at.desc()).first()

        responsible_person = None
        last_process_time = None
        if latest_alert:
            responsible_person = latest_alert.responsible_person
            last_process_time = latest_alert.resolved_at or latest_alert.created_at
        elif latest_followup:
            responsible_person = latest_followup.operator
            last_process_time = latest_followup.followup_time

        return CleaningRecordDetail(
            id=record.id,
            cleaning_date=record.cleaning_date,
            patient_name=patient.name if patient else "未知",
            patient_phone=patient.phone if patient else "",
            patient_type=patient.patient_type if patient else "常规洁治",
            doctor_name=doctor.name if doctor else "未分配",
            clinic_name=clinic.name if clinic else "未知门店",
            followups=record.followups,
            appointments=record.appointments,
            alerts=record.alerts,
            responsible_person=responsible_person,
            last_process_time=last_process_time
        )

    def get_records_by_alert_type(
        self, clinic_id: Optional[int] = None,
        alert_type: Optional[str] = None,
        status: Optional[str] = "待处理"
    ) -> List[Dict[str, Any]]:
        alerts_query = self.db.query(Alert)
        if clinic_id:
            alerts_query = alerts_query.filter(Alert.clinic_id == clinic_id)
        if alert_type:
            alerts_query = alerts_query.filter(Alert.alert_type == alert_type)
        if status:
            alerts_query = alerts_query.filter(Alert.status == status)

        alerts = alerts_query.order_by(Alert.created_at.desc()).all()
        result = []
        for alert in alerts:
            record = self.db.query(CleaningRecord).filter(
                CleaningRecord.id == alert.cleaning_record_id
            ).first()
            if not record:
                continue
            patient = self.db.query(Patient).filter(Patient.id == record.patient_id).first()
            doctor = self.db.query(Doctor).filter(Doctor.id == record.doctor_id).first()
            latest_followup = self.db.query(Followup).filter(
                Followup.cleaning_record_id == record.id
            ).order_by(Followup.followup_time.desc()).first()

            result.append({
                "alert_id": alert.id,
                "alert_type": alert.alert_type,
                "alert_level": alert.alert_level,
                "title": alert.title,
                "description": alert.description,
                "responsible_person": alert.responsible_person,
                "status": alert.status,
                "created_at": alert.created_at,
                "cleaning_record_id": record.id,
                "cleaning_date": record.cleaning_date,
                "patient_name": patient.name if patient else "未知",
                "patient_phone": patient.phone if patient else "",
                "patient_type": patient.patient_type if patient else "常规洁治",
                "doctor_name": doctor.name if doctor else "未分配",
                "last_followup_time": latest_followup.followup_time if latest_followup else None,
                "last_followup_operator": latest_followup.operator if latest_followup else None,
            })
        return result

    def get_doctor_stats(
        self, clinic_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        query = self.db.query(Doctor)
        if clinic_id:
            query = query.filter(Doctor.clinic_id == clinic_id)
        doctors = query.all()

        result = []
        for doctor in doctors:
            records_query = self.db.query(CleaningRecord).filter(
                CleaningRecord.doctor_id == doctor.id
            )
            if start_date:
                records_query = records_query.filter(CleaningRecord.cleaning_date >= start_date)
            if end_date:
                records_query = records_query.filter(CleaningRecord.cleaning_date <= end_date)
            records = records_query.all()

            total = len(records)
            followed = 0
            appointed = 0
            for r in records:
                if self.db.query(Followup).filter(Followup.cleaning_record_id == r.id).first():
                    followed += 1
                if self.db.query(Appointment).filter(
                    and_(
                        Appointment.cleaning_record_id == r.id,
                        Appointment.status.in_(["待就诊", "已就诊"])
                    )
                ).first():
                    appointed += 1

            result.append({
                "doctor_id": doctor.id,
                "doctor_name": doctor.name,
                "title": doctor.title,
                "clinic_name": doctor.clinic.name if doctor.clinic else "",
                "total_cleanings": total,
                "followed_up_count": followed,
                "followup_rate": round(followed / total * 100, 1) if total > 0 else 0.0,
                "appointed_count": appointed,
                "appointment_rate": round(appointed / total * 100, 1) if total > 0 else 0.0,
            })
        return result
