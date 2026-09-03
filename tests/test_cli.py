from typer.testing import CliRunner
from hive.cli import app

runner = CliRunner()

def test_help():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "hive" in r.output.lower()

def test_doctor():
    r = runner.invoke(app, ["doctor"])
    assert r.exit_code == 0

def test_version():
    r = runner.invoke(app, ["--version"])
    assert r.exit_code == 0

def test_config_show():
    r = runner.invoke(app, ["config", "--show"])
    assert r.exit_code == 0
    assert "ollama" in r.output.lower()
