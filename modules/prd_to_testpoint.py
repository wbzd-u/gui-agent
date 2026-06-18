"""PRD 转测试点模块：基于规则/模板生成测试点。"""

from __future__ import annotations

FEATURE_TEMPLATES: list[dict] = [
    {
        "keywords": ["登录", "login", "账号", "密码"],
        "feature": "login",
        "templates": [
            {
                "suffix": "001",
                "user_goal": "用户使用正确账号密码成功登录",
                "precondition": "用户已注册且账号状态正常",
                "oracle": "登录成功后跳转首页并展示用户昵称",
                "priority": "P0",
                "risk_tags": ["auth", "core_flow"],
            },
            {
                "suffix": "002",
                "user_goal": "用户使用错误密码登录失败并看到明确提示",
                "precondition": "用户已注册",
                "oracle": "页面展示密码错误提示，不跳转首页",
                "priority": "P1",
                "risk_tags": ["auth", "error_handling"],
            },
        ],
    },
    {
        "keywords": ["搜索", "search", "商品", "关键词"],
        "feature": "search",
        "templates": [
            {
                "suffix": "001",
                "user_goal": "用户搜索有效关键词并看到匹配商品列表",
                "precondition": "用户已登录，商品库有匹配数据",
                "oracle": "搜索结果列表非空，且每项包含商品名与价格",
                "priority": "P0",
                "risk_tags": ["search", "core_flow"],
            },
            {
                "suffix": "002",
                "user_goal": "用户搜索无结果关键词时看到空态提示",
                "precondition": "用户已登录",
                "oracle": "页面展示「暂无相关商品」或等价空态文案",
                "priority": "P1",
                "risk_tags": ["search", "empty_state"],
            },
        ],
    },
    {
        "keywords": ["购物车", "cart", "加购", "加入"],
        "feature": "cart",
        "templates": [
            {
                "suffix": "001",
                "user_goal": "用户将商品加入购物车并看到数量更新",
                "precondition": "用户已登录，商品有库存",
                "oracle": "购物车角标数量 +1，购物车页展示该商品",
                "priority": "P0",
                "risk_tags": ["cart", "core_flow"],
            },
        ],
    },
    {
        "keywords": ["下单", "订单", "checkout", "结算"],
        "feature": "checkout",
        "templates": [
            {
                "suffix": "001",
                "user_goal": "用户从购物车进入结算并完成下单",
                "precondition": "购物车有商品，用户已登录",
                "oracle": "生成待支付订单，展示订单号与应付金额",
                "priority": "P0",
                "risk_tags": ["checkout", "order"],
            },
        ],
    },
    {
        "keywords": ["支付", "payment", "付款", "pay"],
        "feature": "payment",
        "templates": [
            {
                "suffix": "001",
                "user_goal": "用户使用有效支付方式完成支付",
                "precondition": "存在待支付订单，支付渠道可用",
                "oracle": "支付成功页展示单一明确的成功状态与订单号",
                "priority": "P0",
                "risk_tags": ["payment", "checkout", "critical"],
            },
            {
                "suffix": "002",
                "user_goal": "支付失败时用户看到明确失败原因",
                "precondition": "存在待支付订单",
                "oracle": "仅展示失败状态及原因，不出现成功/失败矛盾文案",
                "priority": "P1",
                "risk_tags": ["payment", "error_handling"],
            },
        ],
    },
]


def _feature_matched(prd_text: str, keywords: list[str]) -> bool:
    prd_lower = prd_text.lower()
    return any(kw.lower() in prd_lower for kw in keywords)


def prd_to_testpoints(prd_text: str) -> list[dict]:
    """从 PRD 文本生成 5-8 个测试点。"""
    testpoints: list[dict] = []

    for feature_def in FEATURE_TEMPLATES:
        if not _feature_matched(prd_text, feature_def["keywords"]):
            continue
        for tpl in feature_def["templates"]:
            feature = feature_def["feature"]
            testpoints.append(
                {
                    "testpoint_id": f"TP-{feature.upper()}-{tpl['suffix']}",
                    "feature": feature,
                    "user_goal": tpl["user_goal"],
                    "precondition": tpl["precondition"],
                    "oracle": tpl["oracle"],
                    "priority": tpl["priority"],
                    "risk_tags": tpl["risk_tags"],
                }
            )

    if not testpoints:
        testpoints = prd_to_testpoints(
            "用户登录后搜索商品，加入购物车，下单并完成支付。"
        )

    return testpoints[:8]
