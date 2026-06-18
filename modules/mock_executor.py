"""Mock 执行器：确定性模拟 GUI Agent 执行，不依赖真实浏览器。"""

from __future__ import annotations

# 固定场景映射：按 case_id 模式决定执行结果（可复现）
SCENARIO_RULES: list[dict] = [
    {
        "match": ["LOGIN", "SEARCH-001", "CASE-SEARCH-001", "CASE-001", "CASE-LOGIN"],
        "status": "pass",
        "scenario": "login_search_pass",
    },
    {
        "match": ["BUG-001", "SEARCH-002", "EMPTY", "REG-BUG-001"],
        "status": "fail",
        "scenario": "search_empty_no_hint",
        "failure_hint": "product_bug",
    },
    {
        "match": ["CART", "BUG-002", "REG-BUG-002", "ADD"],
        "status": "fail",
        "scenario": "add_to_cart_not_clickable",
        "failure_hint": "locator_issue",
    },
    {
        "match": ["PAYMENT", "BUG-003", "REG-BUG-003", "PAY"],
        "status": "unknown",
        "scenario": "payment_ambiguous",
        "failure_hint": "oracle_ambiguous",
    },
]


def _resolve_scenario(case_id: str, index: int) -> dict:
    upper_id = case_id.upper()
    for rule in SCENARIO_RULES:
        if any(token in upper_id for token in rule["match"]):
            return rule

    fallback = [
        {"status": "pass", "scenario": "generic_pass", "failure_hint": None},
        {"status": "fail", "scenario": "search_empty_no_hint", "failure_hint": "product_bug"},
        {"status": "fail", "scenario": "add_to_cart_not_clickable", "failure_hint": "locator_issue"},
        {"status": "unknown", "scenario": "payment_ambiguous", "failure_hint": "oracle_ambiguous"},
        {"status": "pass", "scenario": "generic_pass", "failure_hint": None},
    ]
    return fallback[index % len(fallback)]


def _build_pass_trace(case: dict) -> tuple[list[str], list[dict], list[str]]:
    goal = case.get("goal", "执行用例")
    steps = case.get("steps", [])
    trace: list[str] = []
    actions: list[dict] = []
    refs: list[str] = []

    if steps:
        for i, step in enumerate(steps, start=1):
            sd = step.get("step_decision", {})
            intent = sd.get("intent", step.get("description", f"步骤{i}"))
            target = sd.get("target", "unknown")
            trace.append(f"Step {i}: {intent} → 成功")
            actions.append(
                {
                    "action_id": f"ACT-{case.get('case_id', 'X')}-{i}",
                    "intent": intent,
                    "target": target,
                    "observation": f"元素 {target} 可见且可操作",
                    "decision": "execute",
                    "reason": "前置条件满足，hard_checks 通过",
                    "hard_checks": sd.get("hard_checks", []),
                }
            )
            refs.extend(sd.get("observation_refs", [f"screenshot://step_{i}"]))
    else:
        trace = [
            f"Step 1: 初始化 → 成功",
            f"Step 2: {goal} → 成功",
            f"Step 3: 断言 oracle → 通过",
        ]
        actions = [
            {
                "action_id": f"ACT-{case.get('case_id', 'X')}-1",
                "intent": "初始化环境",
                "target": "app://home",
                "observation": "页面加载完成",
                "decision": "execute",
                "reason": "环境就绪",
                "hard_checks": ["页面可访问"],
            },
            {
                "action_id": f"ACT-{case.get('case_id', 'X')}-2",
                "intent": goal,
                "target": "dynamic",
                "observation": "操作成功",
                "decision": "execute",
                "reason": "步骤执行无异常",
                "hard_checks": ["业务断言通过"],
            },
        ]
        refs = ["screenshot://final_state"]

    return trace, actions, refs


def _build_product_bug_trace(case: dict) -> tuple[list[str], list[dict], list[str]]:
    case_id = case.get("case_id", "CASE-X")
    trace = [
        "Step 1: 用户登录 → 成功",
        "Step 2: 搜索不存在商品 → 执行完成",
        "Step 3: 断言空态提示 → 失败",
    ]
    actions = [
        {
            "action_id": f"ACT-{case_id}-1",
            "intent": "用户登录",
            "target": "#login-btn",
            "observation": "登录成功，跳转首页",
            "decision": "execute",
            "reason": "登录流程正常",
            "hard_checks": ["展示用户昵称"],
        },
        {
            "action_id": f"ACT-{case_id}-2",
            "intent": "搜索商品",
            "target": "#search-btn",
            "observation": "搜索执行完成，结果区域为空",
            "decision": "execute",
            "reason": "搜索请求成功",
            "hard_checks": ["搜索结果区域渲染"],
        },
        {
            "action_id": f"ACT-{case_id}-3",
            "intent": "验证空态提示",
            "target": ".empty-state",
            "observation": "element not found: 空态文案未展示，页面空白",
            "decision": "fail",
            "reason": "产品 Bug：搜索无结果时未展示空态提示",
            "hard_checks": ["应展示「暂无相关商品」"],
        },
    ]
    refs = [
        "screenshot://search_empty_blank",
        "dom://.search-results-empty",
    ]
    return trace, actions, refs


def _build_locator_issue_trace(case: dict) -> tuple[list[str], list[dict], list[str]]:
    case_id = case.get("case_id", "CASE-X")
    trace = [
        "Step 1: 用户登录 → 成功",
        "Step 2: 搜索商品 → 成功",
        "Step 3: 点击加入购物车 → 失败",
    ]
    actions = [
        {
            "action_id": f"ACT-{case_id}-1",
            "intent": "用户登录",
            "target": "#login-btn",
            "observation": "登录成功",
            "decision": "execute",
            "reason": "登录正常",
            "hard_checks": [],
        },
        {
            "action_id": f"ACT-{case_id}-2",
            "intent": "搜索商品",
            "target": "#search-input",
            "observation": "找到商品「测试商品A」",
            "decision": "execute",
            "reason": "搜索成功",
            "hard_checks": [],
        },
        {
            "action_id": f"ACT-{case_id}-3",
            "intent": "加入购物车",
            "target": "//button[contains(text(),'加入购物车')]",
            "observation": "element not clickable: 按钮 visible 但 click 无响应",
            "decision": "fail",
            "reason": "Locator 不稳定，疑似 flaky 或定位器失效",
            "hard_checks": ["加购按钮可点击", "购物车角标 +1"],
        },
    ]
    refs = [
        "screenshot://add_to_cart_disabled",
        "dom://button[text='加入购物车']",
    ]
    return trace, actions, refs


def _build_oracle_ambiguous_trace(case: dict) -> tuple[list[str], list[dict], list[str]]:
    case_id = case.get("case_id", "CASE-X")
    trace = [
        "Step 1: 进入支付页 → 成功",
        "Step 2: 提交支付 → 完成",
        "Step 3: 验证支付结果 → unknown",
    ]
    actions = [
        {
            "action_id": f"ACT-{case_id}-1",
            "intent": "进入支付页",
            "target": "#pay-btn",
            "observation": "支付页加载完成",
            "decision": "execute",
            "reason": "页面就绪",
            "hard_checks": [],
        },
        {
            "action_id": f"ACT-{case_id}-2",
            "intent": "提交支付",
            "target": "#pay-btn",
            "observation": "支付请求已发送",
            "decision": "execute",
            "reason": "支付 API 返回",
            "hard_checks": [],
        },
        {
            "action_id": f"ACT-{case_id}-3",
            "intent": "验证支付结果",
            "target": "#payment-result",
            "observation": "同时出现「支付成功」与「支付失败，请重试」矛盾文案",
            "decision": "handoff",
            "reason": "Oracle ambiguous：无法判定最终支付状态",
            "hard_checks": ["支付结果状态唯一且明确"],
        },
    ]
    refs = [
        "screenshot://payment_conflict",
        "dom://#payment-result",
    ]
    return trace, actions, refs


SCENARIO_BUILDERS = {
    "login_search_pass": _build_pass_trace,
    "generic_pass": _build_pass_trace,
    "search_empty_no_hint": _build_product_bug_trace,
    "add_to_cart_not_clickable": _build_locator_issue_trace,
    "payment_ambiguous": _build_oracle_ambiguous_trace,
}


def mock_execute_case(case: dict, index: int = 0, seed: int = 42) -> dict:
    """模拟执行单条 case（seed 保留接口，结果由规则决定）。"""
    _ = seed  # 固定规则，不使用随机
    case_id = case.get("case_id", f"CASE-{index + 1}")
    scenario = _resolve_scenario(case_id, index)
    builder = SCENARIO_BUILDERS.get(scenario["scenario"], _build_pass_trace)
    trace, actions, refs = builder(case)

    return {
        "case_id": case_id,
        "status": scenario["status"],
        "failure_hint": scenario.get("failure_hint"),
        "execution_trace": trace,
        "screenshots_or_observation_refs": refs,
        "action_decisions": actions,
        "scenario": scenario["scenario"],
    }


def mock_execute_cases(cases: list[dict], seed: int = 42) -> list[dict]:
    """模拟执行多条 case，至少包含 pass / product_bug / locator_issue / oracle_ambiguous。"""
    if not cases:
        cases = _default_demo_cases()

    # 限制 3-5 条，并确保覆盖四种状态
    selected = _ensure_coverage(cases)
    results = []
    for i, case in enumerate(selected):
        results.append(mock_execute_case(case, index=i, seed=seed))
    return results


def _default_demo_cases() -> list[dict]:
    return [
        {"case_id": "CASE-LOGIN-001", "goal": "用户登录并搜索商品", "priority": "P0"},
        {"case_id": "REG-BUG-001", "goal": "搜索空结果空态提示", "priority": "P1", "source": "regression"},
        {"case_id": "REG-BUG-002", "goal": "加购按钮可点击", "priority": "P1", "source": "regression"},
        {"case_id": "REG-BUG-003", "goal": "支付失败提示明确", "priority": "P0", "source": "regression"},
    ]


def _ensure_coverage(cases: list[dict]) -> list[dict]:
    """从输入 cases 中选取 3-5 条，保证 pass/fail/unknown 均出现。"""
    required_templates = [
        {"case_id": "CASE-LOGIN-001", "goal": "用户登录并搜索商品", "priority": "P0"},
        {"case_id": "REG-BUG-001", "goal": "搜索空结果空态提示", "source": "regression"},
        {"case_id": "REG-BUG-002", "goal": "加购按钮可点击", "source": "regression"},
        {"case_id": "REG-BUG-003", "goal": "支付失败提示明确", "source": "regression"},
    ]

    selected: list[dict] = []
    seen_ids: set[str] = set()

    def _add(case: dict) -> None:
        cid = case.get("case_id", "")
        if cid and cid not in seen_ids and len(selected) < 5:
            seen_ids.add(cid)
            selected.append(case)

    for template in required_templates:
        matched = next((c for c in cases if c.get("case_id") == template["case_id"]), template)
        _add({**template, **matched})

    for case in cases:
        _add(case)

    return selected[:5] if len(selected) >= 3 else selected + _default_demo_cases()[: max(0, 3 - len(selected))]
