import sys
from datetime import date, datetime, timedelta
from database import SessionLocal
from alert_engine import AlertEngine
from stats_service import StatsService
from models import ClinicConfig, Followup, Appointment, Alert, CleaningRecord, Patient, Clinic


def test_alert_engine_v3():
    print("=" * 60)
    print("【测试1】预警引擎 - 第三轮扩展功能")
    print("=" * 60)
    db = SessionLocal()
    try:
        engine = AlertEngine(db)
        new_alerts = engine.run_all_checks()
        print(f"初始预警生成: {len(new_alerts)}条")

        pending = engine.get_alerts_by_clinic(status="待处理")
        print(f"初始待处理预警: {len(pending)}条")
        for a in pending[:3]:
            print(f"  - [{a.alert_type}] {a.title}")

        unfollow_alert = next((a for a in pending if a.alert_type == "未随访"), None)
        if unfollow_alert:
            record = db.query(CleaningRecord).filter(
                CleaningRecord.id == unfollow_alert.cleaning_record_id
            ).first()
            followup = Followup(
                cleaning_record_id=record.id,
                patient_id=record.patient_id,
                followup_time=datetime.now() - timedelta(hours=1),
                operator="客服小王",
                contact_method="电话",
                patient_feedback="患者无不适，已预约复查",
                has_bleeding=False,
                has_sensitivity=False,
                has_pain=False,
                next_step="半年后复查"
            )
            db.add(followup)
            db.commit()

            engine.run_all_checks()
            db.refresh(unfollow_alert)
            print(f"\n随访补录自动闭环验证:")
            print(f"  预警状态: {unfollow_alert.status}")
            print(f"  处理人: {unfollow_alert.resolved_by}")
            print(f"  处理详情: {unfollow_alert.resolved_detail}")
            print(f"  处理时间: {unfollow_alert.resolved_at}")
            print(f"  自动关闭: {unfollow_alert.auto_resolved}")

    finally:
        db.close()


def test_assign_alert():
    print()
    print("=" * 60)
    print("【测试2】预警任务分派")
    print("=" * 60)
    db = SessionLocal()
    try:
        engine = AlertEngine(db)
        pending = engine.get_alerts_by_clinic(status="待处理")
        if not pending:
            print("没有待处理预警")
        else:
            alert = pending[0]
            print(f"原预警: {alert.title}")
            print(f"  原负责人: {alert.responsible_person}")
            print(f"  原assignee: {alert.assignee}")

            deadline = datetime.now() + timedelta(days=2)
            assigned = engine.assign_alert(
                alert_id=alert.id,
                assignee="客服小李",
                deadline=deadline,
                assigned_by="运营主管张经理"
            )
            print(f"\n分派后:")
            print(f"  assignee: {assigned.assignee}")
            print(f"  分派时间: {assigned.assigned_at}")
            print(f"  分派人: {assigned.assigned_by}")
            print(f"  截止时间: {assigned.deadline}")

            print(f"\n按负责人筛选(客服小李):")
            by_assignee = engine.get_alerts_by_clinic(assignee="客服小李")
            print(f"  找到 {len(by_assignee)} 条预警分派给客服小李")
            for a in by_assignee[:2]:
                print(f"    - {a.title}")

            print(f"\n处理动作时间线(分派记录):")
            actions = sorted(alert.actions, key=lambda x: x.action_time)
            for action in actions[-3:]:
                print(f"  [{action.action_time.strftime('%Y-%m-%d %H:%M')}] {action.action_type} "
                      f"- {action.operator}: {action.content or action.close_reason}")

    finally:
        db.close()


def test_alerts_filter():
    print()
    print("=" * 60)
    print("【测试3】预警列表多维度筛选")
    print("=" * 60)
    db = SessionLocal()
    try:
        engine = AlertEngine(db)

        print("按患者类型筛选(种植):")
        pt_alerts = engine.get_alerts_by_clinic(patient_type="种植")
        print(f"  种植患者预警: {len(pt_alerts)}条")

        print("\n按医生筛选(医生ID=1):")
        doc_alerts = engine.get_alerts_by_clinic(doctor_id=1)
        print(f"  医生1相关预警: {len(doc_alerts)}条")

        print("\n按门店筛选(门店ID=1):")
        clinic_alerts = engine.get_alerts_by_clinic(clinic_id=1)
        print(f"  门店1预警: {len(clinic_alerts)}条")

    finally:
        db.close()


def test_overview_ranking_v3():
    print()
    print("=" * 60)
    print("【测试4】总览排行 - 多维度筛选联动+逾期/待处理数")
    print("=" * 60)
    db = SessionLocal()
    try:
        stats = StatsService(db)

        print("【无筛选】门店排行前2名(带详细指标):")
        overview = stats.get_overview()
        for item in overview.clinic_ranking[:2]:
            print(f"  {item.name}:")
            print(f"    洁治{item.total_cleanings}例, 随访率{item.followup_rate}%, 预约率{item.appointment_rate}%")
            print(f"    逾期{item.overdue_count}人(未随访{item.unfollowup_count}/未转化{item.unconverted_count}/高价值{item.high_value_overdue_count})")
            print(f"    待处理预警: {item.alert_pending_count}个")

        print("\n【无筛选】医生排行前2名(带详细指标):")
        for item in overview.doctor_ranking[:2]:
            print(f"  {item.name}:")
            print(f"    洁治{item.total_cleanings}例, 随访率{item.followup_rate}%, 预约率{item.appointment_rate}%")
            print(f"    逾期{item.overdue_count}人(未随访{item.unfollowup_count}/未转化{item.unconverted_count}/高价值{item.high_value_overdue_count})")
            print(f"    待处理预警: {item.alert_pending_count}个")

        print("\n【无筛选】患者类型分布(带详细指标):")
        for pt in overview.patient_type_breakdown:
            print(f"  {pt['patient_type']}:")
            print(f"    洁治{pt['total_cleanings']}例, 随访率{pt['followup_rate']}%, 预约率{pt['appointment_rate']}%")
            print(f"    逾期{pt['overdue_count']}人, 待处理预警{pt['alert_pending_count']}个")

        clinic = db.query(Clinic).first()
        if clinic:
            print(f"\n【按门店筛选{clinic.name}】排行联动验证:")
            clinic_overview = stats.get_overview(clinic_id=clinic.id)
            print(f"  门店排行共{len(clinic_overview.clinic_ranking)}个门店")
            print(f"  医生排行共{len(clinic_overview.doctor_ranking)}个医生")
            print(f"  汇总: 洁治{clinic_overview.summary.total_cleanings}例, "
                  f"逾期{clinic_overview.summary.total_overdue}人, "
                  f"待处理{clinic_overview.summary.total_alerts_pending}个")

    finally:
        db.close()


def test_trend_analysis():
    print()
    print("=" * 60)
    print("【测试5】趋势分析 - 按天/周统计")
    print("=" * 60)
    db = SessionLocal()
    try:
        stats = StatsService(db)

        print("【按天】最近14天趋势(前3个数据点):")
        trend_day = stats.get_trend(period_type="day")
        print(f"  周期类型: {trend_day.period_type}, 数据点: {len(trend_day.data_points)}个")
        for dp in trend_day.data_points[:3]:
            print(f"    {dp.period}: 新增{dp.new_alerts}条, "
                  f"处理{dp.resolved_alerts}条, "
                  f"自动闭环率{dp.auto_resolve_rate}%, "
                  f"平均处理{dp.avg_resolve_hours}小时, "
                  f"待处理{dp.pending_alerts}个")

        print("\n【按周】最近6周趋势:")
        trend_week = stats.get_trend(period_type="week")
        print(f"  周期类型: {trend_week.period_type}, 数据点: {len(trend_week.data_points)}个")
        for dp in trend_week.data_points[:2]:
            print(f"    {dp.period}: 新增{dp.new_alerts}条, "
                  f"处理{dp.resolved_alerts}条, "
                  f"自动闭环率{dp.auto_resolve_rate}%")

        print("\n【按门店对比】各门店趋势:")
        trend_compare = stats.get_trend(period_type="day", compare_clinic=True)
        if trend_compare.by_clinic:
            for cid, c_points in list(trend_compare.by_clinic.items())[:2]:
                clinic_name = db.query(Clinic).filter(Clinic.id == cid).first()
                cname = clinic_name.name if clinic_name else f"门店{cid}"
                print(f"  {cname}: {len(c_points)}个数据点, "
                      f"最近1天新增{c_points[-1].new_alerts if c_points else 0}条")

    finally:
        db.close()


def test_export_with_detail():
    print()
    print("=" * 60)
    print("【测试6】重点名单导出 - 处理人/分派信息完整")
    print("=" * 60)
    db = SessionLocal()
    try:
        stats = StatsService(db)
        export = stats.export_high_value_list()
        print(f"导出{export.total_count}人")
        for item in export.items[:2]:
            print(f"\n  【{item.alert_type}】{item.patient_name}")
            print(f"    状态: {item.status}")
            print(f"    责任人: {item.responsible_person}")
            print(f"    被分派给: {item.assignee or '未分派'}")
            print(f"    截止时间: {item.deadline or '未设置'}")
            print(f"    处理人: {item.resolved_by or '未处理'}")
            print(f"    处理详情: {item.resolved_detail or '未处理'}")
            print(f"    处理时间: {item.resolved_at or '未处理'}")
            print(f"    自动闭环: {item.auto_resolved}")
    finally:
        db.close()


if __name__ == "__main__":
    test_alert_engine_v3()
    test_assign_alert()
    test_alerts_filter()
    test_overview_ranking_v3()
    test_trend_analysis()
    test_export_with_detail()
    print()
    print("=" * 60)
    print("🎉 第三轮所有功能测试完成！")
    print("=" * 60)
