#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
运行完整的测试套件并生成报告
"""

import subprocess
import sys
from datetime import datetime

print("=" * 80)
print("物流定价系统 - 综合测试套件")
print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

# 定义测试组
test_groups = {
    "1. 统计与看板功能": [
        "tests/test_statistics_comprehensive.py",
    ],
    "2. 权限控制与计费": [
        "tests/test_permissions_and_billing.py",
    ],
    "3. 定价模式测试": [
        "tests/test_pricing_modes.py",
    ],
    "4. 备份与支付": [
        "tests/test_backup_and_payment.py",
    ],
    "5. 核心业务逻辑": [
        "tests/test_logic.py",
        "tests/test_logic_core_functions.py",
        "tests/test_logic_pricing.py",
    ],
    "6. 数据库工具": [
        "tests/test_db_utils_subscription.py",
        "tests/test_db_utils_upgrades.py",
    ],
    "7. 会话安全": [
        "tests/test_session_security.py",
    ],
}

total_passed = 0
total_failed = 0
total_errors = 0

for group_name, test_files in test_groups.items():
    print(f"\n{'=' * 80}")
    print(f"运行测试组: {group_name}")
    print(f"{'=' * 80}")

    # 过滤存在的测试文件
    existing_files = []
    for f in test_files:
        import os
        if os.path.exists(f):
            existing_files.append(f)

    if not existing_files:
        print("  ⚠️  没有找到测试文件")
        continue

    # 运行测试
    cmd = [
        sys.executable, "-m", "pytest"
    ] + existing_files + [
        "-v", "--tb=short", "-x"  # -x表示遇到第一个失败就停止
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    # 解析结果
    output = result.stdout + result.stderr

    if "passed" in output:
        # 提取通过和失败的数量
        import re
        match = re.search(r'(\d+) passed', output)
        if match:
            passed = int(match.group(1))
            total_passed += passed
            print(f"  ✅ 通过: {passed}")

        match = re.search(r'(\d+) failed', output)
        if match:
            failed = int(match.group(1))
            total_failed += failed
            print(f"  ❌ 失败: {failed}")

        match = re.search(r'(\d+) error', output)
        if match:
            errors = int(match.group(1))
            total_errors += errors
            print(f"  💥 错误: {errors}")

    print("\n测试结果详情:")
    split_out = output.split('\n')
    if len(split_out) > 15:
        print(split_out[-15:])
    else:
        print(output[-500:])

print("\n" + "=" * 80)
print("测试总结")
print("=" * 80)
print(f"✅ 通过: {total_passed}")
print(f"❌ 失败: {total_failed}")
print(f"💥 错误: {total_errors}")
print(f"总计: {total_passed + total_failed + total_errors}")

if total_failed == 0 and total_errors == 0:
    print("\n🎉 所有测试通过!")
    sys.exit(0)
else:
    print("\n⚠️  有测试失败，请检查上述详情")
    sys.exit(1)
