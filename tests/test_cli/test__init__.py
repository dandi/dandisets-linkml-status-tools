import pytest
from typer.testing import CliRunner

from dandisets_linkml_status_tools.cli import app

runner = CliRunner()


@pytest.mark.skip(
    reason="This test currently takes too long. It should be re-enabled "
    "when there is an option in the app to limit the number of "
    "dandisets to validate."
)
def test_smoke_cli(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app)
    assert result.exit_code == 0
