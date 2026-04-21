import pytest

from password_utils import (
    check_password_strength,
    get_password_requirements_text,
    get_password_strength_color,
    validate_password_strength,
)


class TestValidatePasswordStrength:
    def test_none_input_returns_invalid(self):
        result = validate_password_strength(None)
        assert result["is_valid"] is False
        assert "密码不能为空" in result["errors"]
        assert result["score"] == 0

    @pytest.mark.parametrize("bad", [123, 12.5, [], {}, True, b"bytes"])
    def test_non_string_input_rejected(self, bad):
        result = validate_password_strength(bad)
        assert result["is_valid"] is False
        assert "密码必须是字符串类型" in result["errors"]
        assert result["score"] == 0

    def test_empty_string_fails_all_rules(self):
        result = validate_password_strength("")
        assert result["is_valid"] is False
        assert result["score"] == 0
        assert "密码长度必须至少13位" in result["errors"]
        assert "密码必须包含大写字母" in result["errors"]
        assert "密码必须包含小写字母" in result["errors"]
        assert "密码必须包含数字" in result["errors"]
        assert "密码必须包含特殊字符" in result["errors"]

    def test_short_but_complex_fails_only_length(self):
        eight_char_complex = "Ab1!cdef"
        result = validate_password_strength(eight_char_complex)
        assert result["is_valid"] is False
        assert "密码长度必须至少13位" in result["errors"]
        assert "密码必须包含大写字母" not in result["errors"]
        assert "密码必须包含小写字母" not in result["errors"]
        assert "密码必须包含数字" not in result["errors"]
        assert "密码必须包含特殊字符" not in result["errors"]
        assert result["score"] == 4

    def test_long_but_lowercase_only(self):
        fourteen_char_lowercase_only = "abcdefghijklmn"
        result = validate_password_strength(fourteen_char_lowercase_only)
        assert result["is_valid"] is False
        assert "密码必须包含大写字母" in result["errors"]
        assert "密码必须包含数字" in result["errors"]
        assert "密码必须包含特殊字符" in result["errors"]
        assert result["score"] == 2

    def test_missing_only_uppercase(self):
        result = validate_password_strength("abc1234567890!")
        assert result["is_valid"] is False
        assert result["errors"] == ["密码必须包含大写字母"]
        assert result["score"] == 4

    def test_missing_only_lowercase(self):
        result = validate_password_strength("ABC1234567890!")
        assert result["is_valid"] is False
        assert result["errors"] == ["密码必须包含小写字母"]
        assert result["score"] == 4

    def test_missing_only_digit(self):
        result = validate_password_strength("Abcdefghijklmn!")
        assert result["is_valid"] is False
        assert result["errors"] == ["密码必须包含数字"]
        assert result["score"] == 4

    def test_missing_only_special(self):
        result = validate_password_strength("Abcdefghijklm1")
        assert result["is_valid"] is False
        assert result["errors"] == ["密码必须包含特殊字符"]
        assert result["score"] == 4

    def test_valid_password_passes_all(self):
        result = validate_password_strength("Secur3-P@ssw0rd")
        assert result["is_valid"] is True
        assert result["errors"] == []
        assert result["score"] == 5

    @pytest.mark.parametrize("special", list("~!@#$%^&*+-/.,\\{}[]();:?<>\"'_`"))
    def test_each_special_character_counts(self, special):
        pwd = f"Abcdefghijkl1{special}"
        result = validate_password_strength(pwd)
        assert result["is_valid"] is True, f"special '{special}' should satisfy"
        assert result["score"] == 5

    def test_exactly_13_chars_boundary(self):
        result = validate_password_strength("Abcdefghijk1!")
        assert len("Abcdefghijk1!") == 13
        assert result["is_valid"] is True
        assert result["score"] == 5

    def test_12_chars_fails_length(self):
        result = validate_password_strength("Abcdefghij1!")
        assert len("Abcdefghij1!") == 12
        assert result["is_valid"] is False
        assert "密码长度必须至少13位" in result["errors"]


class TestGetPasswordRequirementsText:
    def test_returns_non_empty_string(self):
        text = get_password_requirements_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_mentions_all_rules(self):
        text = get_password_requirements_text()
        assert "13" in text
        assert "大写" in text
        assert "小写" in text
        assert "数字" in text
        assert "特殊字符" in text


class TestGetPasswordStrengthColor:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0, "red"),
            (1, "red"),
            (2, "orange"),
            (3, "yellow"),
            (4, "lightgreen"),
            (5, "green"),
        ],
    )
    def test_integer_scores(self, score, expected):
        assert get_password_strength_color(score) == expected

    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.5, "red"),
            (1.5, "orange"),
            (2.5, "yellow"),
            (3.5, "lightgreen"),
            (4.5, "green"),
        ],
    )
    def test_float_scores(self, score, expected):
        assert get_password_strength_color(score) == expected

    def test_negative_score_returns_red(self):
        assert get_password_strength_color(-1) == "red"

    def test_score_above_five_returns_green(self):
        assert get_password_strength_color(10) == "green"


class TestCheckPasswordStrength:
    def test_compat_shim_matches_validate(self):
        pwd = "Secur3-P@ssw0rd"
        assert check_password_strength(pwd) == validate_password_strength(pwd)

    def test_compat_shim_none(self):
        assert check_password_strength(None) == validate_password_strength(None)
