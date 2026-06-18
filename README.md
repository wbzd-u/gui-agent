# GUI Agent Test Loop MVP

一个用于展示 **GUI Agent 测试闭环系统** 的最小可运行 Demo，**对应四道考题的可运行示例**。本 Demo 不控制真实浏览器或手机 App，而是通过 Mock Executor 模拟 Agent 执行，完整呈现从 PRD 到测试点、从自然语言用例到 Agent Case、从调度执行到失败归因与资产记忆沉淀的闭环流程。

---

## 项目背景

GUI Agent（基于视觉/语义理解的自动化测试 Agent）正在改变传统 UI 自动化测试的形态。与传统 Selenium/Playwright 脚本不同，Agent 以「目标驱动 + 逐步决策」方式操作界面，测试体系也需要相应升级：不仅要记录 pass/fail，还要理解 **为什么失败、如何修复、如何避免重复踩坑**。

本 MVP 是一个 **Streamlit 交互式 Demo**，帮助团队快速理解 GUI Agent 测试闭环的核心概念与数据结构。

## 与四道考题的对应关系

| 考题 | Demo 对应模块 |
|------|---------------|
| 考题一：多场景调度引擎 | scheduler.py + Tab 3 调度与 Mock 执行 |
| 考题二：自然语言手工用例转换 | case_converter.py + Tab 2 Agent Case |
| 考题三：BUG 回归端到端方案 | bug_regression.py + 历史 Bug 生成 REG-* case + 优先调度 |
| 考题四：PRD 召回知识库生成测试点 | prd_to_testpoint.py + mock_knowledge.json + Tab 1 测试点生成 |

---

## 目标问题

| 传统测试 | GUI Agent 测试的新挑战 |
|----------|------------------------|
| 脚本逐步骤写死 | Agent 每步需做 StepDecision / ActionDecision |
| pass/fail 二元结果 | 失败可能是产品 Bug、定位器、环境、Oracle 模糊等 |
| 用例写完即固化 | 需要从执行结果反哺 Case 设计与知识库 |
| 回归靠人工维护 | 历史 Bug 应自动生成回归 Case 并优先调度 |

---

## 为什么不能只看 pass/fail

GUI Agent 测试的失败往往 **不是单一原因**：

- **product_bug** — 产品行为不符合 PRD，Agent 正确发现了问题
- **locator_issue** — 定位器 flaky，Agent 本身无错但执行不稳定
- **oracle_ambiguous** — 预期结果定义不清，Agent 无法判定 pass/fail
- **env_issue / data_issue** — 环境或数据问题，不应误报为产品 Bug
- **agent_execution_error** — Agent 决策或策略错误
- **case_design_issue** — 用例设计不合理

若只记录 pass/fail，团队会：
1. 把环境抖动当成产品 Bug
2. 把产品 Bug 当成 Agent 能力问题
3. 重复踩同样的 flaky locator
4. 无法沉淀可复用的测试资产

本 Demo 的 **outcome_analyzer + asset_memory** 正是为了解决上述问题。

---

## Agentic Workflow

```
PRD 文本
   ↓ prd_to_testpoints
测试点（testpoint_id, oracle, priority, risk_tags）
   ↓ case_converter + mock_knowledge + asset_memory
Agent Case（含 StepDecision 的步骤序列）
   ↓ scheduler（priority + risk_tags + 回归 case）
执行计划
   ↓ mock_executor（确定性模拟）
执行结果（pass / fail / unknown + action_decisions）
   ↓ outcome_analyzer（7 类 taxonomy）
失败归因 + repair_suggestion
   ↓ asset_memory（持久化）
stable_locators / flaky_steps / known_product_bugs / ...
   ↓ 反馈
下次 Case 转换时注入 warnings，形成闭环
```

---

## StepDecision / ActionDecision 设计

### StepDecision（Case 设计阶段，每步一个）

在 **自然语言 → Agent Case** 时生成，描述 Agent **计划** 如何执行：

| 字段 | 说明 |
|------|------|
| `intent` | 本步目标（如「用户登录」） |
| `target` | 目标元素 locator |
| `action` | 动作类型（click / fill_and_click / search） |
| `observation_refs` | 预期观察引用（screenshot/dom） |
| `hard_checks` | 必须通过的硬断言 |
| `warnings` | 来自 asset_memory 的历史风险提示 |
| `decision` | execute / wait / skip |

### ActionDecision（执行阶段，每步一个）

在 **Mock Executor 实际执行** 时产出，描述 Agent **实际** 做了什么：

| 字段 | 说明 |
|------|------|
| `action_id` | 动作唯一 ID |
| `intent` | 本步意图 |
| `target` | 实际操作目标 |
| `observation` | 实际观察到的 UI 状态 |
| `decision` | execute / wait / skip / fail / handoff |
| `reason` | 决策原因 |
| `hard_checks` | 本步关联的硬断言 |

**区别**：StepDecision 是「计划」，ActionDecision 是「执行记录」。对比两者可发现计划与实际的偏差，支撑归因与修复。

---

## 失败归因 Taxonomy

| 类型 | 含义 | 典型 next_action |
|------|------|------------------|
| `product_bug` | 产品行为不符合需求 | file_bug |
| `env_issue` | 环境/网络/服务异常 | retry_with_recovery |
| `locator_issue` | 定位器不稳定或失效 | update_locator |
| `data_issue` | 测试数据不满足前置 | fix_test_data |
| `oracle_ambiguous` | 预期结果定义模糊 | refine_oracle |
| `agent_execution_error` | Agent 决策或执行错误 | retry_with_recovery |
| `case_design_issue` | 用例设计不合理 | refine_case |

---

## Case Repair 闭环

1. **执行** — mock_executor 产出 trace 与 action_decisions
2. **归因** — outcome_analyzer 匹配 taxonomy，给出 root_cause 与 repair_suggestion
3. **沉淀** — asset_memory 按 failure_type 写入对应 bucket
4. **反馈** — 下次 case_converter 读取 memory，在 flaky 步骤注入 warnings
5. **回归** — bug_regression 从历史 Bug 生成 REG-* case，scheduler 优先调度

---

## 目录结构

```
gui-agent-mvp/
├── app.py                      # Streamlit 入口（4 Tab）
├── modules/
│   ├── prd_to_testpoint.py     # PRD → 测试点
│   ├── case_converter.py       # 自然语言 → Agent Case
│   ├── bug_regression.py       # 历史 Bug 回归用例
│   ├── scheduler.py            # 执行计划调度
│   ├── mock_executor.py        # Mock 执行器
│   ├── outcome_analyzer.py     # 失败归因
│   └── asset_memory.py         # 资产记忆读写
├── data/
│   ├── asset_memory.json
│   ├── mock_knowledge.json
│   └── mock_bugs.json
├── requirements.txt
└── README.md
```

---

## 如何运行

```bash
cd gui-agent-mvp
pip install -r requirements.txt
python -m streamlit run app.py
```

浏览器将自动打开 `http://localhost:8501`。

如果你的工作目录路径包含空格，也可以使用绝对路径启动：

```bash
cd "c:\Users\www29\Desktop\gui agent\gui-agent-mvp"
python -m streamlit run app.py
```

**环境要求**：Python 3.10+，无需 Selenium/Playwright。

---

## 建议演示路径

### Step 0 — 概览

1. 打开 **概览** Tab，说明项目定位：GUI Agent 测试闭环 Copilot，而非普通用例生成器
2. 指出顶部 KPI 与闭环流程图，建立整体认知

### Step 1 — PRD 解析

1. 展示默认 PRD（登录 / 搜索 / 购物车 / 下单 / 支付）
2. 点击 **「生成测试点」**，展示功能模块摘要卡片
3. 说明 `oracle`、`priority`、`risk_tags` 如何支撑后续调度

### Step 2 — Agent Case

1. 使用默认用例：「用户登录后搜索商品并加入购物车」
2. 点击 **「转换为 Agent Case」**，展开 StepDecision：intent、target、warnings、decision
3. 说明 asset_memory 中的 flaky_steps 如何影响 warnings

### Step 3 — 执行轨迹

1. 点击 **「Mock 执行」**（会自动生成执行计划）
2. 展示 pass / fail / unknown 三种结果及 ActionDecision 轨迹
3. 对比 StepDecision（计划）与 ActionDecision（执行）的差异

### Step 4 — 失败归因与资产记忆

1. 点击 **「分析执行结果」**，展示 failure taxonomy、root cause、repair suggestion
2. 点击 **「写入资产记忆」**，说明 KPI「资产记忆条目」变化
3. 回到 **Agent Case** Tab 重新转换用例，展示 warnings 变化 — **闭环完成**

---

## 说明

- 本 Demo 使用 **规则/模板** 模拟 LLM 与 Agent，结果 **确定性可复现**（seed=42）
- 所有 JSON 读写使用 UTF-8 编码
- 完整版系统设计请参考项目文档（PDF/DOCX）
