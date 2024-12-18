import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated

from jsondiff import diff
from pydantic import Field

from dandisets_linkml_status_tools.cli import (
    ASSET_VALIDATION_REPORTS_FILE,
    DANDISET_VALIDATION_REPORTS_FILE,
)
from dandisets_linkml_status_tools.models import (
    ASSET_VALIDATION_REPORTS_ADAPTER,
    DANDISET_VALIDATION_REPORTS_ADAPTER,
    AssetValidationReportsType,
    DandiBaseReport,
    DandisetValidationReportsType,
    PydanticValidationErrsType,
)
from dandisets_linkml_status_tools.tools import (
    create_or_replace_dir,
    gen_header_and_alignment_rows,
    get_validation_reports_entries,
    read_reports,
    write_data,
)
from dandisets_linkml_status_tools.tools.md import (
    gen_diff_cell,
    gen_pydantic_validation_errs_cell,
    gen_row,
)

logger = logging.getLogger(__name__)


class _DandiValidationDiffReport(DandiBaseReport):
    """
    A base class for DANDI validation diff reports
    """

    pydantic_validation_errs1: Annotated[
        PydanticValidationErrsType, Field(default_factory=list)
    ]
    pydantic_validation_errs2: Annotated[
        PydanticValidationErrsType, Field(default_factory=list)
    ]
    pydantic_validation_errs_diff: dict | list


class _DandisetValidationDiffReport(_DandiValidationDiffReport):
    """
    A class for Dandiset validation diff reports
    """


class _AssetValidationDiffReport(_DandiValidationDiffReport):
    """
    A class for Asset validation diff reports
    """

    asset_id: str | None
    asset_path: str | None


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
    diff_reports_dir = output_dir / "diff_reports"

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

    _output_validation_diff_reports(
        _dandiset_validation_diff_reports_iter(*dandiset_validation_reports_lst),
        _asset_validation_diff_reports_iter(*asset_validation_reports_lst),
        diff_reports_dir,
    )

    logger.info("Success!")


def _dandiset_validation_diff_reports_iter(
    reports1: DandisetValidationReportsType, reports2: DandisetValidationReportsType
) -> Iterable[_DandisetValidationDiffReport]:
    """
    Get the iterator of the dandiset validation diff reports of two given collections of
    dandiset validation reports

    :param reports1: The first collection of dandiset validation reports
    :param reports2: The second collection of dandiset validation reports
    :return: The iterator of dandiset validation diff reports of the given two
        collections
    """

    # Get all entries involved in the two collections of dandiset validation reports
    entries = sorted(
        get_validation_reports_entries(reports1)
        | get_validation_reports_entries(reports2)
    )

    for id_, ver in entries:  # Each entry can be break down to dandiset ID and version
        # Get reports at the same entry from the two collections respectively
        r1 = reports1.get(id_, {}).get(ver, None)
        r2 = reports2.get(id_, {}).get(ver, None)

        # If both are None, skip this entry
        if r1 is None and r2 is None:
            continue

        pydantic_errs1 = r1.pydantic_validation_errs if r1 is not None else []
        pydantic_errs2 = r2.pydantic_validation_errs if r2 is not None else []

        # If all errs are empty, skip this entry
        if not any([pydantic_errs1, pydantic_errs2]):
            continue

        yield _DandisetValidationDiffReport(
            dandiset_identifier=id_,
            dandiset_version=ver,
            pydantic_validation_errs1=pydantic_errs1,
            pydantic_validation_errs2=pydantic_errs2,
            pydantic_validation_errs_diff=(
                diff(pydantic_errs1, pydantic_errs2, marshal=True)
            ),
        )


def _asset_validation_diff_reports_iter(
    reports1: AssetValidationReportsType, reports2: AssetValidationReportsType
) -> Iterable[_AssetValidationDiffReport]:
    """
    Get the iterator of asset validation diff reports of two given collections of asset
    validation reports

    :param reports1: The first collection of asset validation reports
    :param reports2: The second collection of asset validation reports
    :return: The iterator of asset validation diff reports of the given two collections
    """

    # Get all entries involved in the two collections of validation reports
    entries = sorted(reports1.keys() | reports2.keys())

    for entry in entries:
        # Get reports at the same entry from the two collections respectively
        r1 = reports1.get(entry)
        r2 = reports2.get(entry)

        pydantic_errs1 = r1.pydantic_validation_errs if r1 is not None else []
        pydantic_errs2 = r2.pydantic_validation_errs if r2 is not None else []

        # If all errs are empty, skip this entry
        if not any([pydantic_errs1, pydantic_errs2]):
            continue

        dandiset_id, dandiset_ver, _ = entry.parts
        yield _AssetValidationDiffReport(
            dandiset_identifier=dandiset_id,
            dandiset_version=dandiset_ver,
            asset_id=r1.asset_id,
            asset_path=r1.asset_path,
            pydantic_validation_errs1=pydantic_errs1,
            pydantic_validation_errs2=pydantic_errs2,
            pydantic_validation_errs_diff=diff(
                pydantic_errs1, pydantic_errs2, marshal=True
            ),
        )


def _output_validation_diff_reports(
    dandiset_validation_diff_reports: Iterable[_DandisetValidationDiffReport],
    asset_validation_diff_reports: Iterable[_AssetValidationDiffReport],
    output_dir: Path,
) -> None:
    """
    Output the validation diff reports

    :param dandiset_validation_diff_reports: The list of dandiset validation diff
        reports to be output
    :param asset_validation_diff_reports: The list of asset validation diff reports
        to be output
    :param output_dir: Path of the directory to write the validation diff reports to
    """
    dandiset_diff_reports_dir = output_dir / "dandiset"
    asset_diff_reports_dir = output_dir / "asset"

    logger.info("Creating validation diff report directory %s", output_dir)
    create_or_replace_dir(output_dir)

    # Output dandiset validation diff reports
    _output_dandiset_validation_diff_reports(
        dandiset_validation_diff_reports, dandiset_diff_reports_dir
    )

    # Output asset validation diff reports
    _output_asset_validation_diff_reports(
        asset_validation_diff_reports, asset_diff_reports_dir
    )


def _output_dandiset_validation_diff_reports(
    reports: Iterable[_DandisetValidationDiffReport],
    output_dir: Path,
) -> None:
    """
    Output dandiset validation diff reports

    :param reports: The list of dandiset validation diff reports to be output
    :param output_dir: Path of the directory to write the dandiset validation diff
        reports to
    """
    summary_file_name = "summary.md"

    summary_headers = [
        "dandiset",
        "version",
        "pydantic errs 1",
        "pydantic errs 2",
        "pydantic errs diff",
    ]

    logger.info("Creating dandiset validation diff report directory %s", output_dir)
    output_dir.mkdir(parents=True)

    with (output_dir / summary_file_name).open("w") as summary_f:
        # Write the header and alignment rows of the summary table
        summary_f.write(gen_header_and_alignment_rows(summary_headers))

        # Output individual dandiset validation diff reports by writing the supporting
        # files and the summary table row
        for r in reports:
            report_dir = output_dir / r.dandiset_identifier / r.dandiset_version
            report_dir.mkdir(parents=True)

            pydantic_errs1_base_fname = "pydantic_validation_errs1"
            pydantic_errs2_base_fname = "pydantic_validation_errs2"
            pydantic_errs_diff_base_fname = "pydantic_validation_errs_diff"

            for errs, base_fname in [
                (r.pydantic_validation_errs1, pydantic_errs1_base_fname),
                (r.pydantic_validation_errs2, pydantic_errs2_base_fname),
            ]:
                if errs:
                    write_data(errs, report_dir, base_fname)

            if r.pydantic_validation_errs_diff:
                write_data(
                    r.pydantic_validation_errs_diff,
                    report_dir,
                    pydantic_errs_diff_base_fname,
                )

            logger.info(
                "Wrote dandiset %s validation diff report supporting files to %s",
                r.dandiset_identifier,
                report_dir,
            )

            # === Write the summary table row for the validation diff report ===
            # Directory for storing all validation diff reports of the dandiset
            dandiset_dir = f"./{r.dandiset_identifier}"
            # Directory for storing all validation diff reports of the dandiset
            # at a particular version
            version_dir = f"{dandiset_dir}/{r.dandiset_version}"

            row_cells = (
                f" {c} "  # Add spaces around the cell content for better readability
                for c in [
                    # For the dandiset column
                    f"[{r.dandiset_identifier}]({dandiset_dir}/)",
                    # For the version column
                    f"[{r.dandiset_version}]({version_dir}/)",
                    # For the pydantic errs 1 column
                    gen_pydantic_validation_errs_cell(
                        r.pydantic_validation_errs1,
                        f"{version_dir}/{pydantic_errs1_base_fname}.json",
                    ),
                    # For the pydantic errs 2 column
                    gen_pydantic_validation_errs_cell(
                        r.pydantic_validation_errs2,
                        f"{version_dir}/{pydantic_errs2_base_fname}.json",
                    ),
                    # For the pydantic errs diff column
                    gen_diff_cell(
                        r.pydantic_validation_errs_diff,
                        f"{version_dir}/{pydantic_errs_diff_base_fname}.json",
                    ),
                ]
            )
            summary_f.write(gen_row(row_cells))

    logger.info("Output of dandiset validation diff reports is complete")


def _output_asset_validation_diff_reports(
    reports: Iterable[_AssetValidationDiffReport],
    output_dir: Path,
) -> None:
    """
    todo: more here
    :param reports:
    :param output_dir:
    :return:
    """
