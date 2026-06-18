"""历史 Bug 回归用例生成模块。"""

from __future__ import annotations

import json
from pathlib import Path


def get_bugs_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "mock_bugs.json"


def load_bugs(path: str | Path | None = None) -> list[dict]:
    bugs_path = Path(path) if path else get_bugs_path()
    with bugs_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def generate_regression_cases(bugs: list[dict] | None = None) -> list[dict]:
    """根据历史 bug 生成回归用例。"""
    bugs = bugs if bugs is not None else load_bugs()
    cases: list[dict] = []

    for bug in bugs:
        cases.append(
            {
                "case_id": f"REG-{bug['bug_id']}",
                "bug_id": bug["bug_id"],
                "title": bug["title"],
                "regression_case": (
                    f"回归验证：{bug['title']}。"
                    f"步骤提示：{bug.get('regression_hint', '')}"
                ),
                "expected_oracle": bug.get("symptoms", "") + " → 应已修复，符合预期行为",
                "risk_level": bug.get("risk_level", "medium"),
                "feature": bug.get("feature", "unknown"),
                "source": "regression",
                "priority": "P0" if bug.get("risk_level") == "critical" else "P1",
                "risk_tags": ["regression", bug.get("feature", "unknown")],
                "goal": bug.get("regression_hint", bug["title"]),
            }
        )

    return cases
