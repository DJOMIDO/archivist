from typer.testing import CliRunner

from archivist.cli import app

runner = CliRunner()


def test_config_command_prints_settings():
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "chat_model" in result.output


def test_config_command_reflects_env_override(monkeypatch):
    monkeypatch.setenv("ARCHIVIST_CHAT_MODEL", "my-test-model")
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "chat_model = my-test-model" in result.output
