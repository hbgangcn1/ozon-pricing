#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
安装可选依赖
"""

import subprocess
import sys


def install_dependencies():
    """安装可选依赖"""
    print("安装可选依赖...")

    optional_deps = ['psutil']

    for dep in optional_deps:
        try:
            __import__(dep)
            print(f"✅ {dep} 已安装")
        except ImportError:
            print(f"安装 {dep}...")
            try:
                subprocess.check_call(
                    [sys.executable, '-m', 'pip', 'install', dep]
                )
                print(f"✅ {dep} 安装成功")
            except subprocess.CalledProcessError as e:
                print(f"❌ {dep} 安装失败: {e}")


if __name__ == "__main__":
    install_dependencies()
