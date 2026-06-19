import requests
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8001"


def test_version_and_features():
    print("=" * 60)
    print("【测试1】版本和特性列表")
    print("=" * 60)
    resp = requests.get(f"{BASE_URL}/")
    data = resp.json()
    print(f"  版本: {data['version']}")
    print(f"  特性数量: {len(data['features'])}")
    for f in data['features']:
        print(f"    - {f}")
    assert data["version"] == "2.2.0", "版本号应该是 2.2.0"
    assert len(data["features"]) >= 11, "应该至少有11个特性"
    assert any("批量分派" in f for f in data["features"]), "应该有批量分派特性"
    assert any("负责人绩效" in f for f in data["features"]), "应该有负责人绩效特性"
    assert any("多维度导出" in f for f in data["features"]), "应该有多维度导出特性"
    print("  ✅ 版本和特性测试通过")


def test_batch_assign_api():
    print()
    print("=" * 60)
    print("【测试2】批量分派 API")
    print("=" * 60)

    resp = requests.get(f"{BASE_URL}/alerts/", params={"status": "待处理"})
    alerts = resp.json()
    pending_ids = [a["id"] for a in alerts[:3]]
    print(f"  选 {len(pending_ids)} 条待处理预警进行批量分派")
    print(f"  预警ID: {pending_ids}")

    deadline = (datetime.now() + timedelta(days=2)).isoformat()
    payload = {
        "alert_ids": pending_ids + [9999],
        "assignee": "客服小李",
        "deadline": deadline,
        "assigned_by": "运营张主管"
    }
    resp = requests.post(f"{BASE_URL}/alerts/batch-assign", json=payload)
    print(f"  响应状态码: {resp.status_code}")
    result = resp.json()
    print(f"  成功数: {result['success_count']}")
    print(f"  失败数: {result['failed_count']}")
    print(f"  成功IDs: {result['success_ids']}")
    print(f"  失败IDs: {result['failed_ids']}")
    assert resp.status_code == 200, "状态码应该是 200"
    assert result["success_count"] == 3, "应该成功3条"
    assert result["failed_count"] == 1, "应该失败1条（无效ID）"
    assert 9999 in result["failed_ids"], "无效ID应该在失败列表中"

    resp2 = requests.get(f"{BASE_URL}/alerts/", params={"assignee": "客服小李"})
    assigned = resp2.json()
    print(f"  按负责人'客服小李'筛选，查到 {len(assigned)} 条")
    assert len(assigned) >= 3, "分派后应该能查到至少3条"

    if assigned:
        first = assigned[0]
        print(f"  第一条：assignee={first['assignee']}, assigned_by={first['assigned_by']}")
        timeline_resp = requests.get(f"{BASE_URL}/alerts/{first['id']}/timeline")
        timeline = timeline_resp.json()
        has_batch_assign = any(
            a["action_type"] == "分派" and "批量" in (a["content"] or "")
            for a in timeline["actions"]
        )
        print(f"  时间线有批量分派记录: {has_batch_assign}")
        assert has_batch_assign, "时间线应该有批量分派记录"

    print("  ✅ 批量分派 API 测试通过")


def test_assignee_performance_api():
    print()
    print("=" * 60)
    print("【测试3】负责人绩效统计 API")
    print("=" * 60)

    resp = requests.get(f"{BASE_URL}/stats/assignee-performance")
    data = resp.json()
    print(f"  响应状态码: {resp.status_code}")
    print(f"  负责人总数: {data['total_assignees']}")
    print(f"  总分派数: {data['total_assigned']}")
    print(f"  总已处理: {data['total_resolved']}")
    print(f"  总待处理: {data['total_pending']}")
    print(f"  整体按时率: {data['overall_on_time_rate']}%")
    print(f"  整体自动闭环率: {data['overall_auto_resolve_rate']}%")
    print(f"  整体平均处理时长: {data['overall_avg_resolve_hours']}小时")
    assert resp.status_code == 200
    assert "items" in data
    print(f"  负责人数量: {len(data['items'])}")

    if data["items"]:
        first = data["items"][0]
        print(f"  第一名: {first['assignee']}")
        print(f"    分派: {first['total_assigned']}条")
        print(f"    已处理: {first['resolved_count']}条")
        print(f"    待处理: {first['pending_count']}条")
        print(f"    按时: {first['on_time_count']}条")
        print(f"    超时: {first['overdue_count']}条")
        print(f"    自动闭环: {first['auto_resolved_count']}条")
        print(f"    按时率: {first['on_time_rate']}%")
        print(f"    自动闭环率: {first['auto_resolve_rate']}%")
        print(f"    平均处理时长: {first['avg_resolve_hours']}小时")
        for key in ["assignee", "total_assigned", "resolved_count", "pending_count",
                     "on_time_count", "overdue_count", "auto_resolved_count",
                     "on_time_rate", "auto_resolve_rate", "avg_resolve_hours"]:
            assert key in first, f"缺少字段: {key}"

    resp_clinic = requests.get(f"{BASE_URL}/stats/assignee-performance", params={"clinic_id": 1})
    data_clinic = resp_clinic.json()
    print(f"  按门店1筛选后，负责人数量: {data_clinic['total_assignees']}")
    assert resp_clinic.status_code == 200

    print("  ✅ 负责人绩效统计 API 测试通过")


def test_export_multi_filter_api():
    print()
    print("=" * 60)
    print("【测试4】导出多维度筛选 API")
    print("=" * 60)

    resp_default = requests.get(f"{BASE_URL}/stats/export/high-value")
    data_default = resp_default.json()
    print(f"  默认导出（待处理重点）: {data_default['total_count']} 条")
    print(f"    高价值: {data_default['high_value_count']}")
    print(f"    未转化: {data_default['unconverted_count']}")

    resp_resolved = requests.get(f"{BASE_URL}/stats/export/high-value", params={"status": "已处理"})
    data_resolved = resp_resolved.json()
    print(f"  按状态'已处理'筛选: {data_resolved['total_count']} 条")

    resp_type = requests.get(f"{BASE_URL}/stats/export/high-value", params={"alert_type": "未随访"})
    data_type = resp_type.json()
    print(f"  按类型'未随访'筛选: {data_type['total_count']} 条")
    for item in data_type["items"]:
        assert item["alert_type"] == "未随访"

    resp_assignee = requests.get(f"{BASE_URL}/stats/export/high-value", params={"assignee": "客服小李"})
    data_assignee = resp_assignee.json()
    print(f"  按负责人'客服小李'筛选: {data_assignee['total_count']} 条")

    resp_clinic = requests.get(f"{BASE_URL}/stats/export/high-value", params={"clinic_id": 1})
    data_clinic = resp_clinic.json()
    print(f"  按门店1筛选: {data_clinic['total_count']} 条, 门店名: {data_clinic.get('clinic_name')}")

    print("  ✅ 导出多维度筛选 API 测试通过")


def test_resolved_alert_export_info():
    print()
    print("=" * 60)
    print("【测试5】已处理预警导出信息完整")
    print("=" * 60)

    resp = requests.get(f"{BASE_URL}/alerts/", params={"status": "待处理", "alert_type": "未随访"})
    alerts = resp.json()
    if alerts:
        aid = alerts[0]["id"]
        print(f"  选择预警 {aid} 手动关闭")
        close_resp = requests.post(
            f"{BASE_URL}/alerts/{aid}/resolve",
            json={"operator": "客服小王", "resolved_note": "API测试关闭"}
        )
        print(f"  关闭响应状态码: {close_resp.status_code}")

    resp_export = requests.get(f"{BASE_URL}/stats/export/high-value", params={"status": "已处理"})
    data = resp_export.json()
    print(f"  已处理预警数量: {data['total_count']}")

    if data["items"]:
        item = data["items"][0]
        print(f"  第一条已处理预警：")
        print(f"    状态: {item['status']}")
        print(f"    处理人: {item.get('resolved_by')}")
        print(f"    处理时间: {item.get('resolved_at')}")
        print(f"    处理详情: {item.get('resolved_detail')}")
        print(f"    是否自动闭环: {item.get('auto_resolved')}")
        print(f"    assignee: {item.get('assignee')}")
        print(f"    deadline: {item.get('deadline')}")
        for key in ["status", "resolved_by", "resolved_at", "resolved_detail",
                     "auto_resolved", "assignee", "deadline"]:
            assert key in item, f"导出项缺少字段: {key}"

    print("  ✅ 已处理预警导出信息测试通过")


def test_detail_export_alignment():
    print()
    print("=" * 60)
    print("【测试6】详情与导出信息对齐")
    print("=" * 60)

    resp = requests.get(f"{BASE_URL}/alerts/", params={"status": "已处理"})
    alerts = resp.json()
    if alerts:
        first_alert = alerts[0]
        aid = first_alert["id"]
        detail_resp = requests.get(f"{BASE_URL}/alerts/{aid}/timeline")
        detail = detail_resp.json()

        export_resp = requests.get(f"{BASE_URL}/stats/export/high-value", params={"status": "已处理"})
        export_data = export_resp.json()
        export_item = next((i for i in export_data["items"] if i["alert_title"] == detail["title"]), None)

        if export_item:
            print(f"  预警标题: {detail['title']}")
            print(f"  状态 - 详情: {detail['status']}, 导出: {export_item['status']}")
            assert detail["status"] == export_item["status"]
            print(f"  处理人 - 详情: {detail.get('resolved_by')}, 导出: {export_item.get('resolved_by')}")
            assert detail.get("resolved_by") == export_item.get("resolved_by")
            print(f"  处理详情 - 详情: {detail.get('resolved_detail')}, 导出: {export_item.get('resolved_detail')}")
            assert detail.get("resolved_detail") == export_item.get("resolved_detail")
            print(f"  assignee - 详情: {detail.get('assignee')}, 导出: {export_item.get('assignee')}")
            assert detail.get("assignee") == export_item.get("assignee")
            print(f"  是否自动闭环 - 详情: {detail.get('auto_resolved')}, 导出: {export_item.get('auto_resolved')}")
            assert detail.get("auto_resolved") == export_item.get("auto_resolved")

    print("  ✅ 详情与导出信息对齐测试通过")


if __name__ == "__main__":
    print("洁治后流失预警后端服务 - 第四轮 API 测试")
    print("服务地址:", BASE_URL)
    print("=" * 60)

    try:
        test_version_and_features()
        test_batch_assign_api()
        test_assignee_performance_api()
        test_export_multi_filter_api()
        test_resolved_alert_export_info()
        test_detail_export_alignment()

        print("\n" + "=" * 60)
        print("🎉 所有 API 测试通过！")
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
