"""资产记忆模块：加载、更新、持久化测试知识。"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MEMORY: dict[str, Any] = {
    "stable_locators": {},
    "flaky_steps": [],
    "known_product_bugs": [],
    "ambiguous_oracles": [],
    "repaired_cases": [],
}

SEED_MEMORY: dict[str, Any] = {
    "stable_locators": {
        "login_button": "#login-btn",
    },
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

def get_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


def get_default_memory_path() -> Path:
    return get_data_dir() / "asset_memory.json"


def load_memory(path: str | Path | None = None) -> dict[str, Any]:
    memory_path = Path(path) if path else get_default_memory_path()
    if not memory_path.exists():
        return deepcopy(DEFAULT_MEMORY)
    with memory_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    for key, default in DEFAULT_MEMORY.items():
        data.setdefault(key, deepcopy(default))
    return data


def save_memory(memory: dict[str, Any], path: str | Path | None = None) -> None:
    memory_path = Path(path) if path else get_default_memory_path()
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    with memory_path.open("w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def reset_memory(path: str | Path | None = None) -> dict[str, Any]:
    """将 asset_memory.json 恢复为 Demo 初始 seed 状态。"""
    seed = deepcopy(SEED_MEMORY)
    save_memory(seed, path)
    return seed

def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_unique(items: list[dict], new_item: dict, key: str) -> None:
    for item in items:
        if item.get(key) == new_item.get(key):
            item.update(new_item)
            return
    items.append(new_item)


def update_memory(memory: dict[str, Any], analysis_results: list[dict]) -> dict[str, Any]:
    updated = deepcopy(memory)

    for result in analysis_results:
        failure_type = result.get("failure_type")
        case_id = result.get("case_id", "unknown")
        evidence = result.get("evidence", "")
        suggestion = result.get("repair_suggestion", "")

        if failure_type == "locator_issue":
            _append_unique(
                updated["flaky_steps"],
                {
                    "case_id": case_id,
                    "step": result.get("root_cause", "unknown_step"),
                    "locator": evidence,
                    "note": suggestion,
                    "updated_at": _timestamp(),
                },
                "case_id",
            )
            if "建议使用" in suggestion or "#" in evidence:
                locator_key = result.get("target", case_id)
                updated["stable_locators"][locator_key] = "#add-to-cart-btn"

        elif failure_type == "product_bug":
            _append_unique(
                updated["known_product_bugs"],
                {
                    "bug_id": f"BUG-AUTO-{case_id}",
                    "case_id": case_id,
                    "title": result.get("root_cause", "产品缺陷"),
                    "symptoms": evidence,
                    "repair_suggestion": suggestion,
                    "updated_at": _timestamp(),
                },
                "case_id",
            )

        elif failure_type == "oracle_ambiguous":
            _append_unique(
                updated["ambiguous_oracles"],
                {
                    "case_id": case_id,
                    "oracle": evidence,
                    "reason": result.get("root_cause", ""),
                    "refinement": suggestion,
                    "updated_at": _timestamp(),
                },
                "case_id",
            )

        elif failure_type == "case_design_issue":
            _append_unique(
                updated["repaired_cases"],
                {
                    "case_id": case_id,
                    "original_issue": evidence,
                    "repair_suggestion": suggestion,
                    "updated_at": _timestamp(),
                },
                "case_id",
            )

    return updated
