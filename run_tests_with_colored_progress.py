#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试运行脚本 - 彩色进度显示
"""
import sys
import subprocess
import os
import re
from typing import Tuple

# ANSI颜色代码
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def colorize(text: str, color: str) -> str:
    """添加颜色"""
    return f"{color}{text}{Colors.RESET}"

def parse_pytest_output(line: str) -> Tuple[str, str]:
    """解析pytest输出行，返回状态和颜色"""
    line_lower = line.lower()
    
    # 成功标识
    if re.search(r'PASSED|✓|\.', line) and 'FAILED' not in line:
        return line, Colors.GREEN
    
    # 失败标识
    if re.search(r'FAILED|✗|ERROR|FAILURE', line):
        return line, Colors.RED
    
    # 警告标识
    if re.search(r'WARNING|WARN|SKIPPED|XPASS', line):
        return line, Colors.YELLOW
    
    # 进度信息
    if re.search(r'collected|test session starts|running', line):
        return line, Colors.CYAN
    
    # 覆盖率信息
    if 'coverage' in line_lower or '%' in line:
        if '100%' in line or 'TOTAL' in line.upper():
            return line, Colors.GREEN
        elif any(x in line for x in ['80%', '90%', '95%']):
            return line, Colors.CYAN
        else:
            return line, Colors.YELLOW
    
    # 默认颜色
    return line, Colors.WHITE

def main():
    """运行测试并显示彩色进度"""
    # 确保在项目根目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 构建pytest命令
    # 使用 --cov=. 来测量所有模块，但排除测试文件和不需要的文件
    cmd = [
        sys.executable, '-m', 'pytest',
        '-vv',                   # 详细输出（显示每个测试）
        '--tb=short',            # 简短回溯
        '--durations=10',        # 显示最慢的10个测试
        '-ra',                   # 显示所有测试结果摘要
        '--color=yes',           # 启用颜色
        '-s',                    # 禁用输出捕获，实时显示
        '--capture=no',          # 禁用输出捕获（与-s相同，但更明确）
        '--disable-warnings',    # 禁用pytest的警告显示（我们会在脚本中过滤）
        '--cov=.',               # 覆盖率：测量所有模块
        '--cov-config=.coveragerc',  # 使用.coveragerc配置
        '--cov-report=term:skip-covered', # 终端覆盖率报告（跳过已覆盖）
        '--cov-report=xml:coverage.xml',  # XML覆盖率报告
        '--cov-report=html:htmlcov',      # HTML覆盖率报告
        '-W', 'ignore::UserWarning',  # 忽略用户警告
        '-W', 'ignore::DeprecationWarning',  # 忽略弃用警告
        'tests/',                # 测试目录
    ]
    
    print("=" * 80)
    print(colorize("运行单元测试套件（彩色进度显示）", Colors.BOLD + Colors.CYAN))
    print("=" * 80)
    print()
    
    # 运行测试并实时显示输出
    # 在Windows上，使用unbuffered模式确保实时输出
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=0,  # 无缓冲模式
        universal_newlines=True,
        env=env
    )
    
    # 实时输出带颜色的结果
    failed_tests = []
    passed_tests = []
    warnings = []
    skipped_tests = []
    test_count = 0
    
    # 用于从pytest最终汇总行解析准确的统计数据
    final_passed = None
    final_failed = None
    final_skipped = None
    
    if process.stdout is not None:
        import sys as sys_module
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            
            # 移除行尾换行符，但保留内容
            line_stripped = line.rstrip('\n\r')
            if not line_stripped:
                continue
            
            # 实时刷新输出
            sys_module.stdout.flush()
            
            # 过滤Streamlit警告（这些是预期的，不需要显示）
            if any(warn in line_stripped for warn in [
                'streamlit.runtime.caching.cache_data_api',
                'No runtime found',
                'missing ScriptRunContext',
                'Session state does not function'
            ]):
                continue  # 跳过这些警告
            
            # 检测测试进度 - 匹配pytest的输出格式
            # 格式1: tests/test_file.py::TestClass::test_method PASSED [ 10%]
            # 格式2: tests/test_file.py::test_function PASSED
            test_result_match = re.search(
                r'(tests/[^\s:]+(?:::[^\s:]+)*::[^\s\[\]]+)\s+(PASSED|FAILED|SKIPPED|ERROR)',
                line
            )
            
            if test_result_match:
                test_count += 1
                test_name = test_result_match.group(1)
                test_status = test_result_match.group(2)
                
                # 显示进度（带百分比）
                # 注意：测试总数会在运行时动态获取，这里使用一个合理的默认值
                # 实际百分比可能不准确，但进度信息仍然有用
                total_tests = 2283  # 当前测试总数
                percent = int((test_count / total_tests) * 100) if test_count > 0 else 0
                progress_info = f"[{test_count}/{total_tests} ({percent}%)] {test_name} {test_status}"
                
                if test_status == 'PASSED':
                    print(colorize(progress_info, Colors.GREEN))
                    passed_tests.append(test_name)
                elif test_status in ('FAILED', 'ERROR'):
                    print(colorize(progress_info, Colors.RED))
                    failed_tests.append(test_name)
                elif test_status == 'SKIPPED':
                    print(colorize(progress_info, Colors.YELLOW))
                    skipped_tests.append(test_name)
            elif 'PASSED' in line or 'FAILED' in line or 'SKIPPED' in line:
                # 备用匹配：如果上面的正则没匹配到，尝试简单匹配
                test_count += 1
                test_match = re.search(r'tests/[^\s:]+::[^\s:]+::[^\s\[\]]+', line)
                if test_match:
                    test_name = test_match.group(0)
                    total_tests = 2283  # 当前测试总数
                    percent = int((test_count / total_tests) * 100) if test_count > 0 else 0
                    progress_info = f"[{test_count}/{total_tests} ({percent}%)] {test_name}"
                    if 'PASSED' in line:
                        print(colorize(progress_info, Colors.GREEN))
                        passed_tests.append(test_name)
                    elif 'FAILED' in line or 'ERROR' in line:
                        print(colorize(progress_info, Colors.RED))
                        failed_tests.append(test_name)
                    elif 'SKIPPED' in line:
                        print(colorize(progress_info, Colors.YELLOW))
                        skipped_tests.append(test_name)
                else:
                    # 如果没有匹配到测试名，使用原始行
                    colored_line, color = parse_pytest_output(line_stripped)
                    print(colorize(colored_line, color))
            else:
                # 其他输出（覆盖率、摘要等）
                # 只显示重要的输出，过滤掉噪音
                if any(skip in line_stripped for skip in [
                    'WARNING streamlit',
                    'No runtime found',
                    'missing ScriptRunContext',
                    'Session state does not function',
                    'using MemoryCacheStorageManager'
                ]):
                    continue  # 跳过这些输出
                
                # 显示重要的信息（覆盖率、摘要、错误等）
                if any(important in line_stripped for important in [
                    'collected',
                    'TOTAL',
                    'Coverage',
                    'FAILED',
                    'ERROR',
                    'passed',
                    'failed',
                    'skipped',
                    'slowest',
                    'test session'
                ]):
                    colored_line, color = parse_pytest_output(line_stripped)
                    print(colorize(colored_line, color))
                    
                    # 解析pytest的最终汇总行，格式如：
                    # "================= 4 failed, 2279 passed in 597.70s =================="
                    # 或 "4 failed, 2279 passed, 5 skipped in 595.86s (0:09:55)"
                    # 匹配格式：数字 + failed + 逗号/空格 + 数字 + passed
                    if 'failed' in line_stripped and 'passed' in line_stripped:
                        # 尝试多种匹配模式
                        # 模式1: "4 failed, 2279 passed"
                        summary_match = re.search(
                            r'(\d+)\s+failed[,\s]+(\d+)\s+passed',
                            line_stripped
                        )
                        if summary_match:
                            final_failed = int(summary_match.group(1))
                            final_passed = int(summary_match.group(2))
                        else:
                            # 模式2: "2279 passed, 4 failed" (顺序相反)
                            alt_match = re.search(
                                r'(\d+)\s+passed[,\s]+(\d+)\s+failed',
                                line_stripped
                            )
                            if alt_match:
                                final_passed = int(alt_match.group(1))
                                final_failed = int(alt_match.group(2))
                            else:
                                # 模式3: 更宽松的匹配，提取所有数字和对应的状态
                                numbers = re.findall(r'(\d+)\s+(failed|passed|skipped)', line_stripped)
                                for num_str, status in numbers:
                                    num = int(num_str)
                                    if status == 'failed':
                                        final_failed = num
                                    elif status == 'passed':
                                        final_passed = num
                                    elif status == 'skipped':
                                        final_skipped = num
                        
                        # 尝试匹配skipped（可能在任意位置）
                        if final_skipped is None:
                            skipped_match = re.search(r'(\d+)\s+skipped', line_stripped)
                            if skipped_match:
                                final_skipped = int(skipped_match.group(1))
            
            # 收集统计信息（排除Streamlit警告和预期的业务警告）
            if 'WARNING' in line or 'WARN' in line:
                # 排除Streamlit警告和预期的业务警告
                if not any(exclude in line_stripped for exclude in [
                    'streamlit',
                    'No runtime found',
                    'missing ScriptRunContext',
                    '限流告警',  # 这是预期的测试行为
                    '会话User-Agent不匹配',  # 这是预期的测试行为
                    'IP检查失败',  # 这是预期的测试行为
                    '自动备份已在运行中'  # 这是预期的测试行为
                ]):
                    warnings.append(line_stripped)
    
    # 等待进程结束
    returncode = process.wait()
    
    print()
    print("=" * 80)
    print(colorize("测试结果汇总", Colors.BOLD + Colors.CYAN))
    print("=" * 80)
    
    # 优先使用从pytest最终汇总行解析的准确数据
    # 如果解析失败，则使用通过正则匹配统计的数据
    if final_passed is not None:
        print(f"\n{colorize('✅ 通过', Colors.GREEN)}: {final_passed} 个测试")
    else:
        print(f"\n{colorize('✅ 通过', Colors.GREEN)}: {len(passed_tests)} 个测试")
    
    if final_failed is not None:
        if final_failed > 0:
            print(f"{colorize('❌ 失败', Colors.RED)}: {final_failed} 个测试")
    else:
        if failed_tests:
            print(f"{colorize('❌ 失败', Colors.RED)}: {len(failed_tests)} 个测试")
    
    if final_skipped is not None:
        if final_skipped > 0:
            print(f"{colorize('⏭️  跳过', Colors.YELLOW)}: {final_skipped} 个测试")
    else:
        if skipped_tests:
            print(f"{colorize('⏭️  跳过', Colors.YELLOW)}: {len(skipped_tests)} 个测试")
    
    if warnings:
        print(f"{colorize('⚠️  警告', Colors.YELLOW)}: {len(warnings)} 个警告")
        for warning_msg in warnings:
            print(f"   - {warning_msg}")
    
    if returncode == 0:
        print(f"\n{colorize('✅ 所有测试通过！', Colors.BOLD + Colors.GREEN)}")
    else:
        print(f"\n{colorize('❌ 测试失败，退出码: ' + str(returncode), Colors.BOLD + Colors.RED)}")
    
    print("=" * 80)
    
    return returncode

if __name__ == '__main__':
    sys.exit(main())

