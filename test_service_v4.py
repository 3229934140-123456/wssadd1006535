import sys
import os
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from database import Base, engine, SessionLocal
from models import Clinic, Doctor, Patient, CleaningRecord, Followup, Appointment, Alert, ClinicConfig
from alert_engine import AlertEngine
from stats_service import StatsService


def setup_test_data(db):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    c1 = Clinic(name="阳光口腔-朝阳门店", store_manager="王经理", manager_phone="13800000001")
    c2 = Clinic(name="阳光口腔-海淀门店", store_manager="李经理", manager_phone="13800000002")
    db.add_all([c1, c2])
    db.commit()

    d1 = Doctor(name="张医生", clinic_id=c1.id)
    d2 = Doctor(name="李医生", clinic_id=c1.id)
    d3 = Doctor(name="王医生", clinic_id=c2.id)
    db.add_all([d1, d2, d3])
    db.commit()

    patients_data = [
        ("患者A", "13800138001", "种植"),
        ("患者B", "13800138002", "正畸"),
        ("患者C", "13800138003", "牙周维护"),
        ("患者D", "13800138004", "常规洁治"),
        ("患者E", "13800138005", "种植"),
        ("患者F", "13800138006", "正畸"),
    ]
    patients = []
    for name, phone, ptype in patients_data:
        p = Patient(name=name, phone=phone, patient_type=ptype)
        patients.append(p)
        db.add(p)
    db.commit()

    today = date.today()
    records = []
    doctor_ids = [d1.id, d2.id, d1.id, d3.id, d3.id, d3.id]
    clinic_ids = [c1.id, c1.id, c1.id, c2.id, c2.id, c2.id]
    for i, p in enumerate(patients):
        days_ago = [10, 8, 5, 12, 7, 15][i]
        r = CleaningRecord(
            patient_id=p.id,
            doctor_id=doctor_ids[i],
            clinic_id=clinic_ids[i],
            cleaning_date=today - timedelta(days=days_ago),
            notes="牙龈出血" if i % 2 == 0 else "无明显症状"
        )
        records.append(r)
        db.add(r)
    db.commit()

    f1 = Followup(
        cleaning_record_id=records[0].id,
        patient_id=patients[0].id,
        followup_time=datetime.combine(today - timedelta(days=5), datetime.min.time()),
        operator="客服小王",
        contact_method="电话",
        patient_feedback="仍有轻微出血",
        has_bleeding=True
    )
    db.add(f1)
    db.commit()

    alert_engine = AlertEngine(db)
    alert_engine.run_all_checks()

    return {"clinics": [c1, c2], "doctors": [d1, d2, d3], "patients": patients, "records": records}


def test_batch_assign():
    print("\n=== 测试1：批量分派 ===")
    db = SessionLocal()
    setup_test_data(db)

    engine = AlertEngine(db)
    stats = StatsService(db)

    alerts = engine.get_alerts_by_clinic(status="待处理")
    pending_ids = [a.id for a in alerts[:3]]
    print(f"  选了 {len(pending_ids)} 条待处理预警进行批量分派")
    print(f"  预警ID: {pending_ids}")

    deadline = datetime.now() + timedelta(days=2)
    success_count, failed_count, success_ids, failed_ids = engine.batch_assign_alerts(
        alert_ids=pending_ids + [9999],
        assignee="客服小李",
        deadline=deadline,
        assigned_by="运营张主管"
    )

    print(f"  成功数: {success_count}, 失败数: {failed_count}")
    print(f"  成功IDs: {success_ids}")
    print(f"  失败IDs: {failed_ids}")
    assert success_count == 3, f"应该成功3条，实际成功{success_count}条"
    assert failed_count == 1, f"应该失败1条，实际失败{failed_count}条"
    assert 9999 in failed_ids, "无效ID应该在失败列表中"

    assigned_alerts = engine.get_alerts_by_clinic(assignee="客服小李")
    print(f"  按负责人'客服小李'筛选，查到 {len(assigned_alerts)} 条")
    assert len(assigned_alerts) >= 3, "分派后应该能查到至少3条"

    first_alert = assigned_alerts[0]
    print(f"  第一条预警：assignee={first_alert.assignee}, assigned_by={first_alert.assigned_by}")
    assert first_alert.assignee == "客服小李"
    assert first_alert.assigned_by == "运营张主管"

    timeline = first_alert.actions
    has_assign_action = any(a.action_type == "分派" and "批量" in a.content for a in timeline)
    print(f"  时间线中有批量分派动作: {has_assign_action}")
    assert has_assign_action, "时间线应该有批量分派动作"

    print("  ✅ 批量分派测试通过")
    db.close()


def test_export_multi_filter():
    print("\n=== 测试2：导出多维度筛选 ===")
    db = SessionLocal()
    setup_test_data(db)

    stats = StatsService(db)

    result_all = stats.export_high_value_list()
    print(f"  默认导出（待处理重点）: {result_all.total_count} 条")
    print(f"    高价值: {result_all.high_value_count}, 未转化: {result_all.unconverted_count}")

    result_resolved = stats.export_high_value_list(status="已处理")
    print(f"  按状态'已处理'筛选: {result_resolved.total_count} 条")

    result_type = stats.export_high_value_list(alert_type="未随访")
    print(f"  按类型'未随访'筛选: {result_type.total_count} 条")
    for item in result_type.items:
        assert item.alert_type == "未随访"

    result_assignee = stats.export_high_value_list(assignee="客服小李")
    print(f"  按负责人'客服小李'筛选: {result_assignee.total_count} 条")

    result_clinic = stats.export_high_value_list(clinic_id=1)
    print(f"  按门店1筛选: {result_clinic.total_count} 条, 门店名: {result_clinic.clinic_name}")

    print("  ✅ 导出多维度筛选测试通过")
    db.close()


def test_export_resolved_alerts_complete_info():
    print("\n=== 测试3：已处理/自动闭环预警导出信息完整 ===")
    db = SessionLocal()
    data = setup_test_data(db)
    engine = AlertEngine(db)
    stats = StatsService(db)

    alerts = engine.get_alerts_by_clinic(status="待处理", alert_type="未随访")
    if alerts:
        first_id = alerts[0].id
        engine.resolve_alert(
            alert_id=first_id,
            operator="客服小王",
            resolved_note="手动关闭测试"
        )
        print(f"  手动关闭预警 {first_id}，处理人=客服小王")

    stats = StatsService(db)
    result = stats.export_high_value_list(status="已处理")
    print(f"  已处理预警数量: {result.total_count}")

    if result.items:
        first_item = result.items[0]
        print(f"  第一条已处理预警：")
        print(f"    状态: {first_item.status}")
        print(f"    处理人: {first_item.resolved_by}")
        print(f"    处理时间: {first_item.resolved_at}")
        print(f"    处理详情: {first_item.resolved_detail}")
        print(f"    是否自动闭环: {first_item.auto_resolved}")
        assert first_item.resolved_by == "客服小王", "处理人应该是客服小王"
        assert first_item.resolved_at is not None, "处理时间不应该为空"
        assert first_item.status == "已处理", "状态应该是已处理"

    records = data["records"]
    r = records[1]
    f = Followup(
        cleaning_record_id=r.id,
        patient_id=r.patient_id,
        followup_time=datetime.now(),
        operator="客服小张",
        contact_method="微信",
        patient_feedback="已痊愈",
        has_bleeding=False,
        has_sensitivity=False,
        has_pain=False
    )
    db.add(f)
    db.commit()
    engine.run_all_checks()

    result2 = stats.export_high_value_list(status="已处理")
    print(f"  自动闭环后，已处理预警数量: {result2.total_count}")

    auto_resolved_items = [i for i in result2.items if i.auto_resolved]
    print(f"  自动闭环的预警数量: {len(auto_resolved_items)}")
    if auto_resolved_items:
        item = auto_resolved_items[0]
        print(f"  第一条自动闭环预警：")
        print(f"    处理人: {item.resolved_by}")
        print(f"    处理详情: {item.resolved_detail}")
        print(f"    是否自动闭环: {item.auto_resolved}")
        assert item.auto_resolved == True
        assert item.resolved_by is not None, "自动闭环也应该有处理人"
        assert item.resolved_detail is not None, "自动闭环应该有处理详情"

    print("  ✅ 已处理/自动闭环预警导出信息测试通过")
    db.close()


def test_assignee_performance():
    print("\n=== 测试4：负责人绩效统计 ===")
    db = SessionLocal()
    data = setup_test_data(db)
    engine = AlertEngine(db)

    pending_alerts = engine.get_alerts_by_clinic(status="待处理")
    ids_1 = [a.id for a in pending_alerts[:2]]
    ids_2 = [a.id for a in pending_alerts[2:4]]

    engine.batch_assign_alerts(ids_1, "客服小王", deadline=datetime.now() + timedelta(days=1), assigned_by="运营张主管")
    engine.batch_assign_alerts(ids_2, "客服小李", deadline=datetime.now() - timedelta(days=1), assigned_by="运营张主管")
    print(f"  分派给客服小王 {len(ids_1)} 条，截止时间=明天（不超时）")
    print(f"  分派给客服小李 {len(ids_2)} 条，截止时间=昨天（已超时）")

    if ids_1:
        engine.resolve_alert(ids_1[0], operator="客服小王", resolved_note="测试完成1")

    stats = StatsService(db)
    perf = stats.get_assignee_performance()
    print(f"  绩效统计 - 负责人总数: {perf.total_assignees}")
    print(f"  总分派数: {perf.total_assigned}")
    print(f"  总已处理: {perf.total_resolved}")
    print(f"  总待处理: {perf.total_pending}")
    print(f"  整体按时率: {perf.overall_on_time_rate}%")
    print(f"  整体自动闭环率: {perf.overall_auto_resolve_rate}%")
    print(f"  整体平均处理时长: {perf.overall_avg_resolve_hours}小时")

    print(f"  各负责人明细：")
    for item in perf.items:
        print(f"    {item.assignee}: 分派{item.total_assigned}条, 已处理{item.resolved_count}条, 待处理{item.pending_count}条")
        print(f"      按时{item.on_time_count}条, 超时{item.overdue_count}条, 按时率{item.on_time_rate}%")
        print(f"      自动闭环{item.auto_resolved_count}条, 自动闭环率{item.auto_resolve_rate}%")
        print(f"      平均处理时长: {item.avg_resolve_hours}小时")

    assert perf.total_assignees >= 2, "应该至少有2个负责人"
    assert perf.total_assigned >= 4, "应该至少分派了4条"

    wang = next((i for i in perf.items if i.assignee == "客服小王"), None)
    assert wang is not None, "应该有客服小王"
    assert wang.total_assigned == 2, "客服小王应该分派了2条"
    assert wang.on_time_count >= 1, "客服小王应该有按时完成的"

    li = next((i for i in perf.items if i.assignee == "客服小李"), None)
    assert li is not None, "应该有客服小李"
    assert li.overdue_count >= 1, "客服小李应该有超时的"

    perf_clinic1 = stats.get_assignee_performance(clinic_id=data["clinics"][0].id)
    print(f"  门店1筛选后负责人数量: {perf_clinic1.total_assignees}")
    assert perf_clinic1.total_assignees >= 1

    print("  ✅ 负责人绩效统计测试通过")
    db.close()


def test_export_alignment_with_detail():
    print("\n=== 测试5：导出信息与详情/列表对齐 ===")
    db = SessionLocal()
    setup_test_data(db)
    engine = AlertEngine(db)
    stats = StatsService(db)

    pending = engine.get_alerts_by_clinic(status="待处理")
    if pending:
        aid = pending[0].id
        engine.assign_alert(aid, assignee="客服小赵", deadline=datetime.now() + timedelta(days=3), assigned_by="运营张主管")
        engine.resolve_alert(aid, operator="客服小赵", resolved_note="测试对齐")

        detail = engine.get_alert_detail(aid)
        export_list = stats.export_high_value_list(status="已处理")
        export_item = next((i for i in export_list.items if i.alert_title == detail.title), None)

        if export_item:
            print(f"  预警标题: {detail.title}")
            print(f"  详情 - 状态: {detail.status}, 处理人: {detail.resolved_by}")
            print(f"  导出 - 状态: {export_item.status}, 处理人: {export_item.resolved_by}")
            print(f"  详情 - 处理详情: {detail.resolved_detail}")
            print(f"  导出 - 处理详情: {export_item.resolved_detail}")
            print(f"  详情 - assignee: {detail.assignee}")
            print(f"  导出 - assignee: {export_item.assignee}")

            assert detail.status == export_item.status, "状态应该一致"
            assert detail.resolved_by == export_item.resolved_by, "处理人应该一致"
            assert detail.resolved_detail == export_item.resolved_detail, "处理详情应该一致"
            assert detail.assignee == export_item.assignee, "负责人应该一致"

    print("  ✅ 导出与详情信息对齐测试通过")
    db.close()


if __name__ == "__main__":
    print("洁治后流失预警后端服务 - 第四轮单元测试")
    print("=" * 60)

    try:
        test_batch_assign()
        test_export_multi_filter()
        test_export_resolved_alerts_complete_info()
        test_assignee_performance()
        test_export_alignment_with_detail()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
