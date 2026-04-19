# -*- coding: utf-8 -*-
"""
security/utils.py 单元测试
"""
import pytest

from security.utils import get_client_headers, mask_sensitive_value


class TestGetClientHeaders:
    def test_returns_empty_dict(self):
        result = get_client_headers()
        assert result == {}


class TestMaskSensitiveValue:
    def test_mask_value_shorter_than_visible_chars(self):
        result = mask_sensitive_value("abc", visible_chars=4)
        assert result == "***"

    def test_mask_value_equal_to_visible_chars(self):
        result = mask_sensitive_value("abcd", visible_chars=4)
        assert result == "****"

    def test_mask_value_longer_than_visible_chars(self):
        result = mask_sensitive_value("abcdefgh", visible_chars=4)
        assert result == "abcd****"

    def test_mask_value_default_visible_chars(self):
        result = mask_sensitive_value("abcdefgh")
        assert result == "abcd****"

    def test_mask_empty_string(self):
        result = mask_sensitive_value("")
        assert result == ""

    def test_mask_none_value(self):
        result = mask_sensitive_value(None)
        assert result == ""
