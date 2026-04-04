# -*- coding: utf-8 -*-
"""
安全问题模块测试
"""

from security_questions import (
    get_security_questions,
    validate_security_questions,
    validate_security_answers,
    SECURITY_QUESTIONS,
)


class TestGetSecurityQuestions:
    """测试获取安全问题列表"""

    def test_get_security_questions_returns_list(self):
        """测试返回列表"""
        questions = get_security_questions()
        assert isinstance(questions, list)

    def test_get_security_questions_returns_copy(self):
        """测试返回的是副本，不影响原列表"""
        questions1 = get_security_questions()
        questions2 = get_security_questions()
        assert questions1 == questions2
        # 修改副本不应影响原列表
        questions1.append("新问题")
        questions3 = get_security_questions()
        assert len(questions3) == len(SECURITY_QUESTIONS)
        assert "新问题" not in questions3

    def test_get_security_questions_contains_items(self):
        """测试包含预设问题"""
        questions = get_security_questions()
        assert len(questions) > 0
        assert "你小学的名字是什么？" in questions


class TestValidateSecurityQuestions:
    """测试验证安全问题"""

    def test_validate_security_questions_valid(self):
        """测试有效的问题"""
        questions = get_security_questions()
        q1 = questions[0]
        q2 = questions[1]
        valid, error = validate_security_questions(q1, q2)
        assert valid is True
        assert error == ""

    def test_validate_security_questions_empty_q1(self):
        """测试问题1为空"""
        questions = get_security_questions()
        q2 = questions[0]
        valid, error = validate_security_questions("", q2)
        assert valid is False
        assert "请选择两个安全问题" in error

    def test_validate_security_questions_empty_q2(self):
        """测试问题2为空"""
        questions = get_security_questions()
        q1 = questions[0]
        valid, error = validate_security_questions(q1, "")
        assert valid is False
        assert "请选择两个安全问题" in error

    def test_validate_security_questions_both_empty(self):
        """测试两个问题都为空"""
        valid, error = validate_security_questions("", "")
        assert valid is False
        assert "请选择两个安全问题" in error

    def test_validate_security_questions_none_q1(self):
        """测试问题1为None"""
        questions = get_security_questions()
        q2 = questions[0]
        valid, error = validate_security_questions(None, q2)  # type: ignore[arg-type]
        assert valid is False
        assert "请选择两个安全问题" in error

    def test_validate_security_questions_same_question(self):
        """测试两个问题相同"""
        questions = get_security_questions()
        q1 = questions[0]
        valid, error = validate_security_questions(q1, q1)
        assert valid is False
        assert "两个安全问题不能相同" in error

    def test_validate_security_questions_q1_not_in_list(self):
        """测试问题1不在列表中"""
        questions = get_security_questions()
        q2 = questions[0]
        valid, error = validate_security_questions("不存在的问题", q2)
        assert valid is False
        assert "问题1不在预设列表中" in error

    def test_validate_security_questions_q2_not_in_list(self):
        """测试问题2不在列表中"""
        questions = get_security_questions()
        q1 = questions[0]
        valid, error = validate_security_questions(q1, "不存在的问题")
        assert valid is False
        assert "问题2不在预设列表中" in error

    def test_validate_security_questions_both_not_in_list(self):
        """测试两个问题都不在列表中"""
        valid, error = validate_security_questions("问题1", "问题2")
        assert valid is False
        assert "问题1不在预设列表中" in error


class TestValidateSecurityAnswers:
    """测试验证安全答案"""

    def test_validate_security_answers_valid(self):
        """测试有效的答案"""
        valid, error = validate_security_answers("答案1", "答案2")
        assert valid is True
        assert error == ""

    def test_validate_security_answers_empty_answer1(self):
        """测试答案1为空"""
        valid, error = validate_security_answers("", "答案2")
        assert valid is False
        assert "请填写两个安全问题的答案" in error

    def test_validate_security_answers_empty_answer2(self):
        """测试答案2为空"""
        valid, error = validate_security_answers("答案1", "")
        assert valid is False
        assert "请填写两个安全问题的答案" in error

    def test_validate_security_answers_both_empty(self):
        """测试两个答案都为空"""
        valid, error = validate_security_answers("", "")
        assert valid is False
        assert "请填写两个安全问题的答案" in error

    def test_validate_security_answers_none_answer1(self):
        """测试答案1为None"""
        valid, error = validate_security_answers(None, "答案2")  # type: ignore[arg-type]
        assert valid is False
        assert "请填写两个安全问题的答案" in error

    def test_validate_security_answers_none_answer2(self):
        """测试答案2为None"""
        valid, error = validate_security_answers("答案1", None)  # type: ignore[arg-type]
        assert valid is False
        assert "请填写两个安全问题的答案" in error

    def test_validate_security_answers_whitespace_only_answer1(self):
        """测试答案1只有空白字符"""
        valid, error = validate_security_answers("   ", "答案2")
        assert valid is False
        assert "答案1不能为空" in error

    def test_validate_security_answers_whitespace_only_answer2(self):
        """测试答案2只有空白字符"""
        valid, error = validate_security_answers("答案1", "   ")
        assert valid is False
        assert "答案2不能为空" in error

    def test_validate_security_answers_with_whitespace(self):
        """测试答案包含空白字符但有效"""
        valid, error = validate_security_answers(" 答案1 ", " 答案2 ")
        assert valid is True
        assert error == ""

    def test_validate_security_answers_single_character(self):
        """测试单字符答案"""
        valid, error = validate_security_answers("a", "b")
        assert valid is True
        assert error == ""

    def test_validate_security_answers_long_answer(self):
        """测试长答案"""
        long_answer = "答案" * 100
        valid, error = validate_security_answers(long_answer, "答案2")
        assert valid is True
        assert error == ""
