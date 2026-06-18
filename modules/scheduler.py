"""测试用例调度模块：按优先级与风险排序。"""

from __future__ import annotations

PRIORITY_WEIGHT = {"P0": 0, "P1": 1, "P2": 2}
RISK_BOOST = {"payment": -2, "checkout": -1, "critical": -2, "regression": -1}


def _case_sort_key(case: dict) -> tuple:
    priority = case.get("priority", "P2")
    weight = PRIORITY_WEIGHT.get(priority, 2)

    risk_tags = case.get("risk_tags", [])
    if isinstance(risk_tags, str):
        risk_tags = [risk_tags]

    boost = 0
    for tag in risk_tags:
        boost += RISK_BOOST.get(tag, 0)

    risk_level = case.get("risk_level", "")
    if risk_level == "critical":
        boost -= 2
    elif risk_level == "high":
        boost -= 1

    return (weight + boost, case.get("case_id", ""))


def _build_reason(case: dict) -> str:
    parts = []
    priority = case.get("priority", "P2")
    parts.append(f"优先级 {priority}")

    source = case.get("source", "manual")
    if source == "regression":
        parts.append("历史 Bug 回归")
    elif source == "testpoint":
        parts.append("PRD 测试点衍生")

    risk_tags = case.get("risk_tags", [])
    if risk_tags:
        parts.append(f"风险标签: {', '.join(risk_tags)}")

    if case.get("risk_level") in ("critical", "high"):
        parts.append(f"风险等级 {case['risk_level']}")

    return "；".join(parts)


def schedule_cases(
    testpoints: list[dict] | None = None,
    agent_cases: list[dict] | None = None,
    regression_cases: list[dict] | None = None,
) -> list[dict]:
    """生成执行计划，按 priority 和 risk_tags 排序。"""
    all_cases: list[dict] = []

    if agent_cases:
        all_cases.extend(agent_cases)
    if regression_cases:
        all_cases.extend(regression_cases)

    if testpoints and not all_cases:
        for tp in testpoints:
            all_cases.append(
                {
                    "case_id": tp["testpoint_id"].replace("TP-", "CASE-"),
                    "priority": tp.get("priority", "P2"),
                    "risk_tags": tp.get("risk_tags", []),
                    "source": "testpoint",
                    "goal": tp.get("user_goal", ""),
                    "oracle": tp.get("oracle", ""),
                }
            )

    seen_ids: set[str] = set()
    unique_cases: list[dict] = []
    for case in all_cases:
        cid = case.get("case_id", "")
        if cid and cid not in seen_ids:
            seen_ids.add(cid)
            unique_cases.append(case)

    sorted_cases = sorted(unique_cases, key=_case_sort_key)

    plan: list[dict] = []
    for order, case in enumerate(sorted_cases, start=1):
        plan.append(
            {
                "order": order,
                "case_id": case.get("case_id", f"CASE-{order}"),
                "priority": case.get("priority", "P2"),
                "reason": _build_reason(case),
                "case": case,
            }
        )

    return plan
