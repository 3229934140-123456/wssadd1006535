from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models import (
    CleaningRecord, Followup, Appointment, Alert, AlertAction,
    Clinic, Doctor, Patient
)
from config import (
    HIGH_VALUE_PATIENT_TYPES,
    SYMPTOMS_REQUIRING_REVIEW,
    ACTION_TYPES,
    get_followup_threshold,
    get_interval_days
)


class AlertEngine:
    def __init__(self, db: Session):
        self.db = db

    def run_all_checks(self) -> List[Alert]:
        self._auto_resolve_alerts()
        new_alerts = []
        new_alerts.extend(self.check_unfollowed())
        new_alerts.extend(self.check_unconverted())
        new_alerts.extend(self.check_high_value_overdue())
        self.db.commit()
        return new_alerts

    def _auto_resolve_alerts(self) -> None:
        pending_alerts = self.db.query(Alert).filter(Alert.status == "待处理").all()
        for alert in pending_alerts:
            record = self.db.query(CleaningRecord).filter(
                CleaningRecord.id == alert.cleaning_record_id
            ).first()
            if not record:
                continue
            should_resolve = False
            resolve_reason = ""
            resolve_operator = "系统自动"
            resolve_detail = ""
            if alert.alert_type == "未随访":
                has_followup = self.db.query(Followup).filter(
                    Followup.cleaning_record_id == record.id
                ).first()
                if has_followup:
                    should_resolve = True
                    resolve_reason = "已补录随访记录"
                    latest_followup = self.db.query(Followup).filter(
                        Followup.cleaning_record_id == record.id
                    ).order_by(Followup.followup_time.desc()).first()
                    if latest_followup:
                        resolve_operator = latest_followup.operator
                        resolve_detail = f"随访补录-{latest_followup.operator}（{latest_followup.followup_time.strftime('%Y-%m-%d %H:%M')}）"
                        self._add_action(
                            alert_id=alert.id,
                            clinic_id=alert.clinic_id,
                            patient_id=record.patient_id,
                            action_type="电话",
                            action_time=latest_followup.followup_time,
                            operator=latest_followup.operator,
                            contact_method=latest_followup.contact_method,
                            content=latest_followup.patient_feedback,
                            auto_action=True
                        )
            elif alert.alert_type == "未转化":
                has_appointment = self.db.query(Appointment).filter(
                    and_(
                        Appointment.cleaning_record_id == record.id,
                        Appointment.status.in_(["待就诊", "已就诊"])
                    )
                ).first()
                if has_appointment:
                    should_resolve = True
                    resolve_reason = "已安排复查预约"
                    latest_appointment = self.db.query(Appointment).filter(
                        Appointment.cleaning_record_id == record.id
                    ).order_by(Appointment.created_at.desc()).first()
                    if latest_appointment:
                        resolve_operator = latest_appointment.operator or "系统自动"
                        resolve_detail = f"预约补录-{latest_appointment.operator or '系统自动'}（{latest_appointment.created_at.strftime('%Y-%m-%d %H:%M')}）"
                        self._add_action(
                            alert_id=alert.id,
                            clinic_id=alert.clinic_id,
                            patient_id=record.patient_id,
                            action_type="预约",
                            action_time=latest_appointment.created_at,
                            operator=latest_appointment.operator or "系统自动",
                            appointment_date=latest_appointment.appointment_date,
                            content=f"已预约{latest_appointment.appointment_type}，日期：{latest_appointment.appointment_date}",
                            auto_action=True
                        )
                else:
                    latest_followup = self.db.query(Followup).filter(
                        Followup.cleaning_record_id == record.id
                    ).order_by(Followup.followup_time.desc()).first()
                    if latest_followup:
                        has_symptom = (
                            latest_followup.has_bleeding
                            or latest_followup.has_sensitivity
                            or latest_followup.has_pain
                        )
                        if not has_symptom:
                            should_resolve = True
                            resolve_reason = "最新随访显示症状已消除"
                            resolve_operator = latest_followup.operator
                            resolve_detail = f"随访症状消除-{latest_followup.operator}（{latest_followup.followup_time.strftime('%Y-%m-%d %H:%M')}）"
                            self._add_action(
                                alert_id=alert.id,
                                clinic_id=alert.clinic_id,
                                patient_id=record.patient_id,
                                action_type="电话",
                                action_time=latest_followup.followup_time,
                                operator=latest_followup.operator,
                                contact_method=latest_followup.contact_method,
                                content=latest_followup.patient_feedback or "症状已消除",
                                auto_action=True
                            )
            elif alert.alert_type == "高价值维护":
                has_appointment = self.db.query(Appointment).filter(
                    and_(
                        Appointment.cleaning_record_id == record.id,
                        Appointment.status.in_(["待就诊", "已就诊"])
                    )
                ).first()
                if has_appointment:
                    should_resolve = True
                    resolve_reason = "已预约复诊"
                    latest_appointment = self.db.query(Appointment).filter(
                        Appointment.cleaning_record_id == record.id
                    ).order_by(Appointment.created_at.desc()).first()
                    if latest_appointment:
                        resolve_operator = latest_appointment.operator or "系统自动"
                        resolve_detail = f"复诊预约-{latest_appointment.operator or '系统自动'}（{latest_appointment.created_at.strftime('%Y-%m-%d %H:%M')}）"
                        self._add_action(
                            alert_id=alert.id,
                            clinic_id=alert.clinic_id,
                            patient_id=record.patient_id,
                            action_type="预约",
                            action_time=latest_appointment.created_at,
                            operator=latest_appointment.operator or "系统自动",
                            appointment_date=latest_appointment.appointment_date,
                            content=f"已预约{latest_appointment.appointment_type}，日期：{latest_appointment.appointment_date}",
                            auto_action=True
                        )
            if should_resolve:
                alert.status = "已处理"
                alert.resolved_at = datetime.utcnow()
                alert.resolved_note = resolve_reason
                alert.resolved_by = resolve_operator
                alert.resolved_detail = resolve_detail
                alert.auto_resolved = True
                alert.auto_resolved_reason = resolve_reason
                self._add_action(
                    alert_id=alert.id,
                    clinic_id=alert.clinic_id,
                    patient_id=record.patient_id,
                    action_type="关闭",
                    action_time=datetime.utcnow(),
                    operator=resolve_operator,
                    close_reason=resolve_reason,
                    content=resolve_detail,
                    auto_action=True
                )

    def _add_action(
        self,
        alert_id: int,
        clinic_id: int,
        patient_id: int,
        action_type: str,
        action_time: datetime,
        operator: str,
        contact_method: Optional[str] = None,
        content: Optional[str] = None,
        appointment_date: Optional[date] = None,
        close_reason: Optional[str] = None,
        auto_action: bool = False
    ) -> AlertAction:
        action = AlertAction(
            alert_id=alert_id,
            clinic_id=clinic_id,
            patient_id=patient_id,
            action_type=action_type,
            action_time=action_time,
            operator=operator,
            contact_method=contact_method,
            content=content,
            appointment_date=appointment_date,
            close_reason=close_reason,
        )
        self.db.add(action)
        self.db.flush()
        return action

    def add_alert_action(
        self,
        alert_id: int,
        action_type: str,
        action_time: datetime,
        operator: str,
        contact_method: Optional[str] = None,
        content: Optional[str] = None,
        appointment_date: Optional[date] = None,
        close_reason: Optional[str] = None
    ) -> Optional[AlertAction]:
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return None
        action = self._add_action(
            alert_id=alert_id,
            clinic_id=alert.clinic_id,
            patient_id=alert.cleaning_record.patient_id,
            action_type=action_type,
            action_time=action_time,
            operator=operator,
            contact_method=contact_method,
            content=content,
            appointment_date=appointment_date,
            close_reason=close_reason
        )
        if action_type == "关闭" and alert.status == "待处理":
            alert.status = "已处理"
            alert.resolved_at = datetime.utcnow()
            alert.resolved_note = close_reason or "手动关闭"
            alert.resolved_by = operator
            alert.resolved_detail = f"手动关闭-{operator}（{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}）"
            alert.auto_resolved = False
        self.db.commit()
        self.db.refresh(action)
        return action

    def assign_alert(
        self,
        alert_id: int,
        assignee: str,
        deadline: Optional[datetime] = None,
        assigned_by: Optional[str] = None
    ) -> Optional[Alert]:
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return None
        alert.assignee = assignee
        alert.assigned_at = datetime.utcnow()
        alert.assigned_by = assigned_by
        alert.deadline = deadline
        self._add_action(
            alert_id=alert.id,
            clinic_id=alert.clinic_id,
            patient_id=alert.cleaning_record.patient_id,
            action_type="分派",
            action_time=datetime.utcnow(),
            operator=assigned_by or "系统",
            content=f"分派给 {assignee}" + (f"，截止时间：{deadline.strftime('%Y-%m-%d %H:%M')}" if deadline else "")
        )
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def batch_assign_alerts(
        self,
        alert_ids: List[int],
        assignee: str,
        deadline: Optional[datetime] = None,
        assigned_by: Optional[str] = None
    ) -> Tuple[int, int, List[int], List[int]]:
        success_count = 0
        failed_count = 0
        success_ids = []
        failed_ids = []
        now = datetime.utcnow()
        for alert_id in alert_ids:
            alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
            if not alert:
                failed_count += 1
                failed_ids.append(alert_id)
                continue
            alert.assignee = assignee
            alert.assigned_at = now
            alert.assigned_by = assigned_by
            alert.deadline = deadline
            self._add_action(
                alert_id=alert.id,
                clinic_id=alert.clinic_id,
                patient_id=alert.cleaning_record.patient_id,
                action_type="分派",
                action_time=now,
                operator=assigned_by or "系统",
                content=f"批量分派给 {assignee}" + (f"，截止时间：{deadline.strftime('%Y-%m-%d %H:%M')}" if deadline else "")
            )
            success_count += 1
            success_ids.append(alert_id)
        self.db.commit()
        return success_count, failed_count, success_ids, failed_ids

    def check_unfollowed(self) -> List[Alert]:
        new_alerts = []
        records = self.db.query(CleaningRecord).all()
        for record in records:
            threshold = get_followup_threshold(self.db, record.clinic_id)
            threshold_date = date.today() - timedelta(days=threshold)
            if record.cleaning_date > threshold_date:
                continue
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
                    f"已超过{threshold}天未进行随访。"
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
            records = (
                self.db.query(CleaningRecord)
                .join(Patient, CleaningRecord.patient_id == Patient.id)
                .filter(Patient.patient_type == patient_type)
                .all()
            )
            for record in records:
                interval_days = get_interval_days(self.db, record.clinic_id, patient_type)
                threshold_date = today - timedelta(days=interval_days)
                if record.cleaning_date > threshold_date:
                    continue
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

    def resolve_alert(
        self, alert_id: int, resolved_note: Optional[str] = None,
        operator: Optional[str] = None
    ) -> Optional[Alert]:
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return None
        alert.status = "已处理"
        alert.resolved_at = datetime.utcnow()
        alert.resolved_note = resolved_note
        alert.resolved_by = operator
        alert.resolved_detail = f"手动关闭-{operator or '手动处理'}（{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}）"
        alert.auto_resolved = False
        self._add_action(
            alert_id=alert.id,
            clinic_id=alert.clinic_id,
            patient_id=alert.cleaning_record.patient_id,
            action_type="关闭",
            action_time=datetime.utcnow(),
            operator=operator or "手动处理",
            close_reason=resolved_note,
            content=resolved_note or "手动标记处理完成"
        )
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def get_alerts_by_clinic(
        self, clinic_id: Optional[int] = None,
        status: Optional[str] = None,
        alert_type: Optional[str] = None,
        assignee: Optional[str] = None,
        is_overdue_deadline: Optional[bool] = None,
        doctor_id: Optional[int] = None,
        patient_type: Optional[str] = None
    ) -> List[Alert]:
        query = self.db.query(Alert).join(CleaningRecord, Alert.cleaning_record_id == CleaningRecord.id)
        if clinic_id:
            query = query.filter(Alert.clinic_id == clinic_id)
        if status:
            query = query.filter(Alert.status == status)
        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)
        if assignee:
            query = query.filter(Alert.assignee == assignee)
        if is_overdue_deadline is not None:
            now = datetime.utcnow()
            if is_overdue_deadline:
                query = query.filter(Alert.deadline.isnot(None), Alert.deadline < now)
            else:
                query = query.filter(or_(Alert.deadline.is_(None), Alert.deadline >= now))
        if doctor_id:
            query = query.filter(CleaningRecord.doctor_id == doctor_id)
        if patient_type:
            query = query.join(Patient, CleaningRecord.patient_id == Patient.id).filter(
                Patient.patient_type == patient_type
            )
        return query.order_by(Alert.created_at.desc()).all()

    def get_alert_detail(self, alert_id: int) -> Optional[Alert]:
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        return alert

    def get_patient_action_history(self, patient_id: int, limit: int = 20) -> List[AlertAction]:
        actions = (
            self.db.query(AlertAction)
            .filter(AlertAction.patient_id == patient_id)
            .order_by(AlertAction.action_time.desc())
            .limit(limit)
            .all()
        )
        return actions
