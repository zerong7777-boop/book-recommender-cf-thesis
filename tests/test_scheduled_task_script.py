from pathlib import Path


def test_register_daily_rebuild_task_uses_valid_runlevel():
    script_text = Path("scripts/register_daily_rebuild_task.ps1").read_text(encoding="utf-8")

    assert "-RunLevel Limited" in script_text
    assert "LeastPrivilege" not in script_text
