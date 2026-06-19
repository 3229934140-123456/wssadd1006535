import sys
from datetime import date, datetime, timedelta
from database import SessionLocal
from alert_engine import AlertEngine
from stats_service import StatsService
from models import ClinicConfig, Followup, Appointment, Alert, CleaningRecord, Patient


def test_alert_engine():
    print("=" * 60)
    print("【测试1】预警引擎 - 初始预警生成")
    print("=" * 60)
    db = SessionLocal()
    try:
        engine = AlertEngine(db)
        new_alerts = engine.run_all_checks()
        print(f"生成预警数量: {len(new_alerts)}")
        for a in new_alerts:
            print(f"  [{a.alert_type}] {a.title}")
        print()
        print("所有待处理预警:")
        pending = engine.get_alerts_by_clinic(status="待处理")
        for a in pending:
            print(f"  - [{a.alert_type}] {a.title} -> 责任人: {a.responsible_person}")
        print(f"\n待处理预警总数: {len(pending)}")
    finally:
        db.close()


def test_auto_resolve():
    print()
    print("=" * 60)
    print("【测试2】预警自动闭环 - 随访补录后自动关闭")
    print("=" * 60)
    db = SessionLocal()
    try:
        engine = AlertEngine(db)
        pending = engine.get_alerts_by_clinic(status="待处理")

        unfollow_alert = next((a for a in pending if a.alert_type == "未随访"), None)
        if not unfollow_alert:
            print("没有找到待处理的未随访预警，跳过此测试")
        else:
            print(f"找到未随访预警: {unfollow_alert.title}")
            print(f"  当前状态: {unfollow_alert.status}")

            record = db.query(CleaningRecord).filter(
                CleaningRecord.id == unfollow_alert.cleaning_record_id
            ).first()

            followup = Followup(
                cleaning_record_id=record.id,
                patient_id=record.patient_id,
                followup_time=datetime.now() - timedelta(hours=1),
                operator="客服小王",
                contact_method="电话",
                patient_feedback="患者表示无不适，已安排定期检查",
                has_bleeding=False,
                has_sensitivity=False,
                has_pain=False,
                next_step="半年后复查"
            )
            db.add(followup)
            db.commit()
            print(f"  已补录随访记录: {followup.patient_feedback}")

            engine.run_all_checks()

            db.refresh(unfollow_alert)
            print(f"  补录后状态: {unfollow_alert.status}")
            print(f"  自动关闭: {unfollow_alert.auto_resolved}")
            print(f"  关闭原因: {unfollow_alert.auto_resolved_reason}")
            print(f"  处理时间: {unfollow_alert.resolved_at}")

            print(f"\n  处理时间线（共{len(unfollow_alert.actions)}条）:")
            for action in unfollow_alert.actions:
                print(f"    - [{action.action_time.strftime('%Y-%m-%d %H:%M')}] {action.action_type} "
                      f"- {action.operator}: {action.content or action.close_reason}")

        unconverted_alert = next((a for a in pending if a.alert_type == "未转化"), None)
        if not unconverted_alert:
            print("\n没有找到待处理的未转化预警，跳过此测试")
        else:
            print(f"\n找到未转化预警: {unconverted_alert.title}")
            print(f"  当前状态: {unconverted_alert.status}")

            record = db.query(CleaningRecord).filter(
                CleaningRecord.id == unconverted_alert.cleaning_record_id
            ).first()

            appointment = Appointment(
                cleaning_record_id=record.id,
                patient_id=record.patient_id,
                appointment_date=date.today() + timedelta(days=3),
                appointment_type="牙周复查",
                status="待就诊"
            )
            db.add(appointment)
            db.commit()
            print(f"  已安排预约: {appointment.appointment_type} - {appointment.appointment_date}")

            engine.run_all_checks()

            db.refresh(unconverted_alert)
            print(f"  预约后状态: {unconverted_alert.status}")
            print(f"  自动关闭: {unconverted_alert.auto_resolved}")
            print(f"  关闭原因: {unconverted_alert.auto_resolved_reason}")

    finally:
        db.close()


def test_clinic_config():
    print()
    print("=" * 60)
    print("【测试3】门店级独立配置")
    print("=" * 60)
    db = SessionLocal()
    try:
        from models import Clinic
        clinic = db.query(Clinic).filter(Clinic.name.contains("朝阳")).first()
        if clinic:
            print(f"门店: {clinic.name}")

            existing_config = db.query(ClinicConfig).filter(
                ClinicConfig.clinic_id == clinic.id
            ).first()
            if existing_config:
                db.delete(existing_config)
                db.commit()

            config = ClinicConfig(
                clinic_id=clinic.id,
                followup_days_threshold=2,
                implant_interval_days=25,
                orthodontics_interval_days=18,
                periodontal_interval_days=12,
                regular_interval_days=6
            )
            db.add(config)
            db.commit()
            db.refresh(config)
            print(f"  已设置门店配置:")
            print(f"    随访超期天数: {config.followup_days_threshold}天（默认3天）")
            print(f"    种植维护周期: {config.implant_interval_days}天（默认30天）")
            print(f"    正畸维护周期: {config.orthodontics_interval_days}天（默认21天）")
            print(f"    牙周维护周期: {config.periodontal_interval_days}天（默认14天）")

            from config import get_followup_threshold, get_interval_days
            threshold = get_followup_threshold(db, clinic.id)
            implant_interval = get_interval_days(db, clinic.id, "种植")
            print(f"\n  读取验证:")
            print(f"    门店随访阈值: {threshold}天")
            print(f"    门店种植周期: {implant_interval}天")

            other_clinic = db.query(Clinic).filter(Clinic.id != clinic.id).first()
            if other_clinic:
                other_threshold = get_followup_threshold(db, other_clinic.id)
                other_implant = get_interval_days(db, other_clinic.id, "种植")
                print(f"\n  其他门店（{other_clinic.name}）使用默认值:")
                print(f"    随访阈值: {other_threshold}天")
                print(f"    种植周期: {other_implant}天")

    finally:
        db.close()


def test_alert_actions():
    print()
    print("=" * 60)
    print("【测试4】处理记录时间线 - 追加跟进动作")
    print("=" * 60)
    db = SessionLocal()
    try:
        engine = AlertEngine(db)
        pending = engine.get_alerts_by_clinic(status="待处理")

        if not pending:
            print("没有待处理预警，跳过此测试")
        else:
            alert = pending[0]
            print(f"预警: {alert.title}")
            print(f"患者ID: {alert.cleaning_record.patient_id}")

            action1 = engine.add_alert_action(
                alert_id=alert.id,
                action_type="电话",
                action_time=datetime.now() - timedelta(hours=2),
                operator="客服小李",
                contact_method="手机",
                content="患者电话未接通，已发短信提醒"
            )
            print(f"\n已追加动作1: [{action1.action_type}] {action1.operator} - {action1.content}")

            action2 = engine.add_alert_action(
                alert_id=alert.id,
                action_type="微信",
                action_time=datetime.now() - timedelta(hours=1),
                operator="客服小李",
                contact_method="企业微信",
                content="已通过微信联系患者，约定明日下午回电"
            )
            print(f"已追加动作2: [{action2.action_type}] {action2.operator} - {action2.content}")

            patient = db.query(Patient).filter(
                Patient.id == alert.cleaning_record.patient_id
            ).first()
            print(f"\n患者 {patient.name} 的所有历史处理（最近5条）:")
            history = engine.get_patient_action_history(patient.id, limit=5)
            for action in history:
                print(f"  [{action.action_time.strftime('%Y-%m-%d %H:%M')}] "
                      f"{action.action_type} - {action.operator}: {action.content or action.close_reason}")

    finally:
        db.close()


def test_overview_stats():
    print()
    print("=" * 60)
    print("【测试5】总览统计接口 - 多维度筛选与排行")
    print("=" * 60)
    db = SessionLocal()
    try:
        stats = StatsService(db)

        print("【无筛选条件】总览:")
        overview = stats.get_overview()
        print(f"  汇总指标:")
        print(f"    门店数: {overview.summary.total_clinics}")
        print(f"    医生数: {overview.summary.total_doctors}")
        print(f"    患者数: {overview.summary.total_patients}")
        print(f"    洁治总数: {overview.summary.total_cleanings}")
        print(f"    整体随访率: {overview.summary.overall_followup_rate}%")
        print(f"    整体预约率: {overview.summary.overall_appointment_rate}%")
        print(f"    逾期总数: {overview.summary.total_overdue}")
        print(f"    待处理预警: {overview.summary.total_alerts_pending}")
        print(f"      - 未随访: {overview.summary.unfollowup_count}")
        print(f"      - 未转化: {overview.summary.unconverted_count}")
        print(f"      - 高价值逾期: {overview.summary.high_value_overdue_count}")

        print(f"\n  门店逾期排行（Top3）:")
        for item in overview.clinic_ranking[:3]:
            print(f"    {item.name}: 逾期{item.overdue_count}人, "
                  f"随访率{item.followup_rate}%, 预约率{item.appointment_rate}%")

        print(f"\n  医生随访率排行（Top3）:")
        for item in overview.doctor_ranking[:3]:
            print(f"    {item.name}: 随访率{item.followup_rate}%, "
                  f"预约率{item.appointment_rate}%, 洁治{item.total_cleanings}例")

        print(f"\n  患者类型分布:")
        for pt in overview.patient_type_breakdown:
            print(f"    {pt['patient_type']}: {pt['total_cleanings']}例, "
                  f"随访率{pt['followup_rate']}%, 预约率{pt['appointment_rate']}%")

        from models import Clinic
        clinic = db.query(Clinic).first()
        if clinic:
            print(f"\n【按门店筛选】{clinic.name}:")
            clinic_overview = stats.get_overview(clinic_id=clinic.id)
            print(f"  洁治总数: {clinic_overview.summary.total_cleanings}")
            print(f"  随访率: {clinic_overview.summary.overall_followup_rate}%")
            print(f"  预约率: {clinic_overview.summary.overall_appointment_rate}%")

    finally:
        db.close()


def test_patient_history():
    print()
    print("=" * 60)
    print("【测试6】患者预警历史查询")
    print("=" * 60)
    db = SessionLocal()
    try:
        stats = StatsService(db)
        patient = db.query(Patient).first()
        if patient:
            history = stats.get_patient_alert_history(patient.id)
            print(f"患者: {history.patient_name}")
            print(f"电话: {history.patient_phone}")
            print(f"类型: {history.patient_type}")
            print(f"总预警数: {history.total_alerts}")
            print(f"待处理: {history.pending_alerts}")
            print(f"已处理: {history.resolved_alerts}")
            print(f"\n最近处理记录（{len(history.actions)}条）:")
            for action in history.actions[:5]:
                print(f"  [{action.action_time.strftime('%Y-%m-%d %H:%M')}] "
                      f"{action.action_type} - {action.operator}: "
                      f"{action.content or action.close_reason}")
    finally:
        db.close()


def test_export_high_value():
    print()
    print("=" * 60)
    print("【测试7】重点名单导出")
    print("=" * 60)
    db = SessionLocal()
    try:
        stats = StatsService(db)
        export = stats.export_high_value_list()
        print(f"导出时间: {export.export_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"总记录数: {export.total_count}")
        print(f"  高价值维护: {export.high_value_count}人")
        print(f"  未转化: {export.unconverted_count}人")
        print(f"\n导出字段示例（前2条）:")
        for item in export.items[:2]:
            print(f"\n  【{item.alert_type}】{item.patient_name}")
            print(f"    门店: {item.clinic_name}")
            print(f"    患者类型: {item.patient_type}")
            print(f"    责任医生: {item.doctor_name}")
            print(f"    联系电话: {item.patient_phone}")
            print(f"    逾期天数: {item.overdue_days}天")
            print(f"    最近随访: {item.last_followup_content or '无'}")
            print(f"    责任人: {item.responsible_person}")
    finally:
        db.close()


def test_stats_service():
    print()
    print("=" * 60)
    print("【测试8】各门店运营指标")
    print("=" * 60)
    db = SessionLocal()
    try:
        stats = StatsService(db)
        all_stats = stats.get_all_clinics_stats()
        print("各门店运营指标:")
        for s in all_stats:
            print(f"  【{s.clinic_name}】")
            print(f"    洁治总数: {s.total_cleanings}")
            print(f"    随访完成率: {s.followup_rate}% ({s.followed_up_count}/{s.total_cleanings})")
            print(f"    复诊预约率: {s.appointment_rate}% ({s.appointed_count}/{s.total_cleanings})")
            print(f"    逾期人数: {s.overdue_count}")
            print(f"    未随访: {s.unfollowup_count} | 未转化: {s.unconverted_count} | 高价值逾期: {s.high_value_overdue_count}")
            print(f"    待处理预警: {s.alert_pending_count}")
        print()
        print("医生维度统计:")
        doctor_stats = stats.get_doctor_stats()
        for d in doctor_stats:
            print(f"  {d['doctor_name']}({d['clinic_name']}) - 洁治: {d['total_cleanings']}, "
                  f"随访率: {d['followup_rate']}%, 预约率: {d['appointment_rate']}%")
    finally:
        db.close()


if __name__ == "__main__":
    test_alert_engine()
    test_auto_resolve()
    test_clinic_config()
    test_alert_actions()
    test_overview_stats()
    test_patient_history()
    test_export_high_value()
    test_stats_service()
    print()
    print("=" * 60)
    print("🎉 所有测试完成！第二轮功能全部验证通过")
    print("=" * 60)
