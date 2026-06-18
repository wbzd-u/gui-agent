"""GUI Agent 测试闭环 Copilot — Streamlit Demo 入口。"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from modules.asset_memory import get_default_memory_path, load_memory, save_memory, update_memory
from modules.bug_regression import generate_regression_cases, load_bugs
from modules.case_converter import convert_to_agent_case, testpoint_to_agent_case
from modules.mock_executor import mock_execute_cases
from modules.outcome_analyzer import analyze_outcomes
from modules.prd_to_testpoint import prd_to_testpoints
from modules.scheduler import schedule_cases

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

DEFAULT_PRD = """# 电商 App 产品需求（Demo）

## 1. 登录
用户可使用邮箱+密码登录。登录成功后进入首页并展示用户昵称。
错误密码需展示明确错误提示。

## 2. 搜索
用户可在搜索框输入关键词搜索商品。
- 有结果时展示商品列表（含名称、价格）
- 无结果时需展示「暂无相关商品」空态提示

## 3. 购物车
用户可将商品加入购物车，购物车角标实时更新。

## 4. 下单
用户可从购物车进入结算页，确认信息后生成待支付订单。

## 5. 支付
用户选择支付方式完成付款。
支付成功或失败均需展示唯一、明确的状态文案。
"""

DEFAULT_NATURAL_CASE = "用户登录后搜索商品并加入购物车"

DEMO_SEED_MEMORY = {
    "stable_locators": {"login_button": "#login-btn"},
    "flaky_steps": [
        {
            "step": "add_to_cart",
            "locator": "//button[contains(text(),'加入购物车')]",
            "note": "历史偶现不可点击，建议使用 #add-to-cart-btn",
        }
    ],
    "known_product_bugs": [],
    "ambiguous_oracles": [],
    "repaired_cases": [],
}

FEATURE_LABELS = {
    "login": "登录",
    "search": "搜索",
    "cart": "购物车",
    "checkout": "下单",
    "payment": "支付",
}

FEATURE_SUMMARY = {
    "login": "验证正确账号登录、错误密码提示",
    "search": "验证有结果、无结果空态提示",
    "cart": "验证加入购物车和数量更新",
    "checkout": "验证结算下单与订单生成",
    "payment": "验证支付成功/失败提示明确",
}


def _load_json(name: str) -> dict | list:
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _init_session_state() -> None:
    defaults = {
        "testpoints": [],
        "agent_case": None,
        "agent_cases_for_schedule": [],
        "regression_cases": [],
        "execution_plan": [],
        "execution_results": [],
        "analysis_results": [],
        "memory": load_memory(),
        "memory_saved_once": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _reset_demo() -> None:
    """清空演示进度，并将 asset_memory.json 恢复为初始状态。"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    save_memory(dict(DEMO_SEED_MEMORY))
    _init_session_state()
    st.rerun()


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Demo 设置")
        if st.button("恢复默认", type="secondary", use_container_width=True, key="btn_reset_demo"):
            _reset_demo()
        st.caption(
            "清空测试点、Agent Case、执行结果与分析记录，"
            "并将 asset_memory.json 恢复为初始 seed。"
        )

def _status_badge(status: str) -> str:
    mapping = {"pass": "✅ pass", "fail": "❌ fail", "unknown": "❓ unknown"}
    return mapping.get(status, status)


def _count_memory_items(memory: dict) -> int:
    return (
        len(memory.get("stable_locators", {}))
        + len(memory.get("flaky_steps", []))
        + len(memory.get("known_product_bugs", []))
        + len(memory.get("ambiguous_oracles", []))
        + len(memory.get("repaired_cases", []))
    )


def _get_kpis() -> dict[str, int]:
    memory = st.session_state.get("memory") or load_memory()
    agent_case_count = len(st.session_state.agent_cases_for_schedule)
    if agent_case_count == 0 and st.session_state.agent_case:
        agent_case_count = 1

    exec_results = st.session_state.execution_results
    fail_unknown = sum(1 for r in exec_results if r.get("status") in ("fail", "unknown"))

    return {
        "testpoints": len(st.session_state.testpoints),
        "agent_cases": agent_case_count,
        "executed": len(exec_results),
        "fail_unknown": fail_unknown,
        "memory_items": _count_memory_items(memory),
    }


def _render_kpi_row() -> None:
    kpis = _get_kpis()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("测试点", kpis["testpoints"])
    c2.metric("Agent Case", kpis["agent_cases"])
    c3.metric("执行用例", kpis["executed"])
    c4.metric("失败 / 未知", kpis["fail_unknown"])
    c5.metric("资产记忆条目", kpis["memory_items"])


def _render_feature_cards(testpoints: list[dict]) -> None:
    by_feature: dict[str, list[str]] = {}
    for tp in testpoints:
        feature = tp.get("feature", "other")
        by_feature.setdefault(feature, []).append(tp.get("user_goal", ""))

    features = list(by_feature.items())
    cols = st.columns(len(features))
    for col, (feature, goals) in zip(cols, features):
        label = FEATURE_LABELS.get(feature, feature)
        summary = FEATURE_SUMMARY.get(feature, "")
        with col:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.markdown(summary)
                st.caption(f"{len(goals)} 个测试点")


def tab_overview() -> None:
    st.subheader("项目概览")
    st.markdown(
        "**一句话：** 这是一个面向 GUI Agent 的测试闭环 Copilot —— "
        "不只生成测试用例，而是把 **需求理解 → 任务编排 → 执行观测 → 失败归因 → 资产沉淀 → 用例修复** 串成可迭代的测试系统。"
    )

    st.markdown("#### 解决什么问题？")
    st.markdown(
        "GUI Agent 以「目标驱动 + 逐步决策」方式操作界面，传统测试只看 pass/fail 远远不够："
        "失败可能来自产品缺陷、定位器不稳定、Oracle 模糊、环境异常等。"
        "**本 Demo 展示如何把失败结构化归因，并沉淀为测试资产，反哺下一轮测试。**"
    )

    st.markdown("#### 闭环流程")
    st.markdown(
        """
```
① PRD 解析          ② Agent Case         ③ 执行轨迹
   提取测试点    →      结构化任务     →      Mock 执行 + 决策记录
                                                    ↓
⑥ Case Repair   ←   ⑤ 资产记忆    ←   ④ 失败归因
   优化下一轮用例       持久化知识         7 类 taxonomy
```
        """
    )

    st.markdown("#### 三个创新点")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.success(
            "**需求到任务的可执行转换**\n\n"
            "PRD → 测试点 → Agent Case，每步含 intent / target / hard_checks，"
            "Agent 拿到的是可执行任务而非自然语言描述。"
        )
    with c2:
        st.success(
            "**Agent 决策过程显式化**\n\n"
            "StepDecision（计划）与 ActionDecision（执行）分离，"
            "可对比「计划 vs 实际」，支撑调试与归因。"
        )
    with c3:
        st.success(
            "**失败驱动的测试资产迭代**\n\n"
            "7 类 failure taxonomy → repair suggestion → asset_memory，"
            "失败不是终点，而是下一轮测试优化的输入。"
        )

    st.markdown("#### 与普通测试工具的区别")
    st.markdown(
        """
| 维度 | 普通测试工具 | 本 Demo |
|------|-------------|---------|
| 输入 | 人工编写用例 | PRD + 自然语言 → 结构化 Agent Case |
| 执行 | 脚本逐步执行 | Agent 逐步决策（StepDecision / ActionDecision） |
| 结果 | pass / fail | pass / fail / unknown + 根因 + 修复建议 |
| 失败后 | 人工排查 | 自动归因 → 写入资产记忆 → 反哺下一轮 |
        """
    )

    st.markdown("#### 建议演示路径")
    demo_steps = [
        ("PRD 解析", "点击「生成测试点」→ 展示功能模块卡片与 priority / oracle"),
        ("Agent Case", "转换自然语言用例 → 展开 StepDecision，讲解 intent / target / warnings"),
        ("执行轨迹", "生成计划 → Mock 执行 → 展示 pass / fail / unknown 与 ActionDecision 轨迹"),
        ("失败归因与资产记忆", "分析结果 → 写入 memory → 回到 Agent Case 看 warnings 变化，完成闭环"),
    ]
    for idx, (tab_name, desc) in enumerate(demo_steps, start=1):
        st.markdown(f"**Step {idx} · {tab_name}** — {desc}")

    st.caption(
        "Demo 说明：本原型采用规则引擎模拟 LLM 与 Agent 执行（Mock Executor），"
        "重点展示闭环架构与数据结构；完整版可接入真实 LLM 与浏览器 / App 执行器。"
    )


def tab_prd_to_testpoint() -> None:
    st.subheader("PRD 解析")
    st.caption("从 PRD 提取测试点，作为闭环第一步。")

    col_input, col_hint = st.columns([1, 1])
    with col_input:
        with st.expander("编辑 PRD 文本", expanded=False):
            prd_text = st.text_area("PRD 文本", value=DEFAULT_PRD, height=160, label_visibility="collapsed")
        if st.button("生成测试点", type="primary", key="btn_gen_testpoints"):
            testpoints = prd_to_testpoints(prd_text)
            st.session_state.testpoints = testpoints
            st.success(f"已生成 {len(testpoints)} 个测试点")

    with col_hint:
        st.markdown("**本步骤产出**")
        st.markdown("- 结构化测试点（oracle / priority / risk_tags）")
        st.markdown("- 按功能模块分组的可读摘要")
        st.markdown("- 供后续 Agent Case 与调度使用")

    if st.session_state.testpoints:
        st.markdown("#### 功能模块摘要")
        _render_feature_cards(st.session_state.testpoints)

        with st.expander("完整测试点表格", expanded=False):
            st.dataframe(st.session_state.testpoints, use_container_width=True)

        with st.expander("JSON 详情", expanded=False):
            st.json(st.session_state.testpoints)


def tab_case_converter() -> None:
    st.subheader("Agent Case")
    st.caption("将自然语言用例转换为含 StepDecision 的结构化 Agent Case。")

    natural_case = st.text_input("自然语言用例", value=DEFAULT_NATURAL_CASE)
    knowledge = _load_json("mock_knowledge.json")
    memory = load_memory()

    col1, col2 = st.columns(2)
    with col1:
        with st.expander("Mock 知识库摘要", expanded=False):
            st.json(
                {
                    "pages": list(knowledge.get("pages", {}).keys()),
                    "locator_count": len(knowledge.get("locators", {})),
                    "test_accounts": list(knowledge.get("test_accounts", {}).keys()),
                }
            )
    with col2:
        with st.expander("资产记忆（影响 warnings）", expanded=False):
            st.json(
                {
                    "flaky_steps": len(memory.get("flaky_steps", [])),
                    "known_product_bugs": len(memory.get("known_product_bugs", [])),
                    "ambiguous_oracles": len(memory.get("ambiguous_oracles", [])),
                }
            )

    if st.button("转换为 Agent Case", type="primary", key="btn_convert_case"):
        agent_case = convert_to_agent_case(natural_case, knowledge, memory)
        st.session_state.agent_case = agent_case
        st.session_state.agent_cases_for_schedule = [agent_case]
        st.success("Agent Case 已生成")

    if st.session_state.agent_case:
        case = st.session_state.agent_case
        st.markdown("#### Agent Case 概览")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**case_id:** `{case['case_id']}`")
            st.markdown(f"**goal:** {case['goal']}")
            st.markdown(f"**recovery_strategy:** {case['recovery_strategy']}")
        with c2:
            st.markdown(f"**expected_result:** {case['expected_result']}")
            st.markdown(f"**hard_checks:** {', '.join(case['hard_checks'])}")

        st.markdown("#### StepDecision 步骤卡片")
        for step in case.get("steps", []):
            sd = step.get("step_decision", {})
            with st.expander(f"Step {step['step_no']}: {step['description']} — `{sd.get('decision')}`"):
                st.markdown(f"**intent:** {sd.get('intent')}")
                st.markdown(f"**target:** `{sd.get('target')}`")
                st.markdown(f"**action:** {sd.get('action')}")
                st.markdown(f"**observation_refs:** {sd.get('observation_refs')}")
                st.markdown(f"**hard_checks:** {sd.get('hard_checks')}")
                if sd.get("warnings"):
                    st.warning(f"warnings: {sd.get('warnings')}")


def _build_execution_plan() -> list[dict]:
    """生成调度计划（Mock 执行前自动调用）。"""
    knowledge = _load_json("mock_knowledge.json")
    memory = load_memory()
    regression = generate_regression_cases(load_bugs())
    st.session_state.regression_cases = regression

    agent_cases: list[dict] = []
    if st.session_state.agent_case:
        agent_cases.append(st.session_state.agent_case)

    for tp in st.session_state.testpoints[:2]:
        agent_cases.append(testpoint_to_agent_case(tp, knowledge, memory))

    agent_cases.extend(regression)
    st.session_state.agent_cases_for_schedule = agent_cases

    plan = schedule_cases(
        testpoints=st.session_state.testpoints,
        agent_cases=agent_cases,
        regression_cases=regression,
    )
    st.session_state.execution_plan = plan
    return plan


def tab_scheduler_executor() -> None:
    st.subheader("执行轨迹")
    st.caption("调度执行顺序 → Mock Executor → ActionDecision 轨迹。")

    if st.button("生成执行计划", key="btn_gen_plan"):
        plan = _build_execution_plan()
        st.success(f"执行计划已生成，共 {len(plan)} 条 case")

    if st.session_state.execution_plan:
        st.markdown("#### 调度执行顺序")
        plan_display = [
            {
                "order": p["order"],
                "case_id": p["case_id"],
                "priority": p["priority"],
                "reason": p["reason"],
            }
            for p in st.session_state.execution_plan
        ]
        st.dataframe(plan_display, use_container_width=True)

    if st.button("Mock 执行（3-5 条）", type="primary", key="btn_mock_exec"):
        if not st.session_state.execution_plan:
            _build_execution_plan()
        cases = [p["case"] for p in st.session_state.execution_plan]
        st.session_state.execution_results = mock_execute_cases(cases, seed=42)
        st.session_state.analysis_results = []
        st.session_state.memory_saved_once = False
        st.rerun()

    if st.session_state.execution_results:
        st.markdown("#### 执行结果与 ActionDecision")
        for result in st.session_state.execution_results:
            with st.expander(
                f"{_status_badge(result['status'])} — {result['case_id']} ({result.get('scenario', '')})"
            ):
                st.markdown("**execution_trace**")
                for line in result.get("execution_trace", []):
                    st.text(line)

                st.markdown("**screenshots_or_observation_refs**")
                st.code("\n".join(result.get("screenshots_or_observation_refs", [])))

                st.markdown("**action_decisions**")
                st.dataframe(result.get("action_decisions", []), use_container_width=True)


def tab_analyze_memory() -> None:
    st.subheader("失败归因与资产记忆")
    st.caption("失败不是结束，而是进入资产记忆，反过来修复下一轮测试。")

    st.markdown(
        """
```
执行失败  →  failure taxonomy  →  root cause  →  repair suggestion
                                              ↓
                              写入 asset_memory（stable_locators / flaky_steps / ...）
                                              ↓
                              下一轮 Agent Case 自动注入 warnings / 优先 stable locator
```
        """
    )

    if not st.session_state.execution_results:
        st.info("请先在「执行轨迹」Tab 完成 Mock 执行。")
        return

    col_analyze, col_save = st.columns(2)
    with col_analyze:
        if st.button("分析执行结果", type="primary", key="btn_analyze", use_container_width=True):
            st.session_state.analysis_results = analyze_outcomes(st.session_state.execution_results)
            st.rerun()

    can_save = bool(st.session_state.analysis_results)
    with col_save:
        if st.button(
            "写入资产记忆",
            key="btn_save_memory",
            use_container_width=True,
            disabled=not can_save,
            type="primary" if can_save else "secondary",
        ):
            before = _count_memory_items(load_memory())
            memory = load_memory()
            updated = update_memory(memory, st.session_state.analysis_results)
            save_memory(updated)
            st.session_state.memory = updated
            st.session_state.memory_saved_once = True
            st.session_state.memory_count_before = before
            st.session_state.memory_count_after = _count_memory_items(updated)
            st.rerun()

    if not st.session_state.analysis_results:
        return

    if st.session_state.memory_saved_once and st.session_state.get("memory_count_after") is not None:
        before = st.session_state.get("memory_count_before", 0)
        after = st.session_state.get("memory_count_after", 0)
        st.success(
            f"资产记忆已更新：条目数 **{before} → {after}**。"
            "请查看顶部 KPI「资产记忆条目」。"
        )

    st.markdown("#### 失败归因卡片")
    for item in st.session_state.analysis_results:
        if not item.get("failure_type"):
            continue
        with st.container(border=True):
            st.markdown(f"**{item['case_id']}** · `{item['failure_type']}`")
            st.markdown(f"**根因：** {item.get('root_cause')}")
            st.markdown(f"**证据：** {item.get('evidence')}")
            st.markdown(f"**修复建议：** {item.get('repair_suggestion')}")
            st.markdown(f"**next_action：** `{item.get('next_action')}`")

            if item["failure_type"] == "locator_issue":
                st.success(
                    "写入资产：`flaky_steps` + `stable_locators`  \n"
                    "下一轮影响：Agent Case 对应步骤 decision → `wait`，优先使用稳定 locator"
                )
            elif item["failure_type"] == "product_bug":
                st.success(
                    "写入资产：`known_product_bugs`  \n"
                    "下一轮影响：回归 case 优先调度，hard_checks 加强业务断言"
                )
            elif item["failure_type"] == "oracle_ambiguous":
                st.success(
                    "写入资产：`ambiguous_oracles`  \n"
                    "下一轮影响：推动 oracle 澄清，减少 unknown 结果"
                )

    with st.expander("完整归因表格", expanded=False):
        st.dataframe(st.session_state.analysis_results, use_container_width=True)

    st.markdown("#### 当前 asset_memory.json")
    with st.expander("查看 asset_memory.json", expanded=False):
        st.json(st.session_state.get("memory") or load_memory())

    if st.session_state.memory_saved_once:
        st.markdown("#### Case Repair 闭环已完成")
        st.markdown(
            "回到 **Agent Case** Tab 重新转换用例，可看到 flaky 步骤的 `warnings` 与 `decision: wait` 变化。"
        )


def main() -> None:
    st.set_page_config(
        page_title="GUI Agent 测试闭环 Copilot",
        layout="wide",
    )
    _init_session_state()
    _render_sidebar()

    st.title("GUI Agent 测试闭环 Copilot")
    st.markdown(
        "面向 GUI Agent 的自动化测试闭环 Demo —— "
        "从 PRD 到 Agent Case，再到执行轨迹、失败归因与资产记忆的完整链路。"
    )

    _render_kpi_row()
    st.divider()

    tab0, tab1, tab2, tab3, tab4 = st.tabs(
        [
            "概览",
            "PRD 解析",
            "Agent Case",
            "执行轨迹",
            "失败归因与资产记忆",
        ]
    )

    with tab0:
        tab_overview()
    with tab1:
        tab_prd_to_testpoint()
    with tab2:
        tab_case_converter()
    with tab3:
        tab_scheduler_executor()
    with tab4:
        tab_analyze_memory()


if __name__ == "__main__":
    main()
