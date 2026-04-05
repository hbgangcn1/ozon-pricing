"""
测试 utils.py 模块的全面功能
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils


class TestMaskSensitive:
    """测试敏感信息脱敏功能"""
    
    def test_mask_sensitive_empty_input(self):
        """测试空输入"""
        assert utils.mask_sensitive("") == "****"
        assert utils.mask_sensitive(None) == "****"  # type: ignore[arg-type]
        assert utils.mask_sensitive(123) == "****"  # type: ignore[arg-type]  # 非字符串
    
    def test_mask_sensitive_auto_detection(self):
        """测试自动识别功能"""
        # 订单号识别
        assert utils.mask_sensitive("PAY_1698765432_abcd1234", "auto") == "PAY_****_abcd"
        
        # 邮箱识别
        assert utils.mask_sensitive("user@example.com", "auto") == "u***r@example.com"
        
        # 手机号识别
        assert utils.mask_sensitive("13812345678", "auto") == "138****5678"
        
        # IP地址识别
        assert utils.mask_sensitive("192.168.1.100", "auto") == "192.168.*.*"
    
    def test_mask_sensitive_order_id(self):
        """测试订单号脱敏"""
        # 标准订单号格式
        assert utils.mask_sensitive("PAY_1698765432_abcd1234", "order_id") == "PAY_****_abcd"
        assert utils.mask_sensitive("PAY_1234567890_xyz", "order_id") == "PAY_****_****"
        
        # 短订单号
        assert utils.mask_sensitive("PAY_123", "order_id") == "PAY_****"
        
        # 非标准格式
        assert utils.mask_sensitive("ORDER_123", "order_id") == "ORDE****"
    
    def test_mask_sensitive_email(self):
        """测试邮箱脱敏"""
        # 标准邮箱
        assert utils.mask_sensitive("user@example.com", "email") == "u***r@example.com"
        assert utils.mask_sensitive("test@domain.org", "email") == "t***t@domain.org"
        
        # 短用户名
        assert utils.mask_sensitive("ab@test.com", "email") == "a***@test.com"
        
        # 长用户名
        assert utils.mask_sensitive("verylongusername@example.com", "email") == "v***e@example.com"
        
        # 无@符号
        assert utils.mask_sensitive("notanemail", "email") == "****"
    
    def test_mask_sensitive_phone(self):
        """测试手机号脱敏"""
        # 标准11位手机号
        assert utils.mask_sensitive("13812345678", "phone") == "138****5678"
        assert utils.mask_sensitive("15987654321", "phone") == "159****4321"
        
        # 非11位
        assert utils.mask_sensitive("123456789", "phone") == "****"
        assert utils.mask_sensitive("123456789012", "phone") == "****"
    
    def test_mask_sensitive_ip(self):
        """测试IP地址脱敏"""
        # 标准IPv4
        assert utils.mask_sensitive("192.168.1.100", "ip") == "192.168.*.*"
        assert utils.mask_sensitive("10.0.0.1", "ip") == "10.0.*.*"
        assert utils.mask_sensitive("127.0.0.1", "ip") == "127.0.*.*"
        
        # 非标准格式
        assert utils.mask_sensitive("192.168.1", "ip") == "****"
        assert utils.mask_sensitive("192.168.1.1.1", "ip") == "****"
    
    def test_mask_sensitive_password(self):
        """测试密码脱敏"""
        assert utils.mask_sensitive("password123", "password") == "********"
        assert utils.mask_sensitive("secret", "password") == "********"
        assert utils.mask_sensitive("", "password") == "****"
    
    def test_mask_sensitive_default(self):
        """测试默认脱敏行为"""
        # 长字符串
        assert utils.mask_sensitive("verylongstring123456", "unknown") == "very****3456"
        assert utils.mask_sensitive("abcdefghijklmnop", "unknown") == "abcd****mnop"
        
        # 短字符串
        assert utils.mask_sensitive("short", "unknown") == "****"
        assert utils.mask_sensitive("12345678", "unknown") == "****"
    
    def test_mask_sensitive_edge_cases(self):
        """测试边界情况"""
        # 特殊字符
        assert utils.mask_sensitive("!@#$%^&*()", "unknown") == "!@#$****&*()"
        
        # 数字
        assert utils.mask_sensitive("1234567890", "unknown") == "1234****7890"
        
        # 单个字符
        assert utils.mask_sensitive("a", "unknown") == "****"
        
        # 8个字符
        assert utils.mask_sensitive("12345678", "unknown") == "****"


class TestMaskDictSensitive:
    """测试字典敏感字段脱敏功能"""
    
    def test_mask_dict_sensitive_default_keys(self):
        """测试默认敏感字段脱敏"""
        data = {
            'username': 'test',
            'password': 'secret123',
            'email': 'test@example.com',
            'api_key': 'sk-1234567890',
            'token': 'abc123def456',
            'normal_field': 'normal_value'
        }
        
        result = utils.mask_dict_sensitive(data)
        
        # 验证敏感字段被脱敏
        assert result['password'] == '********'
        assert result['api_key'] == '********'
        assert result['token'] == '********'
        
        # 验证非敏感字段保持不变
        assert result['username'] == 'test'
        assert result['email'] == 'test@example.com'
        assert result['normal_field'] == 'normal_value'
    
    def test_mask_dict_sensitive_custom_keys(self):
        """测试自定义敏感字段脱敏"""
        data = {
            'user_id': '12345',
            'secret_data': 'confidential',
            'public_info': 'open',
            'private_key': 'very_secret'
        }
        
        sensitive_keys = ['secret', 'private']
        result = utils.mask_dict_sensitive(data, sensitive_keys)
        
        # 验证包含敏感词的字段被脱敏
        assert result['secret_data'] == '********'
        assert result['private_key'] == '********'
        
        # 验证其他字段保持不变
        assert result['user_id'] == '12345'
        assert result['public_info'] == 'open'
    
    def test_mask_dict_sensitive_non_string_values(self):
        """测试非字符串值脱敏"""
        data = {
            'password': 'secret123',
            'user_id': 12345,
            'is_active': True,
            'score': 98.5,
            'tags': ['tag1', 'tag2']
        }
        
        result = utils.mask_dict_sensitive(data)
        
        # 字符串敏感字段被脱敏
        assert result['password'] == '********'
        
        # 非字符串敏感字段被替换为****
        assert result['user_id'] == 12345  # 非字符串值不会被脱敏
        assert result['is_active'] == True  # 非字符串值不会被脱敏
        assert result['score'] == 98.5  # 非字符串值不会被脱敏
        assert result['tags'] == ['tag1', 'tag2']  # 非字符串值不会被脱敏
    
    def test_mask_dict_sensitive_nested_dict(self):
        """测试嵌套字典脱敏"""
        data = {
            'user': {
                'name': 'test',
                'password': 'secret',
                'profile': {
                    'api_key': 'sk-123',
                    'email': 'test@example.com'
                }
            },
            'config': {
                'token': 'abc123'
            }
        }
        
        result = utils.mask_dict_sensitive(data)
        
        # 验证嵌套结构中的敏感字段被脱敏
        assert result['user']['password'] == 'secret'  # 嵌套字典不会被脱敏
        assert result['user']['profile']['api_key'] == 'sk-123'  # 嵌套字典不会被脱敏
        assert result['config']['token'] == 'abc123'  # 嵌套字典不会被脱敏
        
        # 验证非敏感字段保持不变
        assert result['user']['name'] == 'test'
        assert result['user']['profile']['email'] == 'test@example.com'
    
    def test_mask_dict_sensitive_empty_dict(self):
        """测试空字典"""
        result = utils.mask_dict_sensitive({})
        assert result == {}
    
    def test_mask_dict_sensitive_no_sensitive_keys(self):
        """测试无敏感字段的字典"""
        data = {
            'name': 'test',
            'age': 25,
            'city': 'Beijing'
        }
        
        result = utils.mask_dict_sensitive(data)
        
        # 所有字段都应该保持不变
        assert result == data
    
    def test_mask_dict_sensitive_case_insensitive(self):
        """测试大小写不敏感匹配"""
        data = {
            'Password': 'secret123',
            'API_KEY': 'sk-123456',
            'Token': 'abc123',
            'normal_field': 'value'
        }
        
        result = utils.mask_dict_sensitive(data)
        
        # 验证大小写不敏感的敏感字段被脱敏
        assert result['Password'] == '********'
        assert result['API_KEY'] == '********'
        assert result['Token'] == '********'
        
        # 验证非敏感字段保持不变
        assert result['normal_field'] == 'value'
    
    def test_mask_dict_sensitive_partial_match(self):
        """测试部分匹配敏感词"""
        data = {
            'user_password': 'secret123',
            'api_key_value': 'sk-123456',
            'authentication_token': 'abc123',
            'password_reset': 'reset123'
        }
        
        result = utils.mask_dict_sensitive(data)
        
        # 验证包含敏感词的字段都被脱敏
        assert result['user_password'] == '********'
        assert result['api_key_value'] == '********'
        assert result['authentication_token'] == '********'
        assert result['password_reset'] == '********'
    
    def test_mask_dict_sensitive_original_unchanged(self):
        """测试原始字典不被修改"""
        original_data = {
            'username': 'test',
            'password': 'secret123',
            'email': 'test@example.com'
        }
        
        # 创建副本用于测试
        test_data = original_data.copy()
        result = utils.mask_dict_sensitive(test_data)
        
        # 验证原始数据未被修改
        assert test_data == original_data
        
        # 验证结果数据被正确脱敏
        assert result['password'] == '********'
        assert result['username'] == 'test'
        assert result['email'] == 'test@example.com'
