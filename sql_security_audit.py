# -*- coding: utf-8 -*-
"""
SQL安全检查工具
用于审查代码中的SQL注入风险
"""

import re
from typing import List, Dict, Optional
from pathlib import Path


class SQLSecurityAuditor:
    """SQL安全检查器"""

    # 危险的SQL模式
    DANGEROUS_PATTERNS = [
        (r'execute\s*\(\s*f["\']', 'f-string SQL执行'),
        (r'execute\s*\(\s*["\'].*%[sd]', '字符串格式化SQL'),
        (r'execute\s*\(\s*["\'].*\{.*\}', '字符串插值SQL'),
        (r'execute\s*\(\s*["\']\+', '字符串拼接SQL'),
        (r'\.format\s*\([^)]*\)\s*\)', 'format方法SQL'),
    ]

    # 安全模式（参数化查询）
    SAFE_PATTERNS = [
        (r'execute\s*\(\s*["\'][^"\']*\?[^"\']*["\']\s*,', '参数化查询（?占位符）'),
        (r'execute\s*\(\s*["\'][^"\']*%s[^"\']*["\']\s*,', '参数化查询（%s占位符）'),
    ]

    def __init__(self, project_root: str = '.'):
        """
        初始化检查器

        Args:
            project_root: 项目根目录
        """
        self.project_root = Path(project_root)
        self.issues: List[Dict] = []
        self.safe_count = 0

    def scan_file(self, file_path: Path) -> List[Dict]:
        """
        扫描单个文件

        Args:
            file_path: 文件路径

        Returns:
            问题列表
        """
        issues = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            # 检查危险模式
            for line_num, line in enumerate(lines, 1):
                for pattern, description in self.DANGEROUS_PATTERNS:
                    if re.search(pattern, line):
                        # 检查是否是安全的情况（如PRAGMA命令）
                        if self._is_safe_context(line):
                            continue

                        issues.append({
                            'file': str(
                                file_path.relative_to(self.project_root)
                            ),
                            'line': line_num,
                            'type': 'dangerous',
                            'description': description,
                            'code': line.strip()
                        })

                # 检查安全模式
                for pattern, description in self.SAFE_PATTERNS:
                    if re.search(pattern, line):
                        self.safe_count += 1

        except Exception as e:
            issues.append({
                'file': str(file_path.relative_to(self.project_root)),
                'line': 0,
                'type': 'error',
                'description': f'文件读取失败: {e}',
                'code': ''
            })

        return issues

    @staticmethod
    def _is_safe_context(line: str) -> bool:
        """
        检查是否是安全的上下文（如PRAGMA、表操作等）

        Args:
            line: 代码行

        Returns:
            是否安全
        """
        safe_keywords = [
            'PRAGMA',
            'CREATE TABLE',
            'DROP TABLE',
            'ALTER TABLE',
            'CREATE INDEX',
            'DROP INDEX'
        ]
        return any(keyword in line.upper() for keyword in safe_keywords)

    def scan_directory(
        self,
        directory: Optional[Path] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        扫描目录

        Args:
            directory: 目录路径
            exclude_patterns: 排除模式列表

        Returns:
            问题列表
        """
        if directory is None:
            directory = self.project_root

        if exclude_patterns is None:
            exclude_patterns = [
                '__pycache__',
                '.git',
                '.venv',
                'venv',
                'node_modules',
                'htmlcov',
                '*.pyc'
            ]

        all_issues = []
        py_files = list(directory.rglob('*.py'))

        for py_file in py_files:
            # 检查是否应该排除
            should_exclude = False
            for pattern in exclude_patterns:
                if pattern in str(py_file):
                    should_exclude = True
                    break

            if should_exclude:
                continue

            issues = self.scan_file(py_file)
            all_issues.extend(issues)

        return all_issues

    def generate_report(self, issues: List[Dict]) -> str:
        """
        生成检查报告

        Args:
            issues: 问题列表

        Returns:
            报告文本
        """
        if not issues:
            return (
                "✅ SQL安全检查通过！\n"
                f"发现 {self.safe_count} 处使用参数化查询的安全代码。"
            )

        report_lines = [
            f"⚠️  SQL安全检查发现 {len(issues)} 个潜在问题：\n"
        ]

        # 按文件分组
        issues_by_file = {}
        for issue in issues:
            file_path = issue['file']
            if file_path not in issues_by_file:
                issues_by_file[file_path] = []
            issues_by_file[file_path].append(issue)

        for file_path, file_issues in issues_by_file.items():
            report_lines.append(f"\n📄 {file_path}:")
            for issue in file_issues:
                report_lines.append(
                    f"  行 {issue['line']}: {issue['description']}"
                )
                report_lines.append(f"    代码: {issue['code'][:80]}...")

        report_lines.append(
            f"\n✅ 发现 {self.safe_count} 处使用参数化查询的安全代码。"
        )
        report_lines.append(
            "\n💡 建议：将所有SQL语句改为使用参数化查询。"
        )

        return '\n'.join(report_lines)


def audit_sql_security(project_root: str = '.') -> str:
    """
    执行SQL安全检查并返回报告

    Args:
        project_root: 项目根目录

    Returns:
        检查报告
    """
    auditor = SQLSecurityAuditor(project_root)
    issues = auditor.scan_directory()
    return auditor.generate_report(issues)


if __name__ == '__main__':
    # 执行检查
    report = audit_sql_security()
    print(report)
