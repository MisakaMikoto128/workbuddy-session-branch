#!/usr/bin/env python3
"""打印当前 git tag 版本号，供发布脚本读取。版本号唯一来源 = git tag。"""

import subprocess
import sys


def git(*args):
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return ""


version = git("tag", "--points-at", "HEAD") or git("describe", "--tags", "--abbrev=0")
if version:
    sys.stdout.write(version.splitlines()[0])
