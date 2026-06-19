import requests
import json

BASE_URL = "http://localhost:8001"

def test_root():
    print("=== 测试1: 根端点 ===")
    r = requests.get(f"{BASE_URL}/")
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))

def test_overview():
    print("\n=== 测试2: 总览统计 ===")
    r = requests.get(f"{BASE_URL}/stats/overview")
    data = r.json()
    print(f"汇总: {data['summary']['total_cleanings']}例洁治, "
          f"随访率{data['summary']['overall_followup_rate']}%, "
          f"待处理预警{data['summary']['total_alerts_pending']}个")
    print(f"门店排行前2: {[x['name'] for x in data['clinic_ranking'][:2]]}")
    print(f"医生排行前2: {[x['name'] for x in data['doctor_ranking'][:2]]}")
    print(f"患者类型: {[x['patient_type'] for x in data['patient_type_breakdown']]}")

def test_patient_history():
    print("\n=== 测试3: 患者预警历史 ===")
    r = requests.get(f"{BASE_URL}/patients/4/alert-history")
    data = r.json()
    print(f"患者: {data['patient_name']}, 电话: {data['patient_phone']}")
    print(f"总预警{data['total_alerts']}个, 待处理{data['pending_alerts']}个, "
          f"已处理{data['resolved_alerts']}个")
    print(f"处理记录共{len(data['actions'])}条:")
    for action in data['actions'][:3]:
        print(f"  - [{action['action_time']}] {action['action_type']} "
              f"- {action['operator']}: {action['content'] or action['close_reason']}")

def test_clinic_config():
    print("\n=== 测试4: 门店配置 ===")
    config_data = {
        "clinic_id": 1,
        "followup_days_threshold": 2,
        "implant_interval_days": 25,
        "orthodontics_interval_days": 18,
        "periodontal_interval_days": 12,
        "regular_interval_days": 6
    }
    r = requests.post(f"{BASE_URL}/clinics/1/config", json=config_data)
    print(f"配置创建状态: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"随访阈值: {data['followup_days_threshold']}天 (默认3天)")
        print(f"种植周期: {data['implant_interval_days']}天 (默认30天)")
        print(f"正畸周期: {data['orthodontics_interval_days']}天 (默认21天)")
        print(f"牙周周期: {data['periodontal_interval_days']}天 (默认14天)")
    else:
        print(f"错误: {r.text}")

def test_add_action():
    print("\n=== 测试5: 追加处理动作 ===")
    action_data = {
        "alert_id": 8,
        "action_type": "电话",
        "action_time": "2026-06-20T10:30:00",
        "operator": "运营主管-张经理",
        "contact_method": "手机",
        "content": "已与患者确认，预约下周二复诊"
    }
    r = requests.post(f"{BASE_URL}/alerts/8/actions", json=action_data)
    print(f"追加动作状态: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"动作已记录: {data['action_type']} - {data['operator']}: {data['content']}")
    else:
        print(f"错误: {r.text}")

def test_alert_timeline():
    print("\n=== 测试6: 预警详情+时间线 ===")
    r = requests.get(f"{BASE_URL}/alerts/8/timeline")
    data = r.json()
    print(f"预警: {data['title']}")
    print(f"患者: {data['patient_name']}, 电话: {data['patient_phone']}")
    print(f"状态: {data['status']}, 责任人: {data['responsible_person']}")
    print(f"处理时间线（共{len(data['actions'])}条）:")
    for action in data['actions'][:3]:
        print(f"  - [{action['action_time']}] {action['action_type']} "
              f"- {action['operator']}: {action['content'] or action['close_reason']}")

def test_export():
    print("\n=== 测试7: 重点名单导出 ===")
    r = requests.get(f"{BASE_URL}/stats/export/high-value")
    data = r.json()
    print(f"导出时间: {data['export_time']}")
    print(f"导出{data['total_count']}人: 高价值{data['high_value_count']}人, "
          f"未转化{data['unconverted_count']}人")
    for item in data['items']:
        print(f"\n  【{item['alert_type']}】{item['patient_name']}")
        print(f"    门店: {item['clinic_name']}")
        print(f"    患者类型: {item['patient_type']}")
        print(f"    责任医生: {item['doctor_name']}")
        print(f"    联系电话: {item['patient_phone']}")
        print(f"    逾期天数: {item['overdue_days']}天")
        print(f"    最近随访: {item['last_followup_content'] or '无'}")

def test_followup_submit():
    print("\n=== 测试8: 随访补录+自动关闭预警 ===")
    followup_data = {
        "cleaning_record_id": 1,
        "followup_time": "2026-06-20T11:00:00",
        "operator": "客服小李",
        "contact_method": "电话",
        "patient_feedback": "患者无不适，已预约半年后复查",
        "has_bleeding": False,
        "has_sensitivity": False,
        "has_pain": False,
        "next_step": "半年后复查"
    }
    r = requests.post(f"{BASE_URL}/followups/", json=followup_data)
    print(f"随访提交状态: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"随访ID: {data['followup_id']}")
        print(f"待处理预警: {data['pending_alerts']}个")
        print(f"自动关闭: {data['auto_resolved']}")
        print(f"关闭原因: {data['auto_resolved_reason']}")
    else:
        print(f"错误: {r.text}")

if __name__ == "__main__":
    try:
        test_root()
        test_overview()
        test_patient_history()
        test_clinic_config()
        test_add_action()
        test_alert_timeline()
        test_export()
        test_followup_submit()
        print("\n" + "=" * 60)
        print("🎉 所有第二轮API测试通过！")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
