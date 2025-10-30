# utils.py
# 通用工具函数

import re
from typing import Optional


def mask_sensitive(data: str, mask_type: str = 'auto') -> str:
    """
    敏感信息脱敏

    Args:
        data: 待脱敏的数据
        mask_type: 脱敏类型
            - 'auto': 自动识别
            - 'order_id': 订单号
            - 'email': 邮箱
            - 'phone': 手机号
            - 'password': 密码
            - 'ip': IP地址

    Returns:
        脱敏后的字符串

    Examples:
        >>> mask_sensitive('PAY_1698765432_abcd1234', 'order_id')
        'PAY_****_****'
        >>> mask_sensitive('user@example.com', 'email')
        'u***@example.com'
    """
    if not data or not isinstance(data, str):
        return '****'

    # 自动识别类型
    if mask_type == 'auto':
        if data.startswith('PAY_'):
            mask_type = 'order_id'
        elif '@' in data:
            mask_type = 'email'
        elif re.match(r'^\d{11}$', data):
            mask_type = 'phone'
        elif re.match(r'^\d{1,3}(\.\d{1,3}){3}$', data):
            mask_type = 'ip'

    # 订单号脱敏: PAY_1698765432_abcd1234 -> PAY_****_****
    if mask_type == 'order_id':
        parts = data.split('_')
        if len(parts) >= 3:
            return f"{parts[0]}_****_{parts[-1][:4] if len(parts[-1]) > 4 else '****'}"  # noqa: E501
        return data[:4] + '****'

    # 邮箱脱敏: user@example.com -> u***@example.com
    elif mask_type == 'email':
        if '@' in data:
            local, domain = data.split('@', 1)
            if len(local) <= 2:
                masked_local = local[0] + '***'
            else:
                masked_local = local[0] + '***' + local[-1]
            return f"{masked_local}@{domain}"
        return '****'

    # 手机号脱敏: 13812345678 -> 138****5678
    elif mask_type == 'phone':
        if len(data) == 11:
            return data[:3] + '****' + data[-4:]
        return '****'

    # IP地址脱敏: 192.168.1.100 -> 192.168.*.*
    elif mask_type == 'ip':
        parts = data.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*"
        return '****'

    # 密码完全隐藏
    elif mask_type == 'password':
        return '********'

    # 默认：保留前后4位
    else:
        if len(data) <= 8:
            return '****'
        return f"{data[:4]}****{data[-4:]}"


def mask_dict_sensitive(
    data: dict,
    sensitive_keys: Optional[list] = None
) -> dict:
    """
    脱敏字典中的敏感字段

    Args:
        data: 待脱敏的字典
        sensitive_keys: 敏感字段列表，默认包含常见敏感字段

    Returns:
        脱敏后的字典（深拷贝）
    """
    if sensitive_keys is None:
        sensitive_keys = [
            'password', 'pwd', 'token', 'secret', 'api_key',
            'private_key', 'cert', 'credential', 'auth'
        ]

    import copy
    result = copy.deepcopy(data)

    for key, value in result.items():
        # 检查键名是否包含敏感词
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            if isinstance(value, str):
                result[key] = '********'
            else:
                result[key] = '****'

    return result
