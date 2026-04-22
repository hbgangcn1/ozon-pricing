"""
security_questions 模块的单元测试。

Wave 10 Commit 5 起：1 题制 (q / answer 单参)，q2/a2 已废弃。
"""
from security_questions import (
    SECURITY_QUESTIONS,
    get_security_questions,
    validate_security_answers,
    validate_security_questions,
)


class TestGetSecurityQuestions:
    """get_security_questions 返回预设清单的副本。"""

    def test_returns_list_of_strings(self):
        questions = get_security_questions()
        assert isinstance(questions, list)
        assert all(isinstance(q, str) for q in questions)

    def test_returns_five_questions(self):
        assert len(get_security_questions()) == 5

    def test_returns_copy_not_reference(self):
        questions = get_security_questions()
        questions.append("新题")
        assert len(get_security_questions()) == 5

    def test_matches_module_constant(self):
        assert get_security_questions() == list(SECURITY_QUESTIONS)


class TestValidateSecurityQuestions:
    """validate_security_questions 单参校验。"""

    def test_valid_question_returns_true(self):
        ok, err = validate_security_questions(SECURITY_QUESTIONS[0])
        assert ok is True
        assert err is None

    def test_empty_string_rejected(self):
        ok, err = validate_security_questions("")
        assert ok is False
        assert err == "请选择安全问题"

    def test_none_rejected(self):
        ok, err = validate_security_questions(None)  # type: ignore[arg-type]
        assert ok is False
        assert err == "请选择安全问题"

    def test_question_not_in_preset_rejected(self):
        ok, err = validate_security_questions("自定义不在预设的问题？")
        assert ok is False
        assert err == "问题不在预设列表中"


class TestValidateSecurityAnswers:
    """validate_security_answers 单参校验。"""

    def test_valid_answer_returns_true(self):
        ok, err = validate_security_answers("张三")
        assert ok is True
        assert err is None

    def test_empty_string_rejected(self):
        ok, err = validate_security_answers("")
        assert ok is False
        assert err == "请填写安全问题的答案"

    def test_none_rejected(self):
        ok, err = validate_security_answers(None)  # type: ignore[arg-type]
        assert ok is False
        assert err == "请填写安全问题的答案"

    def test_whitespace_only_rejected(self):
        ok, err = validate_security_answers("   ")
        assert ok is False
        assert err == "答案不能为空"

    def test_answer_with_surrounding_whitespace_accepted(self):
        ok, err = validate_security_answers("  张三  ")
        assert ok is True
        assert err is None

    def test_long_answer_accepted(self):
        ok, err = validate_security_answers("a" * 200)
        assert ok is True
        assert err is None
