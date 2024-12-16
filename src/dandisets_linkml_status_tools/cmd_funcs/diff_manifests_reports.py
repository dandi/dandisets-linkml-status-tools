import logging
from pathlib import Path

from dandisets_linkml_status_tools.cli import (
    ASSET_VALIDATION_REPORTS_FILE,
    DANDISET_VALIDATION_REPORTS_FILE,
)
from dandisets_linkml_status_tools.models import (
    ASSET_VALIDATION_REPORTS_ADAPTER,
    DANDISET_VALIDATION_REPORTS_ADAPTER,
    AssetValidationReportsType,
    DandisetValidationReportsType,
)
from dandisets_linkml_status_tools.tools import read_reports

logger = logging.getLogger(__name__)


def diff_manifests_reports(
    reports_dir1: Path, reports_dir2: Path, output_dir: Path
) -> None:
    """
    Generate a report of differences between two sets of reports on the same manifests

    :param reports_dir1: Path of the directory containing the first set of reports
        for contrast
    :param reports_dir2: Path of the directory containing the second set of reports
        for contrast
    :param output_dir: Path of the directory to write the report of differences to
    """
    reports_dirs = [reports_dir1, reports_dir2]

    dandiset_validation_reports_lst: list[DandisetValidationReportsType] = []
    asset_validation_reports_lst: list[AssetValidationReportsType] = []
    for dir_ in reports_dirs:
        dandiset_validation_reports_file: Path = dir_ / DANDISET_VALIDATION_REPORTS_FILE
        asset_validation_reports_file: Path = dir_ / ASSET_VALIDATION_REPORTS_FILE

        for f in [
            dandiset_validation_reports_file,
            asset_validation_reports_file,
        ]:
            if not f.is_file():
                raise RuntimeError(f"There is no file at {f}")

        # Load and store dandiset validation reports
        dandiset_validation_reports_lst.append(
            read_reports(
                dandiset_validation_reports_file,
                DANDISET_VALIDATION_REPORTS_ADAPTER,
            )
        )

        # Load and store asset validation reports
        asset_validation_reports_lst.append(
            read_reports(
                asset_validation_reports_file, ASSET_VALIDATION_REPORTS_ADAPTER
            )
        )