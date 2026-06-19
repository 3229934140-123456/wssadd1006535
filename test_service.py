import sys
from datetime import date, datetime, timedelta
from database import SessionLocal
from alert_engine import AlertEngine
from stats_service import StatsService


def test_alert_engine():
    print("=" * 60)
    print("测试预警引擎")
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
    finally:
        db.close()


def test_stats_service():
    print()
    print("=" * 60)
    print("测试运营统计")
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
        print()
        print("预警详情列表:")
        details = stats.get_records_by_alert_type()
        for d in details:
            print(f"  [{d['alert_type']}] {d['patient_name']}({d['patient_type']}) - "
                  f"责任人: {d['responsible_person']}")
    finally:
        db.close()


def test_detail_view():
    print()
    print("=" * 60)
    print("测试单条记录详情")
    print("=" * 60)
    db = SessionLocal()
    try:
        stats = StatsService(db)
        from models import CleaningRecord
        record = db.query(CleaningRecord).first()
        if record:
            detail = stats.get_cleaning_record_detail(record.id)
            print(f"患者: {detail.patient_name}")
            print(f"电话: {detail.patient_phone}")
            print(f"类型: {detail.patient_type}")
            print(f"医生: {detail.doctor_name}")
            print(f"门店: {detail.clinic_name}")
            print(f"洁治日期: {detail.cleaning_date}")
            print(f"责任人: {detail.responsible_person}")
            print(f"最近处理: {detail.last_process_time}")
            print(f"随访次数: {len(detail.followups)}")
            print(f"预约次数: {len(detail.appointments)}")
            print(f"预警次数: {len(detail.alerts)}")
    finally:
        db.close()


if __name__ == "__main__":
    test_alert_engine()
    test_stats_service()
    test_detail_view()
    print()
    print("=" * 60)
    print("所有测试完成！")
    print("=" * 60)
