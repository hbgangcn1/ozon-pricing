# -*- coding: utf-8 -*-
"""
utils.py 工具函数测试
测试敏感数据脱敏功能
"""

from utils import mask_sensitive, mask_dict_sensitive


class TestMaskSensitive:
    """测试 mask_sensitive 函数"""

    def test_mask_order_id_with_underscores(self):
        """测试带下划线的订单号脱敏"""
        result = mask_sensitive('PAY_1698765432_abcd1234', 'order_id')
        assert result == 'PAY_****_abcd'
        assert 'PAY_' in result

    def test_mask_order_id_simple(self):
        """测试简单订单号脱敏"""
        result = mask_sensitive('ORDER20250122123456', 'order_id')
        assert result == 'ORDE****'

    def test_mask_email(self):
        """测试邮箱脱敏"""
        result = mask_sensitive('user@example.com', 'email')
        assert result == 'u***r@example.com'
        assert '@example.com' in result

    def test_mask_email_short_local(self):
        """测试短用户名邮箱脱敏"""
        result = mask_sensitive('ab@example.com', 'email')
        assert result == 'a***@example.com'

    def test_mask_phone(self):
        """测试手机号脱敏"""
        result = mask_sensitive('13800138000', 'phone')
        assert result == '138****8000'
        assert len(result) == 11

    def test_mask_ip(self):
        """测试IP地址脱敏"""
        result = mask_sensitive('192.168.1.100', 'ip')
        assert result == '192.168.*.*'
        assert '192.168' in result

    def test_mask_password(self):
        """测试密码脱敏"""
        result = mask_sensitive('MyP@ssw0rd123', 'password')
        assert result == '********'

    def test_mask_auto_short_string(self):
        """测试自动模式 - 短字符串"""
        result = mask_sensitive('test', 'auto')
        assert result == '****'

    def test_mask_auto_long_string(self):
        """测试自动模式 - 长字符串"""
        result = mask_sensitive('this_is_a_long_string', 'auto')
        assert result == 'this****ring'
        assert result.startswith('this')
        assert result.endswith('ring')

    def test_mask_empty_string(self):
        """测试空字符串"""
        result = mask_sensitive('', 'auto')
        assert result == '****'

    def test_mask_none_value(self):
        """测试None值"""
        result = mask_sensitive(None, 'auto')  # type: ignore[arg-type]
        assert result == '****'

    def test_mask_unknown_type(self):
        """测试未知类型（使用默认逻辑）"""
        result = mask_sensitive('test123', 'unknown_type')
        assert result == '****'  # 长度<=8


class TestMaskDictSensitive:
    """测试 mask_dict_sensitive 函数"""

    def test_mask_dict_default_keys(self):
        """测试默认敏感键"""
        data = {
            'password': 'mypassword123',
            'token': 'abc123token',
            'secret': 'my_secret',
            'name': 'John Doe'
        }
        result = mask_dict_sensitive(data)
        
        assert result['password'] == '********'
        assert result['token'] == '********'
        assert result['secret'] == '********'
        assert result['name'] == 'John Doe'  # 不在敏感列表中

    def test_mask_dict_custom_keys(self):
        """测试自定义敏感键"""
        data = {
            'username': 'john_doe',
            'secret_key': 'my_secret_123',
            'public_info': 'public'
        }
        result = mask_dict_sensitive(data, ['username', 'secret'])
        
        assert result['username'] == '********'
        assert result['secret_key'] == '********'  # 包含'secret'
        assert result['public_info'] == 'public'

    def test_mask_dict_case_insensitive(self):
        """测试键名大小写不敏感"""
        data = {
            'PASSWORD': 'mypassword',
            'Token': 'mytoken',
            'API_KEY': 'myapikey'
        }
        result = mask_dict_sensitive(data)
        
        assert result['PASSWORD'] == '********'
        assert result['Token'] == '********'
        assert result['API_KEY'] == '********'

    def test_mask_dict_empty(self):
        """测试空字典"""
        result = mask_dict_sensitive({})
        assert result == {}

    def test_mask_dict_no_sensitive_keys(self):
        """测试没有敏感键的字典"""
        data = {'name': 'John', 'age': 30}
        result = mask_dict_sensitive(data)
        assert result == data

    def test_mask_dict_with_none_values(self):
        """测试包含None值的敏感字段"""
        data = {'password': None, 'name': 'John'}
        result = mask_dict_sensitive(data)
        assert result['password'] == '****'  # None被转为****
        assert result['name'] == 'John'

    def test_mask_dict_with_numeric_values(self):
        """测试敏感键包含数值"""
        data = {'password': 123456, 'token': 789, 'name': 'John'}
        result = mask_dict_sensitive(data)
        assert result['password'] == '****'
        assert result['token'] == '****'
        assert result['name'] == 'John'

    def test_mask_dict_preserve_other_fields(self):
        """测试保留非敏感字段"""
        data = {
            'order_id': 'ORDER123',
            'password': 'mypass',
            'amount': 9900,
            'status': 'PAID',
            'created_at': 1234567890
        }
        result = mask_dict_sensitive(data)
        
        assert result['password'] == '********'  # 敏感字段被脱敏
        assert result['order_id'] == 'ORDER123'  # 非敏感字段保留
        assert result['amount'] == 9900
        assert result['status'] == 'PAID'
        assert result['created_at'] == 1234567890


class TestMaskSensitiveEdgeCases:
    """测试边界情况"""

    def test_very_long_string(self):
        """测试非常长的字符串"""
        long_string = 'a' * 1000
        result = mask_sensitive(long_string, 'auto')
        assert len(result) < len(long_string)
        assert '***' in result

    def test_special_characters(self):
        """测试特殊字符"""
        result = mask_sensitive('user+tag@example.com', 'email')
        assert '@' in result
        assert 'example' in result

    def test_unicode_string(self):
        """测试Unicode字符"""
        result = mask_sensitive('用户@示例.com', 'email')
        assert '@' in result

    def test_order_id_short(self):
        """测试短订单号"""
        result = mask_sensitive('ORD123', 'order_id')
        assert result.startswith('ORD')
        assert '***' in result

    def test_phone_invalid_format(self):
        """测试无效手机号格式"""
        result = mask_sensitive('123', 'phone')
        assert '***' in result

    def test_ip_invalid_format(self):
        """测试无效IP格式"""
        result = mask_sensitive('192.168', 'ip')
        # 不符合IP格式，应该使用auto模式
        assert '***' in result

