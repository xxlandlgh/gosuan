from __future__ import annotations

import subprocess
import sys


def test_python_m_gosuan_cli_outputs_human_text():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gosuan.cli",
            "bazi",
            "--name",
            "测试",
            "--gender",
            "male",
            "--birth",
            "1995-08-17 14:30",
            "--tz",
            "Asia/Shanghai",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "八字命盘" in result.stdout
