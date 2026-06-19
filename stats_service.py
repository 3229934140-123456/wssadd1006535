from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from models import (
    CleaningRecord, Followup, Appointment, Alert, AlertAction,
    Clinic, Doctor, Patient
)
from schemas import (
    ClinicStats, CleaningRecordDetail, OverviewResponse, OverviewSummary,
    OverviewRankingItem, PatientAlertHistory, PatientActionHistory,
    HighValueExportResponse, HighValueExportItem,
    TrendResponse, TrendDataPoint
)
from config import (
    HIGH_VALUE_PATIENT_TYPES,
    get_followup_threshold,
    get_interval_days
)


class StatsService:
    def __init__(self, db: Session):
        self.db = db

    def get_all_clinics_stats(
        self, start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        clinic_id: Optional[int] = None,
        doctor_id: Optional[int] = None,
        patient_type: Optional[str] = None
    ) -> List[ClinicStats]:
        query = self.db.query(Clinic)
        if clinic_id:
            query = query.filter(Clinic.id == clinic_id)
        clinics = query.all()
        stats_list = []
        for clinic in clinics:
            stats = self.get_clinic_stats(
                clinic.id, start_date, end_date, doctor_id, patient_type
            )
            stats_list.append(stats)
        return stats_list

    def get_clinic_stats(
        self, clinic_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        doctor_id: Optional[int] = None,
        patient_type: Optional[str] = None
    ) -> ClinicStats:
        clinic = self.db.query(Clinic).filter(Clinic.id == clinic_id).first()
        if not clinic:
            return ClinicStats(clinic_id=clinic_id, clinic_name="未知门店")

        query = self.db.query(CleaningRecord).filter(CleaningRecord.clinic_id == clinic_id)
        if start_date:
            query = query.filter(CleaningRecord.cleaning_date >= start_date)
        if end_date:
            query = query.filter(CleaningRecord.cleaning_date <= end_date)
        if doctor_id:
            query = query.filter(CleaningRecord.doctor_id == doctor_id)
        if patient_type:
            query = query.join(Patient).filter(Patient.patient_type == patient_type)
        records = query.all()

        total_cleanings = len(records)
        followed_up_count = 0
        appointed_count = 0
        unfollowup_count = 0
        unconverted_count = 0
        high_value_overdue_count = 0
        overdue_count = 0

        today = date.today()

        for record in records:
            threshold = get_followup_threshold(self.db, record.clinic_id)
            threshold_date = today - timedelta(days=threshold)

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
                interval_days = get_interval_days(self.db, record.clinic_id, patient.patient_type)
                hv_threshold = today - timedelta(days=interval_days)
                if record.cleaning_date <= hv_threshold and not has_valid_appointment:
                    high_value_overdue_count += 1
                    overdue_count += 1

        pending_alerts_query = self.db.query(Alert).filter(
            and_(Alert.clinic_id == clinic_id, Alert.status == "待处理")
        )
        if doctor_id or patient_type or start_date or end_date:
            pending_alerts_query = pending_alerts_query.join(CleaningRecord).filter(
                CleaningRecord.id == Alert.cleaning_record_id
            )
            if doctor_id:
                pending_alerts_query = pending_alerts_query.filter(
                    CleaningRecord.doctor_id == doctor_id
                )
            if patient_type:
                pending_alerts_query = pending_alerts_query.join(Patient).filter(
                    Patient.id == CleaningRecord.patient_id,
                    Patient.patient_type == patient_type
                )
            if start_date:
                pending_alerts_query = pending_alerts_query.filter(
                    CleaningRecord.cleaning_date >= start_date
                )
            if end_date:
                pending_alerts_query = pending_alerts_query.filter(
                    CleaningRecord.cleaning_date <= end_date
                )
        pending_alerts = pending_alerts_query.count()

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

    def get_overview(
        self, start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        clinic_id: Optional[int] = None,
        doctor_id: Optional[int] = None,
        patient_type: Optional[str] = None
    ) -> OverviewResponse:
        all_stats = self.get_all_clinics_stats(
            start_date, end_date, clinic_id, doctor_id, patient_type
        )

        total_clinics = len([s for s in all_stats if s.total_cleanings > 0])
        total_doctors = self.db.query(Doctor).filter(
            Doctor.clinic_id.in_([s.clinic_id for s in all_stats]) if clinic_id else True
        ).count() if not doctor_id else 1
        total_patients_query = self.db.query(func.count(func.distinct(CleaningRecord.patient_id)))
        if start_date:
            total_patients_query = total_patients_query.filter(CleaningRecord.cleaning_date >= start_date)
        if end_date:
            total_patients_query = total_patients_query.filter(CleaningRecord.cleaning_date <= end_date)
        if clinic_id:
            total_patients_query = total_patients_query.filter(CleaningRecord.clinic_id == clinic_id)
        if doctor_id:
            total_patients_query = total_patients_query.filter(CleaningRecord.doctor_id == doctor_id)
        if patient_type:
            total_patients_query = total_patients_query.join(Patient).filter(
                Patient.patient_type == patient_type
            )
        total_patients = total_patients_query.scalar() or 0

        total_cleanings = sum(s.total_cleanings for s in all_stats)
        total_followed = sum(s.followed_up_count for s in all_stats)
        total_appointed = sum(s.appointed_count for s in all_stats)
        total_overdue = sum(s.overdue_count for s in all_stats)
        total_alerts_pending = sum(s.alert_pending_count for s in all_stats)
        total_unfollowup = sum(s.unfollowup_count for s in all_stats)
        total_unconverted = sum(s.unconverted_count for s in all_stats)
        total_high_value = sum(s.high_value_overdue_count for s in all_stats)

        summary = OverviewSummary(
            total_clinics=total_clinics,
            total_doctors=total_doctors,
            total_patients=total_patients,
            total_cleanings=total_cleanings,
            overall_followup_rate=round(total_followed / total_cleanings * 100, 1) if total_cleanings > 0 else 0.0,
            overall_appointment_rate=round(total_appointed / total_cleanings * 100, 1) if total_cleanings > 0 else 0.0,
            total_overdue=total_overdue,
            total_alerts_pending=total_alerts_pending,
            unfollowup_count=total_unfollowup,
            unconverted_count=total_unconverted,
            high_value_overdue_count=total_high_value
        )

        clinic_ranking = sorted(
            [
                OverviewRankingItem(
                    id=s.clinic_id,
                    name=s.clinic_name,
                    total_cleanings=s.total_cleanings,
                    followed_up_count=s.followed_up_count,
                    appointed_count=s.appointed_count,
                    followup_rate=s.followup_rate,
                    appointment_rate=s.appointment_rate,
                    overdue_count=s.overdue_count,
                    unfollowup_count=s.unfollowup_count,
                    unconverted_count=s.unconverted_count,
                    high_value_overdue_count=s.high_value_overdue_count,
                    alert_pending_count=s.alert_pending_count,
                    alert_count=s.alert_pending_count
                )
                for s in all_stats if s.total_cleanings > 0
            ],
            key=lambda x: x.overdue_count,
            reverse=True
        )

        doctor_stats = self.get_doctor_stats(clinic_id, start_date, end_date, doctor_id, patient_type)
        doctor_ranking = sorted(
            [
                OverviewRankingItem(
                    id=d["doctor_id"],
                    name=d["doctor_name"],
                    total_cleanings=d["total_cleanings"],
                    followed_up_count=d["followed_up_count"],
                    appointed_count=d["appointed_count"],
                    followup_rate=d["followup_rate"],
                    appointment_rate=d["appointment_rate"],
                    overdue_count=d["overdue_count"],
                    unfollowup_count=d["unfollowup_count"],
                    unconverted_count=d["unconverted_count"],
                    high_value_overdue_count=d["high_value_overdue_count"],
                    alert_pending_count=d["alert_pending_count"],
                    alert_count=d["alert_pending_count"]
                )
                for d in doctor_stats if d["total_cleanings"] > 0
            ],
            key=lambda x: x.overdue_count,
            reverse=True
        )

        patient_type_breakdown = []
        pt_query = self.db.query(
            Patient.patient_type,
            func.count(CleaningRecord.id).label("total")
        ).join(CleaningRecord, Patient.id == CleaningRecord.patient_id)
        if start_date:
            pt_query = pt_query.filter(CleaningRecord.cleaning_date >= start_date)
        if end_date:
            pt_query = pt_query.filter(CleaningRecord.cleaning_date <= end_date)
        if clinic_id:
            pt_query = pt_query.filter(CleaningRecord.clinic_id == clinic_id)
        if doctor_id:
            pt_query = pt_query.filter(CleaningRecord.doctor_id == doctor_id)
        if patient_type:
            pt_query = pt_query.filter(Patient.patient_type == patient_type)
        pt_data = pt_query.group_by(Patient.patient_type).all()

        for pt, total in pt_data:
            pt_records_query = self.db.query(CleaningRecord).join(Patient).filter(
                Patient.patient_type == pt
            )
            if start_date:
                pt_records_query = pt_records_query.filter(CleaningRecord.cleaning_date >= start_date)
            if end_date:
                pt_records_query = pt_records_query.filter(CleaningRecord.cleaning_date <= end_date)
            if clinic_id:
                pt_records_query = pt_records_query.filter(CleaningRecord.clinic_id == clinic_id)
            if doctor_id:
                pt_records_query = pt_records_query.filter(CleaningRecord.doctor_id == doctor_id)
            pt_records = pt_records_query.all()

            followed = 0
            appointed = 0
            for r in pt_records:
                if self.db.query(Followup).filter(Followup.cleaning_record_id == r.id).first():
                    followed += 1
                if self.db.query(Appointment).filter(
                    and_(
                        Appointment.cleaning_record_id == r.id,
                        Appointment.status.in_(["待就诊", "已就诊"])
                    )
                ).first():
                    appointed += 1

            overdue_count_pt = 0
            unfollowup_pt = 0
            unconverted_pt = 0
            high_value_pt = 0
            alert_pending_pt = 0
            today = date.today()
            for r in pt_records:
                threshold = get_followup_threshold(self.db, r.clinic_id)
                threshold_date = today - timedelta(days=threshold)
                has_followup = self.db.query(Followup).filter(
                    Followup.cleaning_record_id == r.id
                ).first() is not None
                has_valid_appointment = self.db.query(Appointment).filter(
                    and_(
                        Appointment.cleaning_record_id == r.id,
                        Appointment.status.in_(["待就诊", "已就诊"])
                    )
                ).first() is not None
                if not has_followup and r.cleaning_date <= threshold_date:
                    unfollowup_pt += 1
                    overdue_count_pt += 1
                if has_followup and not has_valid_appointment:
                    symptomatic = self.db.query(Followup).filter(
                        and_(
                            Followup.cleaning_record_id == r.id,
                            (Followup.has_bleeding == True) |
                            (Followup.has_sensitivity == True) |
                            (Followup.has_pain == True)
                        )
                    ).first()
                    if symptomatic:
                        unconverted_pt += 1
                pt_obj = self.db.query(Patient).filter(Patient.id == r.patient_id).first()
                if pt_obj and pt_obj.patient_type in HIGH_VALUE_PATIENT_TYPES:
                    interval_days = get_interval_days(self.db, r.clinic_id, pt_obj.patient_type)
                    hv_threshold = today - timedelta(days=interval_days)
                    if r.cleaning_date <= hv_threshold and not has_valid_appointment:
                        high_value_pt += 1
                        overdue_count_pt += 1
            pt_alert_query = self.db.query(Alert).filter(
                Alert.status == "待处理"
            ).join(CleaningRecord).join(Patient).filter(
                Patient.patient_type == pt
            )
            if start_date:
                pt_alert_query = pt_alert_query.filter(CleaningRecord.cleaning_date >= start_date)
            if end_date:
                pt_alert_query = pt_alert_query.filter(CleaningRecord.cleaning_date <= end_date)
            if clinic_id:
                pt_alert_query = pt_alert_query.filter(CleaningRecord.clinic_id == clinic_id)
            if doctor_id:
                pt_alert_query = pt_alert_query.filter(CleaningRecord.doctor_id == doctor_id)
            alert_pending_pt = pt_alert_query.count()

            patient_type_breakdown.append({
                "patient_type": pt,
                "total_cleanings": total,
                "followed_up_count": followed,
                "appointed_count": appointed,
                "followup_rate": round(followed / total * 100, 1) if total > 0 else 0.0,
                "appointment_rate": round(appointed / total * 100, 1) if total > 0 else 0.0,
                "overdue_count": overdue_count_pt,
                "unfollowup_count": unfollowup_pt,
                "unconverted_count": unconverted_pt,
                "high_value_overdue_count": high_value_pt,
                "alert_pending_count": alert_pending_pt,
            })

        return OverviewResponse(
            summary=summary,
            clinic_ranking=clinic_ranking,
            doctor_ranking=doctor_ranking,
            patient_type_breakdown=patient_type_breakdown,
            date_range={"start_date": start_date, "end_date": end_date}
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
                "resolved_at": alert.resolved_at,
                "resolved_by": alert.resolved_by,
                "auto_resolved": alert.auto_resolved,
                "auto_resolved_reason": alert.auto_resolved_reason,
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
        end_date: Optional[date] = None,
        doctor_id: Optional[int] = None,
        patient_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = self.db.query(Doctor)
        if clinic_id:
            query = query.filter(Doctor.clinic_id == clinic_id)
        if doctor_id:
            query = query.filter(Doctor.id == doctor_id)
        doctors = query.all()

        result = []
        today = date.today()
        for doctor in doctors:
            records_query = self.db.query(CleaningRecord).filter(
                CleaningRecord.doctor_id == doctor.id
            )
            if start_date:
                records_query = records_query.filter(CleaningRecord.cleaning_date >= start_date)
            if end_date:
                records_query = records_query.filter(CleaningRecord.cleaning_date <= end_date)
            if patient_type:
                records_query = records_query.join(Patient).filter(Patient.patient_type == patient_type)
            records = records_query.all()

            total = len(records)
            followed = 0
            appointed = 0
            unfollowup_count = 0
            unconverted_count = 0
            high_value_overdue_count = 0
            overdue_count = 0

            for r in records:
                threshold = get_followup_threshold(self.db, r.clinic_id)
                threshold_date = today - timedelta(days=threshold)

                has_followup = self.db.query(Followup).filter(
                    Followup.cleaning_record_id == r.id
                ).first() is not None

                has_valid_appointment = self.db.query(Appointment).filter(
                    and_(
                        Appointment.cleaning_record_id == r.id,
                        Appointment.status.in_(["待就诊", "已就诊"])
                    )
                ).first() is not None

                if has_followup:
                    followed += 1
                elif r.cleaning_date <= threshold_date:
                    unfollowup_count += 1
                    overdue_count += 1

                if has_valid_appointment:
                    appointed += 1

                if has_followup and not has_valid_appointment:
                    symptomatic_followup = self.db.query(Followup).filter(
                        and_(
                            Followup.cleaning_record_id == r.id,
                            (Followup.has_bleeding == True) |
                            (Followup.has_sensitivity == True) |
                            (Followup.has_pain == True)
                        )
                    ).first()
                    if symptomatic_followup:
                        unconverted_count += 1

                pt = self.db.query(Patient).filter(Patient.id == r.patient_id).first()
                if pt and pt.patient_type in HIGH_VALUE_PATIENT_TYPES:
                    interval_days = get_interval_days(self.db, r.clinic_id, pt.patient_type)
                    hv_threshold = today - timedelta(days=interval_days)
                    if r.cleaning_date <= hv_threshold and not has_valid_appointment:
                        high_value_overdue_count += 1
                        overdue_count += 1

            pending_alerts_query = self.db.query(Alert).filter(
                and_(Alert.status == "待处理")
            ).join(CleaningRecord).filter(
                CleaningRecord.id == Alert.cleaning_record_id,
                CleaningRecord.doctor_id == doctor.id
            )
            if start_date:
                pending_alerts_query = pending_alerts_query.filter(CleaningRecord.cleaning_date >= start_date)
            if end_date:
                pending_alerts_query = pending_alerts_query.filter(CleaningRecord.cleaning_date <= end_date)
            if patient_type:
                pending_alerts_query = pending_alerts_query.join(Patient).filter(
                    Patient.id == CleaningRecord.patient_id,
                    Patient.patient_type == patient_type
                )
            alert_pending_count = pending_alerts_query.count()

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
                "overdue_count": overdue_count,
                "unfollowup_count": unfollowup_count,
                "unconverted_count": unconverted_count,
                "high_value_overdue_count": high_value_overdue_count,
                "alert_pending_count": alert_pending_count,
            })
        return result

    def get_patient_alert_history(self, patient_id: int) -> Optional[PatientAlertHistory]:
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return None

        alerts = (
            self.db.query(Alert)
            .join(CleaningRecord, Alert.cleaning_record_id == CleaningRecord.id)
            .filter(CleaningRecord.patient_id == patient_id)
            .order_by(Alert.created_at.desc())
            .all()
        )

        total_alerts = len(alerts)
        pending_alerts = sum(1 for a in alerts if a.status == "待处理")
        resolved_alerts = sum(1 for a in alerts if a.status == "已处理")

        actions = (
            self.db.query(AlertAction)
            .filter(AlertAction.patient_id == patient_id)
            .order_by(AlertAction.action_time.desc())
            .limit(20)
            .all()
        )

        action_history = []
        for action in actions:
            alert = self.db.query(Alert).filter(Alert.id == action.alert_id).first()
            action_history.append(PatientActionHistory(
                action_id=action.id,
                alert_id=action.alert_id,
                alert_type=alert.alert_type if alert else "未知",
                alert_title=alert.title if alert else "未知",
                action_type=action.action_type,
                action_time=action.action_time,
                operator=action.operator,
                contact_method=action.contact_method,
                content=action.content,
                close_reason=action.close_reason
            ))

        return PatientAlertHistory(
            patient_id=patient.id,
            patient_name=patient.name,
            patient_phone=patient.phone,
            patient_type=patient.patient_type,
            total_alerts=total_alerts,
            pending_alerts=pending_alerts,
            resolved_alerts=resolved_alerts,
            actions=action_history
        )

    def export_high_value_list(
        self, clinic_id: Optional[int] = None
    ) -> HighValueExportResponse:
        clinic_name = None
        if clinic_id:
            clinic = self.db.query(Clinic).filter(Clinic.id == clinic_id).first()
            if clinic:
                clinic_name = clinic.name

        alerts_query = self.db.query(Alert).filter(
            and_(
                Alert.status == "待处理",
                Alert.alert_type.in_(["高价值维护", "未转化"])
            )
        )
        if clinic_id:
            alerts_query = alerts_query.filter(Alert.clinic_id == clinic_id)

        alerts = alerts_query.order_by(Alert.alert_type, Alert.created_at.desc()).all()

        items = []
        today = date.today()
        high_value_count = 0
        unconverted_count = 0

        for alert in alerts:
            record = self.db.query(CleaningRecord).filter(
                CleaningRecord.id == alert.cleaning_record_id
            ).first()
            if not record:
                continue
            patient = self.db.query(Patient).filter(Patient.id == record.patient_id).first()
            doctor = self.db.query(Doctor).filter(Doctor.id == record.doctor_id).first()
            clinic = self.db.query(Clinic).filter(Clinic.id == record.clinic_id).first()
            latest_followup = self.db.query(Followup).filter(
                Followup.cleaning_record_id == record.id
            ).order_by(Followup.followup_time.desc()).first()

            overdue_days = (today - record.cleaning_date).days

            if alert.alert_type == "高价值维护":
                high_value_count += 1
            else:
                unconverted_count += 1

            items.append(HighValueExportItem(
                clinic_name=clinic.name if clinic else "未知门店",
                patient_name=patient.name if patient else "未知",
                patient_phone=patient.phone if patient else "",
                patient_type=patient.patient_type if patient else "常规洁治",
                doctor_name=doctor.name if doctor else "未分配",
                cleaning_date=record.cleaning_date,
                overdue_days=overdue_days,
                alert_type=alert.alert_type,
                alert_title=alert.title,
                status=alert.status,
                responsible_person=alert.responsible_person,
                assignee=alert.assignee,
                deadline=alert.deadline,
                resolved_by=alert.resolved_by,
                resolved_at=alert.resolved_at,
                resolved_detail=alert.resolved_detail,
                auto_resolved=alert.auto_resolved,
                last_followup_time=latest_followup.followup_time if latest_followup else None,
                last_followup_content=latest_followup.patient_feedback if latest_followup else None
            ))

        return HighValueExportResponse(
            clinic_id=clinic_id,
            clinic_name=clinic_name,
            export_time=datetime.utcnow(),
            total_count=len(items),
            high_value_count=high_value_count,
            unconverted_count=unconverted_count,
            items=items
        )

    def get_trend(
        self,
        period_type: str = "day",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        clinic_id: Optional[int] = None,
        compare_clinic: bool = False
    ) -> TrendResponse:
        today = date.today()
        if end_date:
            end_date = min(end_date, today)
        else:
            end_date = today
        if not start_date:
            if period_type == "day":
                start_date = end_date - timedelta(days=13)
            else:
                start_date = end_date - timedelta(days=41)
        else:
            start_date = min(start_date, end_date)

        periods = []
        current = start_date
        if period_type == "day":
            while current <= end_date:
                periods.append((current, current, current))
                current += timedelta(days=1)
        else:
            while current <= end_date:
                week_end = min(current + timedelta(days=6), end_date)
                periods.append((current, current, week_end))
                current = week_end + timedelta(days=1)

        data_points = []
        by_clinic_data = {}

        clinics_for_compare = []
        if compare_clinic:
            q = self.db.query(Clinic)
            if clinic_id:
                q = q.filter(Clinic.id == clinic_id)
            clinics_for_compare = q.all()
            for c in clinics_for_compare:
                by_clinic_data[c.id] = []

        for period_start, display_start, period_end in periods:
            if period_type == "day":
                period_label = period_start.strftime("%Y-%m-%d")
            else:
                period_label = f"{period_start.strftime('%m-%d')}~{period_end.strftime('%m-%d')}"

            overall_query = self.db.query(Alert)
            if clinic_id:
                overall_query = overall_query.filter(Alert.clinic_id == clinic_id)

            created_alerts = overall_query.filter(
                func.date(Alert.created_at) >= period_start,
                func.date(Alert.created_at) <= period_end
            ).count()

            resolved_alerts_query = overall_query.filter(
                Alert.resolved_at.isnot(None)
            ).filter(
                func.date(Alert.resolved_at) >= period_start,
                func.date(Alert.resolved_at) <= period_end
            )
            resolved_count = resolved_alerts_query.count()
            auto_resolved_count = overall_query.filter(
                Alert.auto_resolved == True,
                Alert.resolved_at.isnot(None)
            ).filter(
                func.date(Alert.resolved_at) >= period_start,
                func.date(Alert.resolved_at) <= period_end
            ).count()

            resolve_hours_list = []
            for a in overall_query.filter(
                Alert.resolved_at.isnot(None)
            ).filter(
                func.date(Alert.resolved_at) >= period_start,
                func.date(Alert.resolved_at) <= period_end
            ).all():
                delta = a.resolved_at - a.created_at
                resolve_hours_list.append(delta.total_seconds() / 3600)
            avg_resolve_hours = round(sum(resolve_hours_list) / len(resolve_hours_list), 1) if resolve_hours_list else 0.0

            pending_count = overall_query.filter(
                Alert.status == "待处理"
            ).filter(
                func.date(Alert.created_at) <= period_end
            ).count()

            dp = TrendDataPoint(
                period=period_label,
                start_date=display_start,
                end_date=period_end,
                new_alerts=created_alerts,
                resolved_alerts=resolved_count,
                auto_resolved_count=auto_resolved_count,
                auto_resolve_rate=round(auto_resolved_count / resolved_count * 100, 1) if resolved_count > 0 else 0.0,
                avg_resolve_hours=avg_resolve_hours,
                pending_alerts=pending_count
            )
            data_points.append(dp)

            if compare_clinic:
                for c in clinics_for_compare:
                    c_created = self.db.query(Alert).filter(
                        Alert.clinic_id == c.id,
                        func.date(Alert.created_at) >= period_start,
                        func.date(Alert.created_at) <= period_end
                    ).count()
                    c_resolved_query = self.db.query(Alert).filter(
                        Alert.clinic_id == c.id,
                        Alert.resolved_at.isnot(None)
                    ).filter(
                        func.date(Alert.resolved_at) >= period_start,
                        func.date(Alert.resolved_at) <= period_end
                    )
                    c_resolved = c_resolved_query.count()
                    c_auto = self.db.query(Alert).filter(
                        Alert.clinic_id == c.id,
                        Alert.auto_resolved == True,
                        Alert.resolved_at.isnot(None)
                    ).filter(
                        func.date(Alert.resolved_at) >= period_start,
                        func.date(Alert.resolved_at) <= period_end
                    ).count()
                    c_hours = []
                    for a in self.db.query(Alert).filter(
                        Alert.clinic_id == c.id,
                        Alert.resolved_at.isnot(None)
                    ).filter(
                        func.date(Alert.resolved_at) >= period_start,
                        func.date(Alert.resolved_at) <= period_end
                    ).all():
                        delta = a.resolved_at - a.created_at
                        c_hours.append(delta.total_seconds() / 3600)
                    c_avg = round(sum(c_hours) / len(c_hours), 1) if c_hours else 0.0
                    c_pending = self.db.query(Alert).filter(
                        Alert.clinic_id == c.id,
                        Alert.status == "待处理"
                    ).filter(
                        func.date(Alert.created_at) <= period_end
                    ).count()
                    by_clinic_data[c.id].append(TrendDataPoint(
                        period=period_label,
                        start_date=display_start,
                        end_date=period_end,
                        new_alerts=c_created,
                        resolved_alerts=c_resolved,
                        auto_resolved_count=c_auto,
                        auto_resolve_rate=round(c_auto / c_resolved * 100, 1) if c_resolved > 0 else 0.0,
                        avg_resolve_hours=c_avg,
                        pending_alerts=c_pending
                    ))

        return TrendResponse(
            period_type=period_type,
            clinic_id=clinic_id,
            data_points=data_points,
            by_clinic=by_clinic_data if compare_clinic else None
        )
