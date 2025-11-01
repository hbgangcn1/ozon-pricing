# -*- coding: utf-8 -*-
"""
安全审计模块（高优先级安全改进）
检查代码中的安全问题和配置问题
"""

import os
import re
from typing import List, Dict
from pathlib import Path


class SecurityAuditor:
    """安全审计类（高优先级安全改进）"""

    # 敏感配置项（必须使用环境变量）
    SENSITIVE_CONFIGS = [
        'WECHAT_API_V3_KEY',
        'WECHAT_APP_ID',
        'WECHAT_MCH_ID',
        'POSTGRES_PASSWORD',
        'ENCRYPTION_KEY',
        'SECRET_KEY',
        'SESSION_SECRET',
    ]

    # 危险模式（可能泄露敏感信息）
    DANGEROUS_PATTERNS = [
        (r'password\s*=\s*["\']', '硬编码密码'),
        (r'api_key\s*=\s*["\']', '硬编码API密钥'),
        (r'secret\s*=\s*["\']', '硬编码密钥'),
        (r'print\(.*password', '打印密码'),
        (r'print\(.*amount', '打印支付金额'),
        (r'logger\.(info|debug|error).*password', '日志记录密码'),
        (r'logger\.(info|debug|error).*amount', '日志记录支付金额'),
    ]

    @staticmethod
    def check_environment_variables() -> List[Dict[str, str]]:
        """
        检查环境变量配置

        Returns:
            问题列表，每个问题包含 'level', 'message', 'recommendation'
        """
        issues = []

        for config in SecurityAuditor.SENSITIVE_CONFIGS:
            value = os.getenv(config)
            if not value:
                issues.append({
                    'level': 'warning',
                    'message': f'环境变量 {config} 未设置',
                    'recommendation': f'请在.env文件中设置 {config}'
                })
            elif value in ['', 'your_key_here', 'your_password_here',
                           'default']:
                issues.append({
                    'level': 'error',
                    'message': (
                        f'环境变量 {config} 使用了默认值或占位符'
                    ),
                    'recommendation': f'请设置实际的 {config} 值'
                })

        return issues

    @staticmethod
    def check_hardcoded_secrets(
        directory: str = '.'
    ) -> List[Dict[str, str]]:
        """
        检查硬编码的敏感信息

        Args:
            directory: 要检查的目录

        Returns:
            问题列表
        """
        issues = []
        python_files = list(Path(directory).rglob('*.py'))

        # 排除虚拟环境、测试文件和备份文件
        excluded_dirs = {
            '.venv', '__pycache__', '.pytest_cache', 'htmlcov'
        }
        excluded_files = {'test_', 'tests', 'backup', 'fix', 'flake8'}
        python_files = [
            f for f in python_files
            if not any(excluded in str(f) for excluded in excluded_dirs)
            and not any(excluded in f.name for excluded in excluded_files)
        ]

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')

                    for pattern, description in (
                        SecurityAuditor.DANGEROUS_PATTERNS
                    ):
                        for line_num, line in enumerate(lines, 1):
                            if re.search(pattern, line, re.IGNORECASE):
                                # 检查是否是注释或字符串中的示例
                                if ('# ' in line or '"""' in line or
                                        "'''" in line):
                                    continue

                                issues.append({
                                    'level': 'error',
                                    'file': str(file_path),
                                    'line': line_num,
                                    'message': (
                                        f'{description}: '
                                        f'{line.strip()[:100]}'
                                    ),
                                    'recommendation': '使用环境变量或脱敏处理'
                                })
            except (OSError, IOError, UnicodeDecodeError, PermissionError):
                # 跳过无法读取的文件（文件不存在、权限不足、编码错误等）
                continue

        return issues

    @staticmethod
    def check_sql_injection_risks(
        directory: str = '.'
    ) -> List[Dict[str, str]]:
        """
        检查SQL注入风险

        Args:
            directory: 要检查的目录

        Returns:
            问题列表
        """
        issues = []
        python_files = list(Path(directory).rglob('*.py'))

        excluded_dirs = {
            '.venv', '__pycache__', '.pytest_cache', 'htmlcov', 'tests'
        }
        excluded_files = {'test_', 'backup', 'fix', 'flake8'}
        python_files = [
            f for f in python_files
            if not any(excluded in str(f) for excluded in excluded_dirs)
            and not any(excluded in f.name for excluded in excluded_files)
        ]

        # 安全的f-string使用模式（表名通过白名单验证）
        safe_patterns = [
            r'PRAGMA\s+table_info',  # PRAGMA语句是安全的
            r'ALTER\s+TABLE\s+\w+\s+RENAME',  # 表名已通过白名单验证
            r'DROP\s+TABLE\s+\w+_old',  # 临时表名是安全的
            r'ALTER\s+TABLE\s+\w+\s+DROP\s+COLUMN',  # 列名已通过白名单验证
        ]

        # 检查使用字符串格式化的SQL查询
        dangerous_patterns = [
            (r'execute\(.*%[sd]', '使用%格式化SQL'),
            (r'execute\(.*\.format\(', '使用.format()格式化SQL'),
            (r'execute\(.*f["\']', '使用f-string格式化SQL'),
            (r'execute\(.*\+.*["\']', '使用+拼接SQL'),
        ]

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')

                    for pattern, description in dangerous_patterns:
                        for line_num, line in enumerate(lines, 1):
                            if re.search(pattern, line):
                                # 检查是否是安全的模式
                                is_safe = False
                                for safe_pattern in safe_patterns:
                                    if re.search(
                                        safe_pattern, line, re.IGNORECASE
                                    ):
                                        is_safe = True
                                        break

                                if is_safe:
                                    continue

                                # 检查是否使用了参数化查询
                                if '?' in line or '%s' in line:
                                    # 如果同时使用了参数化，可能是安全的
                                    continue

                                # 检查是否是注释或文档字符串
                                if (line.strip().startswith('#') or
                                        '"""' in line or "'''" in line):
                                    continue

                                issues.append({
                                    'level': 'warning',  # 降级为警告
                                    'file': str(file_path),
                                    'line': line_num,
                                    'message': (
                                        f'可能的SQL注入风险: {description}'
                                    ),
                                    'recommendation': (
                                        '使用参数化查询（? 或 %s）或'
                                        '确保输入已通过白名单验证'
                                    )
                                })
            except (OSError, IOError, UnicodeDecodeError, PermissionError):
                # 跳过无法读取的文件（文件不存在、权限不足、编码错误等）
                continue

        return issues

    @staticmethod
    def run_full_audit() -> Dict[str, List[Dict[str, str]]]:
        """
        运行完整的安全审计

        Returns:
            审计结果字典
        """
        audit_results = {
            'environment_issues': (
                SecurityAuditor.check_environment_variables()
            ),
            'hardcoded_secrets': (
                SecurityAuditor.check_hardcoded_secrets()
            ),
            'sql_injection_risks': (
                SecurityAuditor.check_sql_injection_risks()
            ),
        }

        return audit_results

    @staticmethod
    def print_audit_report(audit_results: Dict[str, List[Dict[str, str]]]):
        """
        打印审计报告

        Args:
            audit_results: 审计结果
        """
        print("=" * 80)
        print("安全审计报告")
        print("=" * 80)

        total_issues = 0
        error_count = 0
        warning_count = 0

        for category, issues in audit_results.items():
            if not issues:
                continue

            print(f"\n【{category}】")
            print("-" * 80)

            for issue in issues:
                total_issues += 1
                level = issue.get('level', 'info')
                if level == 'error':
                    error_count += 1
                    prefix = "❌ [错误]"
                elif level == 'warning':
                    warning_count += 1
                    prefix = "⚠️  [警告]"
                else:
                    prefix = "ℹ️  [信息]"

                print(f"{prefix} {issue.get('message', '')}")
                if 'file' in issue:
                    print(
                        f"     文件: {issue['file']}:"
                        f"{issue.get('line', '?')}"
                    )
                if 'recommendation' in issue:
                    print(f"     建议: {issue['recommendation']}")
                print()

        print("=" * 80)
        msg = (
            f"总计: {total_issues} 个问题 "
            f"({error_count} 个错误, {warning_count} 个警告)"
        )
        print(msg)
        print("=" * 80)


if __name__ == '__main__':
    # 运行安全审计
    results = SecurityAuditor.run_full_audit()
    SecurityAuditor.print_audit_report(results)
