from pathlib import Path


def test_register_daily_rebuild_task_uses_valid_runlevel():
    script_text = Path("scripts/register_daily_rebuild_task.ps1").read_text(encoding="utf-8")

    assert "-RunLevel Limited" in script_text
    assert "LeastPrivilege" not in script_text


def test_register_daily_rebuild_task_documents_interactive_logon_limit():
    script_text = Path("scripts/register_daily_rebuild_task.ps1").read_text(encoding="utf-8")
    guide_text = Path("MANUAL_TEST_GUIDE.md").read_text(encoding="utf-8")

    assert "-LogonType Interactive" in script_text
    assert "current Windows user is signed in" in script_text
    assert "Windows 用户保持登录" in guide_text
