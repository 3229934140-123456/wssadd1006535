from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models import (
    CleaningRecord, Followup, Appointment, Alert,
    Clinic, Doctor, Patient
)
from config import (
    FOLLOWUP_DAYS_THRESHOLD,
    HIGH_VALUE_PATIENT_TYPES,
    FOLLOWUP_INTERVAL_DAYS,
    SYMPTOMS_REQUIRING_REVIEW
)


class AlertEngine:
    def __init__(self, db: Session):
        self.db = db

    def run_all_checks(self) -> List[Alert]:
        new_alerts = []
        new_alerts.extend(self.check_unfollowed())
        new_alerts.extend(self.check_unconverted())
        new_alerts.extend(self.check_high_value_overdue())
        self.db.commit()
        return new_alerts

    def check_unfollowed(self) -> List[Alert]:
        threshold_date = date.today() - timedelta(days=FOLLOWUP_DAYS_THRESHOLD)
        records = (
            self.db.query(CleaningRecord)
            .filter(CleaningRecord.cleaning_date <= threshold_date)
            .all()
        )
        new_alerts = []
        for record in records:
            has_followup = self.db.query(Followup).filter(
                Followup.cleaning_record_id == record.id
            ).first()
            if has_followup:
                continue
            existing_alert = self.db.query(Alert).filter(
                and_(
                    Alert.cleaning_record_id == record.id,
                    Alert.alert_type == "未随访",
                    Alert.status == "待处理"
                )
            ).first()
            if existing_alert:
                continue
            patient = self.db.query(Patient).filter(Patient.id == record.patient_id).first()
            doctor = self.db.query(Doctor).filter(Doctor.id == record.doctor_id).first()
            clinic = self.db.query(Clinic).filter(Clinic.id == record.clinic_id).first()
            days_passed = (date.today() - record.cleaning_date).days
            alert = Alert(
                clinic_id=record.clinic_id,
                cleaning_record_id=record.id,
                alert_type="未随访",
                alert_level="high",
                title=f"洁治后{days_passed}天未随访 - {patient.name if patient else '未知患者'}",
                description=(
                    f"患者{patient.name if patient else '未知'}"
                    f"（{patient.phone if patient else '无电话'}）于"
                    f"{record.cleaning_date.strftime('%Y-%m-%d')}完成洁治，"
                    f"已超过{FOLLOWUP_DAYS_THRESHOLD}天未进行随访。"
                    f"责任医生：{doctor.name if doctor else '未分配'}。"
                ),
                responsible_person=clinic.store_manager if clinic and clinic.store_manager else "门店店长",
                status="待处理"
            )
            self.db.add(alert)
            self.db.flush()
            new_alerts.append(alert)
        return new_alerts

    def check_unconverted(self) -> List[Alert]:
        new_alerts = []
        followups = (
            self.db.query(Followup)
            .filter(
                or_(
                    Followup.has_bleeding == True,
                    Followup.has_sensitivity == True,
                    Followup.has_pain == True
                )
            )
            .all()
        )
        processed_records = set()
        for followup in followups:
            if followup.cleaning_record_id in processed_records:
                continue
            processed_records.add(followup.cleaning_record_id)
            has_appointment = self.db.query(Appointment).filter(
                and_(
                    Appointment.cleaning_record_id == followup.cleaning_record_id,
                    Appointment.status.in_(["待就诊", "已就诊"])
                )
            ).first()
            if has_appointment:
                continue
            existing_alert = self.db.query(Alert).filter(
                and_(
                    Alert.cleaning_record_id == followup.cleaning_record_id,
                    Alert.alert_type == "未转化",
                    Alert.status == "待处理"
                )
            ).first()
            if existing_alert:
                continue
            record = self.db.query(CleaningRecord).filter(
                CleaningRecord.id == followup.cleaning_record_id
            ).first()
            if not record:
                continue
            patient = self.db.query(Patient).filter(Patient.id == record.patient_id).first()
            symptoms = []
            if followup.has_bleeding:
                symptoms.append("牙龈出血")
            if followup.has_sensitivity:
                symptoms.append("牙齿敏感")
            if followup.has_pain:
                symptoms.append("牙龈肿痛")
            if followup.other_symptoms:
                symptoms.append(followup.other_symptoms)
            alert = Alert(
                clinic_id=record.clinic_id,
                cleaning_record_id=record.id,
                alert_type="未转化",
                alert_level="medium",
                title=f"有症状未转化 - {patient.name if patient else '未知患者'}",
                description=(
                    f"患者{patient.name if patient else '未知'}"
                    f"（{patient.phone if patient else '无电话'}）随访反馈："
                    f"{'、'.join(symptoms)}，但尚未安排复查预约。"
                    f"随访人：{followup.operator}，随访时间："
                    f"{followup.followup_time.strftime('%Y-%m-%d %H:%M')}。"
                    f"请客服进行二次关怀跟进。"
                ),
                responsible_person="客服团队",
                status="待处理"
            )
            self.db.add(alert)
            self.db.flush()
            new_alerts.append(alert)
        return new_alerts

    def check_high_value_overdue(self) -> List[Alert]:
        new_alerts = []
        today = date.today()
        for patient_type in HIGH_VALUE_PATIENT_TYPES:
            interval_days = FOLLOWUP_INTERVAL_DAYS.get(patient_type, 30)
            threshold_date = today - timedelta(days=interval_days)
            records = (
                self.db.query(CleaningRecord)
                .join(Patient, CleaningRecord.patient_id == Patient.id)
                .filter(
                    Patient.patient_type == patient_type,
                    CleaningRecord.cleaning_date <= threshold_date
                )
                .all()
            )
            for record in records:
                valid_appointment = self.db.query(Appointment).filter(
                    and_(
                        Appointment.cleaning_record_id == record.id,
                        Appointment.status.in_(["待就诊", "已就诊"])
                    )
                ).first()
                if valid_appointment:
                    continue
                existing_alert = self.db.query(Alert).filter(
                    and_(
                        Alert.cleaning_record_id == record.id,
                        Alert.alert_type == "高价值维护",
                        Alert.status == "待处理"
                    )
                ).first()
                if existing_alert:
                    continue
                patient = self.db.query(Patient).filter(Patient.id == record.patient_id).first()
                doctor = self.db.query(Doctor).filter(Doctor.id == record.doctor_id).first()
                days_passed = (today - record.cleaning_date).days
                alert = Alert(
                    clinic_id=record.clinic_id,
                    cleaning_record_id=record.id,
                    alert_type="高价值维护",
                    alert_level="high",
                    title=f"【重点名单】{patient_type}患者到期未预约 - {patient.name if patient else '未知'}",
                    description=(
                        f"{patient_type}患者{patient.name if patient else '未知'}"
                        f"（{patient.phone if patient else '无电话'}）"
                        f"上次洁治日期：{record.cleaning_date.strftime('%Y-%m-%d')}，"
                        f"已逾{days_passed}天未预约维护。"
                        f"按标准应每{interval_days}天复诊一次。"
                        f"责任医生：{doctor.name if doctor else '未分配'}。"
                    ),
                    responsible_person=doctor.name if doctor else "主治医生",
                    status="待处理"
                )
                self.db.add(alert)
                self.db.flush()
                new_alerts.append(alert)
        return new_alerts

    def resolve_alert(self, alert_id: int, resolved_note: Optional[str] = None) -> Optional[Alert]:
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return None
        alert.status = "已处理"
        alert.resolved_at = datetime.utcnow()
        alert.resolved_note = resolved_note
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def get_alerts_by_clinic(
        self, clinic_id: Optional[int] = None,
        status: Optional[str] = None,
        alert_type: Optional[str] = None
    ) -> List[Alert]:
        query = self.db.query(Alert)
        if clinic_id:
            query = query.filter(Alert.clinic_id == clinic_id)
        if status:
            query = query.filter(Alert.status == status)
        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)
        return query.order_by(Alert.created_at.desc()).all()
