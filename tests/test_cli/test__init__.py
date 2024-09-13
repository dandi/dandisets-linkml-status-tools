import pytest
from typer.testing import CliRunner

from dandisets_linkml_status_tools.cli import app

runner = CliRunner()


@pytest.mark.skip(
    reason="This test currently takes too long. It should be re-enabled "
    "when there is an option in the app to limit the number of "
    "dandisets to validate."
)
def test_smoke_cli(tmp_path):
    validation_report_file_path = tmp_path / "validation_reports.json"
    result = runner.invoke(app, ["--output-file", str(validation_report_file_path)])
    assert result.exit_code == 0
