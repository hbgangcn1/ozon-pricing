"""
安全问题预设清单和校验工具。

新规则（Wave 10 Commit 5 起）：
- 用户只设置/校验 1 个安全问题（之前是 2 个）
- 数据库 q2/a2 列保留为 nullable 以兼容老数据，但代码不再读写
"""
from typing import List, Optional, Tuple


SECURITY_QUESTIONS: List[str] = [
    "您母亲的姓名是？",
    "您父亲的姓名是？",
    "您出生的城市是？",
    "您小学班主任的姓名是？",
    "您最喜欢的宠物名字是？",
]


def get_security_questions() -> List[str]:
    """返回预设安全问题清单的副本。"""
    return list(SECURITY_QUESTIONS)


def validate_security_questions(q: str) -> Tuple[bool, Optional[str]]:
    """校验用户选择的安全问题是否合法。"""
    if not q:
        return False, "请选择安全问题"
    if q not in SECURITY_QUESTIONS:
        return False, "问题不在预设列表中"
    return True, None


def validate_security_answers(answer: str) -> Tuple[bool, Optional[str]]:
    """校验用户填写的安全问题答案是否合法。"""
    if not answer:
        return False, "请填写安全问题的答案"
    if not answer.strip():
        return False, "答案不能为空"
    return True, None
