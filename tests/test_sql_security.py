# -*- coding: utf-8 -*-
"""
sql_security.py 单元测试
"""
import pytest

from sql_security import (
    SQLSecurityError,
    validate_table_name,
    validate_field_name,
    validate_field_names,
    validate_id_list,
    build_update_set_clause,
    build_in_clause,
    build_where_clause,
    sanitize_sql_fragment,
    validate_sql_statement,
    SAFE_TABLE_NAMES,
    DANGEROUS_KEYWORDS,
)


class TestValidateTableName:
    def test_valid_table_name(self):
        assert validate_table_name("users") == "users"
        assert validate_table_name("products") == "products"
        assert validate_table_name("logistics") == "logistics"

    def test_valid_table_name_with_whitespace(self):
        assert validate_table_name("  users  ") == "users"

    def test_invalid_table_name_not_in_whitelist(self):
        with pytest.raises(SQLSecurityError, match="非法的表名"):
            validate_table_name("hackers")

    def test_invalid_table_name_empty(self):
        with pytest.raises(SQLSecurityError, match="表名不能为空"):
            validate_table_name("")

    def test_invalid_table_name_whitespace_only(self):
        with pytest.raises(SQLSecurityError, match="表名不能为空"):
            validate_table_name("   ")

    def test_invalid_table_name_not_string(self):
        with pytest.raises(SQLSecurityError, match="表名必须是字符串类型"):
            validate_table_name(123)

    def test_all_whitelisted_tables(self):
        for table in SAFE_TABLE_NAMES:
            assert validate_table_name(table) == table


class TestValidateFieldName:
    def test_valid_field_name(self):
        assert validate_field_name("username") == "username"
        assert validate_field_name("user_id") == "user_id"
        assert validate_field_name("_private") == "_private"

    def test_valid_field_name_with_allowed_fields(self):
        allowed = {"id", "name", "email"}
        assert validate_field_name("name", allowed_fields=allowed) == "name"

    def test_invalid_field_name_not_in_allowed_fields(self):
        allowed = {"id", "name"}
        with pytest.raises(SQLSecurityError, match="非法的字段名"):
            validate_field_name("password", allowed_fields=allowed)

    def test_invalid_field_name_empty(self):
        with pytest.raises(SQLSecurityError, match="字段名不能为空"):
            validate_field_name("")

    def test_invalid_field_name_with_number_prefix(self):
        with pytest.raises(SQLSecurityError, match="非法的字段名格式"):
            validate_field_name("123field")

    def test_invalid_field_name_with_special_chars(self):
        with pytest.raises(SQLSecurityError, match="非法的字段名格式"):
            validate_field_name("field-name")

    def test_invalid_field_name_with_dangerous_keyword(self):
        with pytest.raises(SQLSecurityError, match="包含危险的SQL关键字"):
            validate_field_name("fieldnameDROP")

    def test_invalid_field_name_not_string(self):
        with pytest.raises(SQLSecurityError, match="字段名必须是字符串类型"):
            validate_field_name(None)


class TestValidateFieldNames:
    def test_valid_field_names(self):
        result = validate_field_names(["id", "username", "email"])
        assert result == ["id", "username", "email"]

    def test_valid_field_names_with_allowed_fields(self):
        allowed = {"id", "name", "email"}
        result = validate_field_names(["id", "name"], allowed_fields=allowed)
        assert result == ["id", "name"]

    def test_invalid_field_names_one_invalid(self):
        allowed = {"id", "name"}
        with pytest.raises(SQLSecurityError):
            validate_field_names(["id", "password"], allowed_fields=allowed)


class TestValidateIdList:
    def test_valid_id_list(self):
        result = validate_id_list([1, 2, 3])
        assert result == [1, 2, 3]

    def test_valid_id_list_string_ints(self):
        result = validate_id_list(["1", "2", "3"])
        assert result == [1, 2, 3]

    def test_invalid_id_list_exceeds_max_size(self):
        with pytest.raises(SQLSecurityError, match="超过最大限制"):
            validate_id_list(list(range(1001)), max_size=1000)

    def test_invalid_id_list_not_list(self):
        with pytest.raises(SQLSecurityError, match="ID列表必须是列表类型"):
            validate_id_list("1,2,3")

    def test_invalid_id_list_contains_zero(self):
        with pytest.raises(SQLSecurityError, match="ID必须是正整数"):
            validate_id_list([1, 0, 3])

    def test_invalid_id_list_contains_negative(self):
        with pytest.raises(SQLSecurityError, match="ID必须是正整数"):
            validate_id_list([1, -1, 3])

    def test_invalid_id_list_contains_invalid_value(self):
        with pytest.raises(SQLSecurityError, match="无效的ID"):
            validate_id_list([1, "abc", 3])


class TestBuildUpdateSetClause:
    def test_valid_update_set_clause(self):
        allowed = {"name", "email", "password"}
        result = build_update_set_clause(
            {"name": "test", "email": "test@example.com"},
            allowed_fields=allowed
        )
        set_clause, values = result
        assert "name = ?" in set_clause
        assert "email = ?" in set_clause
        assert values == ["test", "test@example.com"]

    def test_invalid_update_set_clause_empty_dict(self):
        with pytest.raises(SQLSecurityError, match="更新字典不能为空"):
            build_update_set_clause({}, {"name"})

    def test_invalid_update_set_clause_field_not_allowed(self):
        allowed = {"name"}
        with pytest.raises(SQLSecurityError):
            build_update_set_clause({"password": "secret"}, allowed_fields=allowed)


class TestBuildInClause:
    def test_valid_in_clause(self):
        result = build_in_clause([1, 2, 3])
        assert result == ("IN (?,?,?)", [1, 2, 3])

    def test_valid_in_clause_empty_list(self):
        result = build_in_clause([])
        assert result == ("IN (NULL)", [])

    def test_valid_in_clause_with_max_size(self):
        ids = list(range(1, 6))
        result = build_in_clause(ids, max_size=10)
        assert result == ("IN (?,?,?,?,?)", ids)

    def test_invalid_in_clause_exceeds_max_size(self):
        with pytest.raises(SQLSecurityError, match="超过最大限制"):
            build_in_clause(list(range(1001)), max_size=1000)


class TestBuildWhereClause:
    def test_valid_where_clause(self):
        result = build_where_clause(["id = ?", "name = ?"], [1, "test"])
        assert result == ("id = ? AND name = ?", [1, "test"])

    def test_valid_where_clause_empty_conditions(self):
        result = build_where_clause([], [])
        assert result == ("1=1", [])

    def test_valid_where_clause_with_percent_s(self):
        result = build_where_clause(["name LIKE %s"], ["test%"])
        assert result == ("name LIKE %s", ["test%"])

    def test_invalid_where_clause_condition_not_string(self):
        with pytest.raises(SQLSecurityError, match="WHERE条件必须是字符串"):
            build_where_clause([123], [])

    def test_invalid_where_clause_no_placeholder(self):
        with pytest.raises(SQLSecurityError, match="必须使用参数化查询"):
            build_where_clause(["id = 1"], [])


class TestSanitizeSqlFragment:
    def test_sanitize_removes_single_line_comment(self):
        result = sanitize_sql_fragment("SELECT * FROM users -- comment")
        assert result == "SELECT * FROM users"

    def test_sanitize_removes_multi_line_comment(self):
        result = sanitize_sql_fragment("SELECT /* comment */ * FROM users")
        assert result == "SELECT  * FROM users"

    def test_sanitize_removes_semicolon(self):
        result = sanitize_sql_fragment("SELECT * FROM users; DROP TABLE")
        assert result == "SELECT * FROM users DROP TABLE"

    def test_sanitize_returns_stripped(self):
        result = sanitize_sql_fragment("  SELECT *  ")
        assert result == "SELECT *"

    def test_sanitize_non_string_raises(self):
        with pytest.raises(SQLSecurityError, match="SQL片段必须是字符串"):
            sanitize_sql_fragment(123)


class TestValidateSqlStatement:
    def test_valid_select_statement(self):
        result = validate_sql_statement("SELECT * FROM users")
        assert result == "SELECT * FROM users"

    def test_valid_select_with_where(self):
        result = validate_sql_statement("SELECT id, name FROM users WHERE id = ?")
        assert result == "SELECT id, name FROM users WHERE id = ?"

    def test_valid_with_allowed_operations(self):
        allowed = {"SELECT", "INSERT"}
        result = validate_sql_statement("SELECT * FROM users", allowed_operations=allowed)
        assert result == "SELECT * FROM users"

    def test_invalid_multi_statement(self):
        with pytest.raises(SQLSecurityError, match="不能包含多个语句"):
            validate_sql_statement("SELECT * FROM users; DROP TABLE users")

    def test_invalid_operation_not_allowed(self):
        allowed = {"SELECT"}
        with pytest.raises(SQLSecurityError, match="不允许的SQL操作"):
            validate_sql_statement("DROP TABLE users", allowed_operations=allowed)

    def test_invalid_not_string(self):
        with pytest.raises(SQLSecurityError, match="SQL语句必须是字符串"):
            validate_sql_statement(None)
