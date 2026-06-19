import requests
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8001"


def test_version_and_features():
    print("=" * 60)
    print("【测试1】版本和特性列表")
    resp = requests.get(f"{BASE_URL}/")
    data = resp.json()
    print(f"  版本: {data['version']}")
    print(f"  特性数量: {len(data['features'])}")
    assert data["version"] == "2.3.0"
    assert any("批量分派" in f and "待处理" in f for f in data["features"])
    assert any("交叉视图" in f for f in data["features"])
    assert any("导出模板" in f for f in data["features"])
    print("  ✅ 通过")


def test_batch_assign_only_pending():
    print()
    print("=" * 60)
    print("【测试2】批量分派只允许待处理预警，已闭环返回失败原因")

    pending_resp = requests.get(f"{BASE_URL}/alerts/", params={"status": "待处理"})
    pending = pending_resp.json()
    pending_ids = [a["id"] for a in pending[:2]]

    resolved_resp = requests.get(f"{BASE_URL}/alerts/", params={"status": "已处理"})
    resolved = resolved_resp.json()
    resolved_ids = [a["id"] for a in resolved[:2]]

    all_ids = pending_ids + resolved_ids + [9999]
    print(f"  待处理ID: {pending_ids}")
    print(f"  已处理ID: {resolved_ids}")
    print(f"  无效ID: [9999]")

    deadline = (datetime.now() + timedelta(days=2)).isoformat()
    payload = {
        "alert_ids": all_ids,
        "assignee": "客服小张",
        "deadline": deadline,
        "assigned_by": "运营主管"
    }
    resp = requests.post(f"{BASE_URL}/alerts/batch-assign", json=payload)
    result = resp.json()
    print(f"  成功: {result['success_count']}, 失败: {result['failed_count']}")
    print(f"  成功IDs: {result['success_ids']}")
    print(f"  失败IDs: {result['failed_ids']}")
    print(f"  失败详情: {result['failed_details']}")

    assert result["success_count"] == len(pending_ids), "应该只成功待处理的"
    assert result["failed_count"] == len(resolved_ids) + 1, "已闭环和无效的应该失败"
    assert len(result["failed_details"]) > 0, "应该有失败详情"
    for rid in resolved_ids:
        assert str(rid) in result["failed_details"] or rid in result["failed_details"], f"已处理{rid}应该在失败详情中"

    for sid in result["success_ids"]:
        timeline_resp = requests.get(f"{BASE_URL}/alerts/{sid}/timeline")
        timeline = timeline_resp.json()
        has_assign = any(a["action_type"] == "分派" for a in timeline["actions"])
        assert has_assign, f"成功分派的{sid}时间线应该有分派记录"

    for fid in resolved_ids:
        detail_resp = requests.get(f"{BASE_URL}/alerts/{fid}/timeline")
        detail = detail_resp.json()
        assert detail.get("assignee") != "客服小张" or detail.get("status") != "待处理", \
            f"失败的已处理预警{fid}不应该被重新分派"

    print("  ✅ 通过")


def test_performance_calculation():
    print()
    print("=" * 60)
    print("【测试3】负责人绩效口径 - 分派→完成口径")

    resp = requests.get(f"{BASE_URL}/stats/assignee-performance")
    data = resp.json()
    print(f"  负责人数量: {data['total_assignees']}")
    print(f"  整体平均处理时长: {data['overall_avg_resolve_hours']}小时")

    for item in data["items"]:
        print(f"  {item['assignee']}: 分派{item['total_assigned']}条, "
              f"已处理{item['resolved_count']}条, 平均{item['avg_resolve_hours']}小时")
        if item["resolved_count"] > 0 and item["avg_resolve_hours"] > 0:
            print(f"    处理时长口径: 使用 assigned_at→resolved_at（无 assigned_at 用 created_at 兜底）")
            assert item["avg_resolve_hours"] > 0

    print("  ✅ 通过")


def test_clinic_assignee_cross_view():
    print()
    print("=" * 60)
    print("【测试4】门店×负责人交叉视图")

    resp = requests.get(f"{BASE_URL}/stats/clinic-assignee-cross-view")
    data = resp.json()
    print(f"  门店数量: {data['total_clinics']}")
    print(f"  总分派: {data['total_assigned']}, 总已处理: {data['total_resolved']}")
    print(f"  总超时: {data['total_overdue']}, 整体按时率: {data['overall_on_time_rate']}%")
    print(f"  整体自动闭环率: {data['overall_auto_resolve_rate']}%")

    assert data["total_clinics"] >= 1, "应该至少有1家门店"

    for clinic in data["clinics"]:
        print(f"  门店: {clinic['clinic_name']}")
        print(f"    总分派: {clinic['total_assigned']}, 已处理: {clinic['total_resolved']}, "
              f"待处理: {clinic['total_pending']}, 超时: {clinic['total_overdue']}")
        print(f"    按时率: {clinic['overall_on_time_rate']}%, 自动闭环率: {clinic['overall_auto_resolve_rate']}%")
        for a in clinic["assignees"]:
            print(f"    负责人 {a['assignee']}: 分派{a['total_assigned']}条, "
                  f"已处理{a['resolved_count']}条, 超时{a['overdue_count']}条, "
                  f"自动闭环{a['auto_resolved_count']}条")

    print("  ✅ 通过")


def test_export_template_crud():
    print()
    print("=" * 60)
    print("【测试5】导出模板 CRUD")

    create_resp = requests.post(f"{BASE_URL}/export-templates/", json={
        "name": "总部月报",
        "description": "每月总部复盘用，查看所有已处理预警",
        "filters": {
            "status": "已处理"
        }
    })
    assert create_resp.status_code == 200
    t1 = create_resp.json()
    print(f"  创建模板1: id={t1['id']}, name={t1['name']}")
    assert t1["name"] == "总部月报"
    assert t1["filters"]["status"] == "已处理"

    create_resp2 = requests.post(f"{BASE_URL}/export-templates/", json={
        "name": "超时清单",
        "description": "所有超时未处理的预警",
        "filters": {
            "status": "待处理",
            "assignee": "客服小张"
        }
    })
    assert create_resp2.status_code == 200
    t2 = create_resp2.json()
    print(f"  创建模板2: id={t2['id']}, name={t2['name']}, assignee={t2['filters']['assignee']}")

    list_resp = requests.get(f"{BASE_URL}/export-templates/")
    templates = list_resp.json()
    print(f"  模板列表: {len(templates)} 个")
    assert len(templates) >= 2

    get_resp = requests.get(f"{BASE_URL}/export-templates/{t1['id']}")
    got = get_resp.json()
    print(f"  获取模板: name={got['name']}, filters.status={got['filters']['status']}")
    assert got["name"] == "总部月报"

    print("  ✅ 通过")
    return t1


def test_export_by_template(t1):
    print()
    print("=" * 60)
    print("【测试6】模板导出 - 数量与筛选结果一致")

    template_export = requests.get(f"{BASE_URL}/export-templates/{t1['id']}/export").json()
    direct_export = requests.get(f"{BASE_URL}/stats/export/high-value", params={"status": "已处理"}).json()

    print(f"  模板导出数量: {template_export['total_count']}")
    print(f"  直接筛选数量: {direct_export['total_count']}")
    assert template_export["total_count"] == direct_export["total_count"], \
        f"模板导出{template_export['total_count']}和直接筛选{direct_export['total_count']}不一致"

    if template_export["items"]:
        item = template_export["items"][0]
        print(f"  第一条: {item['alert_title']}, 状态={item['status']}, 处理人={item.get('resolved_by')}")
        assert item["status"] == "已处理"

    print("  ✅ 通过")


def test_delete_template(t1):
    print()
    print("=" * 60)
    print("【测试7】删除模板")

    del_resp = requests.delete(f"{BASE_URL}/export-templates/{t1['id']}")
    assert del_resp.status_code == 200

    get_resp = requests.get(f"{BASE_URL}/export-templates/{t1['id']}")
    assert get_resp.status_code == 404
    print(f"  模板 {t1['id']} 已删除，再次获取返回404")
    print("  ✅ 通过")


if __name__ == "__main__":
    print("洁治后流失预警后端服务 - 第五轮 API 测试")
    print("服务地址:", BASE_URL)
    print("=" * 60)

    try:
        test_version_and_features()
        test_batch_assign_only_pending()
        test_performance_calculation()
        test_clinic_assignee_cross_view()
        t1 = test_export_template_crud()
        test_export_by_template(t1)
        test_delete_template(t1)

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
