"""结果分析模块：失败归因与修复建议。"""

from __future__ import annotations

FAILURE_TAXONOMY = [
    "product_bug",
    "env_issue",
    "locator_issue",
    "data_issue",
    "oracle_ambiguous",
    "agent_execution_error",
    "case_design_issue",
]


def _extract_evidence(result: dict) -> str:
    for action in result.get("action_decisions", []):
        if action.get("decision") in ("fail", "handoff"):
            return action.get("observation", "")
    trace = result.get("execution_trace", [])
    return trace[-1] if trace else "无证据"


def _classify_failure(result: dict) -> tuple[str | None, str, str, str]:
    status = result.get("status", "unknown")
    if status == "pass":
        return None, "", "用例执行成功，无需修复", "continue"

    hint = result.get("failure_hint")
    evidence = _extract_evidence(result)
    evidence_lower = evidence.lower()

    if hint == "product_bug":
        return (
            "product_bug",
            evidence,
            "产品行为不符合需求：业务断言失败",
            "file_bug",
        )

    if hint == "locator_issue":
        return (
            "locator_issue",
            evidence,
            "定位器不稳定或元素状态与预期不符",
            "update_locator",
        )

    if hint == "oracle_ambiguous" or status == "unknown":
        return (
            "oracle_ambiguous",
            evidence,
            "支付结果 Oracle 定义不唯一，成功/失败文案冲突",
            "refine_oracle",
        )

    if "not clickable" in evidence_lower or "element not found" in evidence_lower:
        return (
            "locator_issue",
            evidence,
            "定位器不稳定或元素状态与预期不符",
            "update_locator",
        )

    if "空态" in evidence or "未展示" in evidence or "blank" in evidence_lower:
        return (
            "product_bug",
            evidence,
            "产品行为不符合需求：业务断言失败",
            "file_bug",
        )

    if "timeout" in evidence_lower or "network" in evidence_lower or "503" in evidence:
        return (
            "env_issue",
            evidence,
            "测试环境或网络异常导致执行失败",
            "retry_with_recovery",
        )

    if "测试数据" in evidence or "库存" in evidence or "账号" in evidence:
        return (
            "data_issue",
            evidence,
            "测试数据不满足前置条件",
            "fix_test_data",
        )

    if "handoff" in evidence_lower or "agent" in evidence_lower:
        return (
            "agent_execution_error",
            evidence,
            "Agent 决策或执行策略错误",
            "retry_with_recovery",
        )

    return (
        "case_design_issue",
        evidence,
        "用例步骤或断言设计不清晰，导致无法稳定判定",
        "refine_case",
    )


def _repair_suggestion(failure_type: str | None, root_cause: str) -> str:
    suggestions = {
        "product_bug": "提交 Bug 至产品团队；增加回归用例并更新 known_product_bugs",
        "env_issue": "检查测试环境健康度，恢复后重试；记录 env_issue 避免误判为产品 Bug",
        "locator_issue": "切换 stable locator（如 #add-to-cart-btn）；将 flaky 步骤写入 asset_memory",
        "data_issue": "更新 mock 数据或测试账号，确保前置数据满足 oracle",
        "oracle_ambiguous": "与产品/QA 澄清 oracle，改写为可机器判定的单一断言",
        "agent_execution_error": "调整 Agent prompt 或 recovery_strategy，增加 wait/retry",
        "case_design_issue": "拆分步骤、补充 hard_checks，更新 repaired_cases",
    }
    base = suggestions.get(failure_type or "", "Review execution trace and refine case")
    return f"{base}。根因：{root_cause}"


def analyze_outcome(result: dict) -> dict:
    """分析单条执行结果。"""
    case_id = result.get("case_id", "unknown")
    status = result.get("status", "unknown")
    failure_type, evidence, root_cause, next_action = _classify_failure(result)

    return {
        "case_id": case_id,
        "status": status,
        "failure_type": failure_type,
        "evidence": evidence,
        "root_cause": root_cause,
        "repair_suggestion": _repair_suggestion(failure_type, root_cause),
        "next_action": next_action if status != "pass" else "continue",
        "target": _extract_target(result),
    }


def _extract_target(result: dict) -> str:
    for action in result.get("action_decisions", []):
        if action.get("decision") in ("fail", "handoff"):
            return action.get("target", "")
    return ""


def analyze_outcomes(execution_results: list[dict]) -> list[dict]:
    """批量分析执行结果。"""
    return [analyze_outcome(r) for r in execution_results]
