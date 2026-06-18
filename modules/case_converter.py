"""自然语言用例转 Agent Case 模块。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

STEP_KEYWORDS: list[tuple[list[str], dict]] = [
    (
        ["登录", "login"],
        {
            "intent": "用户登录",
            "action": "fill_and_click",
            "locator_keys": ["login_username", "login_password", "login_button"],
            "description": "输入账号密码并点击登录",
            "hard_checks": ["页面跳转至首页", "展示用户昵称"],
            "observation_refs": ["screenshot://login_page", "dom://#login-btn"],
        },
    ),
    (
        ["搜索", "search", "查找"],
        {
            "intent": "搜索商品",
            "action": "search",
            "locator_keys": ["search_input", "search_button", "search_result_item"],
            "description": "输入关键词并执行搜索",
            "hard_checks": ["搜索结果列表可见", "至少一条商品结果"],
            "observation_refs": ["screenshot://search_results", "dom://.search-result-item"],
        },
    ),
    (
        ["购物车", "加购", "加入"],
        {
            "intent": "加入购物车",
            "action": "click",
            "locator_keys": ["add_to_cart_button", "cart_badge"],
            "description": "点击加入购物车并验证角标",
            "hard_checks": ["加购按钮可点击", "购物车角标 +1"],
            "observation_refs": ["screenshot://product_detail", "dom://#add-to-cart-btn"],
        },
    ),
    (
        ["下单", "结算", "checkout"],
        {
            "intent": "提交订单",
            "action": "click",
            "locator_keys": ["checkout_button"],
            "description": "进入结算页并提交订单",
            "hard_checks": ["生成待支付订单", "展示订单号"],
            "observation_refs": ["screenshot://checkout", "dom://#checkout-btn"],
        },
    ),
    (
        ["支付", "付款", "pay"],
        {
            "intent": "完成支付",
            "action": "click",
            "locator_keys": ["pay_button", "payment_result"],
            "description": "点击支付并验证支付结果",
            "hard_checks": ["支付结果状态唯一且明确"],
            "observation_refs": ["screenshot://payment_result", "dom://#payment-result"],
        },
    ),
]


def _resolve_locator(knowledge: dict, key: str, memory: dict | None) -> tuple[str, list[str]]:
    locators = knowledge.get("locators", {})
    loc = locators.get(key, {})
    stable = loc.get("stable", f"#{key}")
    warnings: list[str] = []

    memory = memory or {}
    for flaky in memory.get("flaky_steps", []):
        if key.replace("_", "") in flaky.get("step", "").replace("_", "") or key in flaky.get("note", ""):
            warnings.append(f"历史 flaky：{flaky.get('note', '')}")

    if key in memory.get("stable_locators", {}):
        stable = memory["stable_locators"][key]

    return stable, warnings


def _match_steps(natural_case: str) -> list[dict]:
    matched: list[dict] = []
    text = natural_case.lower()
    for keywords, step_def in STEP_KEYWORDS:
        if any(kw.lower() in text for kw in keywords):
            matched.append(deepcopy(step_def))
    if not matched:
        matched = [deepcopy(STEP_KEYWORDS[0][1]), deepcopy(STEP_KEYWORDS[1][1])]
    return matched


def convert_to_agent_case(
    natural_case: str,
    knowledge: dict,
    memory: dict | None = None,
) -> dict:
    """将自然语言用例转换为结构化 Agent Case。"""
    memory = memory or {}
    step_defs = _match_steps(natural_case)
    steps: list[dict] = []
    all_warnings: list[str] = []

    for idx, step_def in enumerate(step_defs, start=1):
        locator_keys = step_def.pop("locator_keys", [])
        primary_key = locator_keys[0] if locator_keys else "unknown"
        target, warnings = _resolve_locator(knowledge, primary_key, memory)
        all_warnings.extend(warnings)

        step_decision = {
            "intent": step_def["intent"],
            "target": target,
            "action": step_def["action"],
            "observation_refs": step_def["observation_refs"],
            "hard_checks": step_def["hard_checks"],
            "warnings": warnings,
            "decision": "wait" if warnings else "execute",
        }

        steps.append(
            {
                "step_no": idx,
                "description": step_def["description"],
                "step_decision": step_decision,
            }
        )

    hard_checks = []
    for s in steps:
        hard_checks.extend(s["step_decision"]["hard_checks"])
    hard_checks = list(dict.fromkeys(hard_checks))

    recovery_parts = []
    if all_warnings:
        recovery_parts.append("对 flaky 步骤先 wait 再 retry，必要时切换 stable locator")
    if memory.get("known_product_bugs"):
        recovery_parts.append("关注已知产品缺陷并在断言中加强空态/错误态校验")
    if not recovery_parts:
        recovery_parts.append("标准重试 2 次，仍失败则 handoff 人工")

    return {
        "case_id": "CASE-001",
        "goal": natural_case.strip(),
        "preconditions": [
            "测试账号可用（demo@test.com）",
            "网络与测试环境正常",
        ],
        "steps": steps,
        "expected_result": f"完成目标：{natural_case.strip()}",
        "hard_checks": hard_checks,
        "recovery_strategy": "；".join(recovery_parts),
    }


def testpoint_to_agent_case(testpoint: dict, knowledge: dict, memory: dict | None = None) -> dict:
    """将测试点转换为可执行的 Agent Case（供调度器使用）。"""
    natural = f"{testpoint['user_goal']}（{testpoint['feature']}）"
    case = convert_to_agent_case(natural, knowledge, memory)
    case["case_id"] = testpoint["testpoint_id"].replace("TP-", "CASE-")
    case["priority"] = testpoint.get("priority", "P2")
    case["risk_tags"] = testpoint.get("risk_tags", [])
    case["source"] = "testpoint"
    case["oracle"] = testpoint.get("oracle", "")
    return case
