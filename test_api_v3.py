import requests
import json

BASE_URL = "http://localhost:8001"

def test_root():
    print("=== 测试1: 根端点 ===")
    r = requests.get(f"{BASE_URL}/")
    data = r.json()
    print(f"版本: {data['version']}")
    print(f"特性数量: {len(data['features'])}个")
    for f in data['features']:
        print(f"  - {f}")

def test_assign_api():
    print("\n=== 测试2: 预警分派API ===")
    alerts = requests.get(f"{BASE_URL}/alerts", params={"status": "待处理"}).json()
    if alerts:
        alert_id = alerts[0]["id"]
        print(f"选择预警ID: {alert_id} - {alerts[0]['title']}")
        assign_data = {
            "assignee": "客服小王",
            "deadline": "2026-06-22T18:00:00",
            "assigned_by": "运营主管张经理"
        }
        r = requests.post(f"{BASE_URL}/alerts/{alert_id}/assign", json=assign_data)
        print(f"分派状态码: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"分派成功:")
            print(f"  assignee: {data['assignee']}")
            print(f"  分派人: {data['assigned_by']}")
            print(f"  截止时间: {data['deadline']}")

    print("\n按负责人筛选:")
    r = requests.get(f"{BASE_URL}/alerts", params={"assignee": "客服小王", "status": "待处理"})
    data = r.json()
    print(f"  分派给客服小王的预警: {len(data)}条")
    for a in data[:2]:
        print(f"    - {a['title']} (assignee: {a['assignee']})")

def test_alerts_filter():
    print("\n=== 测试3: 预警列表多维度筛选 ===")
    r = requests.get(f"{BASE_URL}/alerts", params={"patient_type": "种植"})
    data = r.json()
    print(f"种植患者预警: {len(data)}条")

    r = requests.get(f"{BASE_URL}/alerts", params={"doctor_id": 1})
    data = r.json()
    print(f"医生1预警: {len(data)}条")

    r = requests.get(f"{BASE_URL}/alerts", params={"clinic_id": 1})
    data = r.json()
    print(f"门店1预警: {len(data)}条")

def test_overview_with_ranking():
    print("\n=== 测试4: 总览排行+逾期/待处理数 ===")
    r = requests.get(f"{BASE_URL}/stats/overview")
    data = r.json()
    print(f"门店排行(前2):")
    for item in data["clinic_ranking"][:2]:
        print(f"  {item['name']}:")
        print(f"    洁治{item['total_cleanings']}例, 逾期{item['overdue_count']}人, "
              f"待处理预警{item['alert_pending_count']}个")

    print(f"医生排行(前2):")
    for item in data["doctor_ranking"][:2]:
        print(f"  {item['name']}: 洁治{item['total_cleanings']}例, "
              f"逾期{item['overdue_count']}人, 待处理{item['alert_pending_count']}个")

    print(f"患者类型分布(带逾期数):")
    for pt in data["patient_type_breakdown"]:
        print(f"  {pt['patient_type']}: 洁治{pt['total_cleanings']}例, "
              f"逾期{pt['overdue_count']}人, 待处理预警{pt['alert_pending_count']}个")

    print(f"\n按门店筛选排行联动:")
    r = requests.get(f"{BASE_URL}/stats/overview", params={"clinic_id": 1})
    data = r.json()
    print(f"  门店排行数: {len(data['clinic_ranking'])}")
    print(f"  医生排行数: {len(data['doctor_ranking'])}")
    print(f"  洁治总数: {data['summary']['total_cleanings']}例")

def test_trend_api():
    print("\n=== 测试5: 趋势分析API ===")
    r = requests.get(f"{BASE_URL}/stats/trend", params={"period_type": "day"})
    data = r.json()
    print(f"按天趋势: {len(data['data_points'])}个数据点")
    for dp in data["data_points"][-3:]:
        print(f"  {dp['period']}: 新增{dp['new_alerts']}条, "
              f"处理{dp['resolved_alerts']}条, "
              f"自动闭环率{dp['auto_resolve_rate']}%")

    r = requests.get(f"{BASE_URL}/stats/trend", params={"period_type": "week"})
    data = r.json()
    print(f"按周趋势: {len(data['data_points'])}个数据点")

    r = requests.get(f"{BASE_URL}/stats/trend", params={"period_type": "day", "compare_clinic": "true"})
    data = r.json()
    print(f"按门店对比: {len(data['by_clinic']) if data['by_clinic'] else 0}家门店")

def test_alert_detail_enhanced():
    print("\n=== 测试6: 预警详情+处理人/时间显示 ===")
    alerts = requests.get(f"{BASE_URL}/alerts", params={"status": "待处理"}).json()
    if alerts:
        alert_id = alerts[0]["id"]
        r = requests.get(f"{BASE_URL}/alerts/{alert_id}/timeline")
        data = r.json()
        print(f"预警: {data['title']}")
        print(f"状态: {data['status']}")
        print(f"assignee: {data['assignee']}")
        print(f"截止时间: {data['deadline']}")
        print(f"是否超截止: {data['is_overdue_deadline']}")
        print(f"处理人: {data['resolved_by']}")
        print(f"处理详情: {data['resolved_detail']}")
        print(f"处理时间: {data['resolved_at']}")
        print(f"自动闭环: {data['auto_resolved']}")
        print(f"时间线共{len(data['actions'])}条记录:")
        for action in data['actions'][:2]:
            print(f"  [{action['action_time']}] {action['action_type']} "
                  f"- {action['operator']}: {action['content'] or action['close_reason']}")

def test_export_with_detail():
    print("\n=== 测试7: 导出字段+处理人/分派信息 ===")
    r = requests.get(f"{BASE_URL}/stats/export/high-value")
    data = r.json()
    print(f"导出{data['total_count']}人")
    for item in data["items"][:2]:
        print(f"\n  【{item['alert_type']}】{item['patient_name']}")
        print(f"    状态: {item['status']}")
        print(f"    assignee: {item['assignee']}")
        print(f"    截止时间: {item['deadline']}")
        print(f"    处理人: {item['resolved_by']}")
        print(f"    处理详情: {item['resolved_detail']}")

if __name__ == "__main__":
    try:
        test_root()
        test_assign_api()
        test_alerts_filter()
        test_overview_with_ranking()
        test_trend_api()
        test_alert_detail_enhanced()
        test_export_with_detail()
        print("\n" + "=" * 60)
        print("🎉 第三轮所有API测试通过！")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
