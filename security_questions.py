# -*- coding: utf-8 -*-
"""
安全问题配置模块
存储预设的安全问题列表
"""

# 预设安全问题列表
SECURITY_QUESTIONS = [
    "你小学的名字是什么？",
    "你母亲的生日是？",
    "你第一只宠物的名字？",
    "你最喜欢的老师姓什么？",
    "你出生的城市是？",
    "你最喜欢的食物是什么？",
    "你父亲的名字中第二个字是？",
    "你第一个手机号的后三位是？",
    "你最喜欢的电影是？",
    "你小学班主任的名字是？",
]


def get_security_questions():
    """
    获取安全问题列表

    Returns:
        list: 安全问题列表
    """
    return SECURITY_QUESTIONS.copy()


def validate_security_questions(q1: str, q2: str) -> tuple[bool, str]:
    """
    验证两个安全问题是否有效

    Args:
        q1: 问题1
        q2: 问题2

    Returns:
        tuple: (是否有效, 错误信息)
    """
    if not q1 or not q2:
        return False, "请选择两个安全问题"

    if q1 == q2:
        return False, "两个安全问题不能相同"

    questions = get_security_questions()
    if q1 not in questions:
        return False, "问题1不在预设列表中"

    if q2 not in questions:
        return False, "问题2不在预设列表中"

    return True, ""


def validate_security_answers(
    answer1: str, answer2: str
) -> tuple[bool, str]:
    """
    验证安全答案是否有效

    Args:
        answer1: 答案1
        answer2: 答案2

    Returns:
        tuple: (是否有效, 错误信息)
    """
    if not answer1 or not answer2:
        return False, "请填写两个安全问题的答案"

    # 答案不区分大小写，但至少需要1个字符
    if len(answer1.strip()) < 1:
        return False, "答案1不能为空"

    if len(answer2.strip()) < 1:
        return False, "答案2不能为空"

    return True, ""
