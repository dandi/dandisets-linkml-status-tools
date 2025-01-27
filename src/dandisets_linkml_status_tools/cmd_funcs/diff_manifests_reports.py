import logging
from collections.abc import Iterable
from itertools import chain
from pathlib import Path
from typing import Annotated, Any, cast

from jsondiff import diff
from pydantic import Field

from dandisets_linkml_status_tools.cli import (
    ASSET_VALIDATION_REPORTS_FILE,
    DANDISET_VALIDATION_REPORTS_FILE,
)
from dandisets_linkml_status_tools.models import (
    ASSET_VALIDATION_REPORTS_ADAPTER,
    DANDISET_VALIDATION_REPORTS_ADAPTER,
    AssetValidationReport,
    AssetValidationReportsType,
    DandiBaseReport,
    DandisetValidationReport,
    DandisetValidationReportsType,
    JsonschemaValidationErrorModel,
    PydanticValidationErrsType,
    ValidationReportsType,
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
    pydantic_validation_err_diff_summary,
)
from dandisets_linkml_status_tools.tools.validation_err_counter import (
    ValidationErrCounter,
)

logger = logging.getLogger(__name__)


class _DandiValidationDiffReport(DandiBaseReport):
    """
    A base class for DANDI validation diff reports
    """

    # Pydantic validation errors and their diff
    pydantic_validation_errs1: Annotated[
        PydanticValidationErrsType, Field(default_factory=list)
    ]
    pydantic_validation_errs2: Annotated[
        PydanticValidationErrsType, Field(default_factory=list)
    ]
    pydantic_validation_errs_diff: dict | list

    # jsonschema validation errors and their diff
    jsonschema_validation_errs1: Annotated[
        list[JsonschemaValidationErrorModel], Field(default_factory=list)
    ]
    jsonschema_validation_errs2: Annotated[
        list[JsonschemaValidationErrorModel], Field(default_factory=list)
    ]
    jsonschema_validation_errs_diff: dict | list


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

    # The index of the asset in the containing JSON array in `assets.jsonld`
    asset_idx: int


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
        _dandiset_validation_diff_reports(*dandiset_validation_reports_lst),
        _asset_validation_diff_reports(*asset_validation_reports_lst),
        diff_reports_dir,
    )

    logger.info("Success!")


def _dandiset_validation_diff_reports(
    reports1: DandisetValidationReportsType, reports2: DandisetValidationReportsType
) -> list[_DandisetValidationDiffReport]:
    """
    Get the list of the dandiset validation diff reports of two given collections of
    dandiset validation reports

    :param reports1: The first collection of dandiset validation reports
    :param reports2: The second collection of dandiset validation reports
    :return: The list of dandiset validation diff reports of the given two
        collections
    """

    # Get all entries involved in the two collections of dandiset validation reports
    entries = sorted(
        get_validation_reports_entries(reports1)
        | get_validation_reports_entries(reports2)
    )

    # The list of dandiset validation diff reports to be returned
    rs = []
    for id_, ver in entries:  # Each entry can be break down to dandiset ID and version
        # Get reports at the same entry from the two collections respectively
        r1 = reports1.get(id_, {}).get(ver, None)
        r2 = reports2.get(id_, {}).get(ver, None)

        if r1 is not None:
            pydantic_errs1 = r1.pydantic_validation_errs
            jsonschema_errs1 = r1.jsonschema_validation_errs
        else:
            pydantic_errs1 = []
            jsonschema_errs1 = []

        if r2 is not None:
            pydantic_errs2 = r2.pydantic_validation_errs
            jsonschema_errs2 = r2.jsonschema_validation_errs
        else:
            pydantic_errs2 = []
            jsonschema_errs2 = []

        # If all errs are empty, skip this entry
        if not any(
            (pydantic_errs1, pydantic_errs2, jsonschema_errs1, jsonschema_errs2)
        ):
            continue

        rs.append(
            _DandisetValidationDiffReport(
                dandiset_identifier=id_,
                dandiset_version=ver,
                pydantic_validation_errs1=pydantic_errs1,
                pydantic_validation_errs2=pydantic_errs2,
                pydantic_validation_errs_diff=diff(
                    pydantic_errs1, pydantic_errs2, marshal=True
                ),
                jsonschema_validation_errs1=jsonschema_errs1,
                jsonschema_validation_errs2=jsonschema_errs2,
                jsonschema_validation_errs_diff=diff(
                    [e.model_dump(mode="json") for e in jsonschema_errs1],
                    [e.model_dump(mode="json") for e in jsonschema_errs2],
                    marshal=True,
                ),
            )
        )

    return rs


def _asset_validation_diff_reports(
    reports1: AssetValidationReportsType, reports2: AssetValidationReportsType
) -> list[_AssetValidationDiffReport]:
    """
    Get the list of asset validation diff reports of two given collections of asset
    validation reports

    :param reports1: The first collection of asset validation reports
    :param reports2: The second collection of asset validation reports
    :return: The list of asset validation diff reports of the given two collections
    """
    rs1 = _key_reports(reports1)
    rs2 = _key_reports(reports2)

    # Get all entries involved in the two collections of validation reports
    entries = sorted(rs1.keys() | rs2.keys())

    # The list of asset validation diff reports to be returned
    rs = []
    for entry in entries:
        # Get reports at the same entry from the two collections respectively
        r1 = rs1.get(entry)
        r2 = rs2.get(entry)

        if r1 is not None:
            pydantic_errs1 = r1.pydantic_validation_errs
            jsonschema_errs1 = r1.jsonschema_validation_errs
        else:
            pydantic_errs1 = []
            jsonschema_errs1 = []

        if r2 is not None:
            pydantic_errs2 = r2.pydantic_validation_errs
            jsonschema_errs2 = r2.jsonschema_validation_errs
        else:
            pydantic_errs2 = []
            jsonschema_errs2 = []

        # If all errs are empty, skip this entry
        if not any(
            (pydantic_errs1, pydantic_errs2, jsonschema_errs1, jsonschema_errs2)
        ):
            continue

        asset_id = r1.asset_id if r1 is not None else r2.asset_id
        asset_path = r1.asset_path if r1 is not None else r2.asset_path

        dandiset_id, dandiset_ver, asset_idx_str = entry.parts
        rs.append(
            _AssetValidationDiffReport(
                dandiset_identifier=dandiset_id,
                dandiset_version=dandiset_ver,
                asset_id=asset_id,
                asset_path=asset_path,
                asset_idx=int(asset_idx_str),
                pydantic_validation_errs1=pydantic_errs1,
                pydantic_validation_errs2=pydantic_errs2,
                pydantic_validation_errs_diff=diff(
                    pydantic_errs1, pydantic_errs2, marshal=True
                ),
                jsonschema_validation_errs1=jsonschema_errs1,
                jsonschema_validation_errs2=jsonschema_errs2,
                jsonschema_validation_errs_diff=diff(
                    [e.model_dump(mode="json") for e in jsonschema_errs1],
                    [e.model_dump(mode="json") for e in jsonschema_errs2],
                    marshal=True,
                ),
            )
        )

    return rs


def _key_reports(
    reports: ValidationReportsType,
) -> dict[Path, DandisetValidationReport | AssetValidationReport]:
    """
    Key each validation report in a given collection by the path of the corresponding
    metadata instance consisting of the dandiset ID, version, and, in the case of a
    `AssetValidationReport`, the index of the corresponding asset in the containing JSON
    array in `assets.jsonld`

    :param reports: The given collection of validation reports to be keyed
    :return: The collection of validation reports keyed by the corresponding paths as
        a dictionary
    :raises ValueError: If the given collection of reports contains a report that is not
        an instance of `DandisetValidationReport` or `AssetValidationReport`
    """
    if reports:
        r0 = reports[0]
        if isinstance(r0, DandisetValidationReport):
            parts = ["dandiset_identifier", "dandiset_version"]
        elif isinstance(r0, AssetValidationReport):
            parts = ["dandiset_identifier", "dandiset_version", "asset_idx"]
        else:
            msg = f"Unsupported report type: {type(r0)}"
            raise ValueError(msg)

        return {Path(*(str(getattr(r, p)) for p in parts)): r for r in reports}

    return {}


def _output_validation_diff_reports(
    dandiset_validation_diff_reports: list[_DandisetValidationDiffReport],
    asset_validation_diff_reports: list[_AssetValidationDiffReport],
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
    reports: list[_DandisetValidationDiffReport],
    output_dir: Path,
) -> None:
    """
    Output dandiset validation diff reports

    :param reports: The reports to be output
    :param output_dir: Path of the directory to write the reports to
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

    err1_rep_lsts: list[list[tuple[str, str, tuple[str | int, ...], Path]]] = []
    err2_rep_lsts: list[list[tuple[str, str, tuple[str | int, ...], Path]]] = []
    for r in reports:
        p = Path(r.dandiset_identifier, r.dandiset_version)

        # Tuple representation of the Pydantic validation errors
        err1_rep_lsts.append(
            [pydantic_err_rep(e, p) for e in r.pydantic_validation_errs1]
        )
        err2_rep_lsts.append(
            [pydantic_err_rep(e, p) for e in r.pydantic_validation_errs2]
        )

    pydantic_validation_errs1_ctr = ValidationErrCounter(pydantic_err_categorizer)
    pydantic_validation_errs2_ctr = ValidationErrCounter(pydantic_err_categorizer)

    pydantic_validation_errs1_ctr.count(chain.from_iterable(err1_rep_lsts))
    pydantic_validation_errs2_ctr.count(chain.from_iterable(err2_rep_lsts))

    with (output_dir / summary_file_name).open("w") as summary_f:
        # Write the summary of the Pydantic validation error differences
        summary_f.write(
            pydantic_validation_err_diff_summary(
                pydantic_validation_errs1_ctr, pydantic_validation_errs2_ctr
            )
        )

        # Write the header and alignment rows of the summary table
        summary_f.write("\n")
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
    reports: list[_AssetValidationDiffReport],
    output_dir: Path,
) -> None:
    """
    Output asset validation diff reports

    :param reports: The reports to be output
    :param output_dir: Path of the directory to write the reports to
    """
    summary_file_name = "summary.md"

    output_dir.mkdir(parents=True)
    logger.info("Created asset validation diff report directory %s", output_dir)

    err1_rep_lsts: list[list[tuple[str, str, tuple[str | int, ...], Path]]] = []
    err2_rep_lsts: list[list[tuple[str, str, tuple[str | int, ...], Path]]] = []
    for r in reports:
        p = Path(r.dandiset_identifier, r.dandiset_version, str(r.asset_idx))

        # Tuple representation of the Pydantic validation errors
        err1_rep_lsts.append(
            [pydantic_err_rep(e, p) for e in r.pydantic_validation_errs1]
        )
        err2_rep_lsts.append(
            [pydantic_err_rep(e, p) for e in r.pydantic_validation_errs2]
        )

    pydantic_validation_errs1_ctr = ValidationErrCounter(pydantic_err_categorizer)
    pydantic_validation_errs2_ctr = ValidationErrCounter(pydantic_err_categorizer)

    pydantic_validation_errs1_ctr.count(chain.from_iterable(err1_rep_lsts))
    pydantic_validation_errs2_ctr.count(chain.from_iterable(err2_rep_lsts))

    with (output_dir / summary_file_name).open("w") as summary_f:
        # Write the summary of the Pydantic validation error differences
        summary_f.write(
            pydantic_validation_err_diff_summary(
                pydantic_validation_errs1_ctr, pydantic_validation_errs2_ctr
            )
        )

        # Output individual asset validation diff reports by writing the constituting
        # files
        for r in reports:
            report_dir = (
                output_dir
                / r.dandiset_identifier
                / r.dandiset_version
                / str(r.asset_idx)
            )
            report_dir.mkdir(parents=True)

            pydantic_errs1_base_fname = "pydantic_validation_errs1"
            pydantic_errs2_base_fname = "pydantic_validation_errs2"
            pydantic_errs_diff_base_fname = "pydantic_validation_errs_diff"

            for data, base_fname in [
                (r.pydantic_validation_errs1, pydantic_errs1_base_fname),
                (r.pydantic_validation_errs2, pydantic_errs2_base_fname),
                (r.pydantic_validation_errs_diff, pydantic_errs_diff_base_fname),
            ]:
                if data:
                    write_data(data, report_dir, base_fname)

            logger.info(
                "Dandiset %s:%s - asset %sat index %d: "
                "Wrote asset validation diff report constituting files to %s",
                r.dandiset_identifier,
                r.dandiset_version,
                f"{r.asset_id} " if r.asset_id else "",
                r.asset_idx,
                report_dir,
            )

    logger.info("Output of asset validation diff reports is complete")


def pydantic_err_categorizer(
    err: tuple[str, str, tuple[str | int, ...], Path]
) -> tuple[str, str, tuple[str, ...]]:
    """
    Categorize a Pydantic validation error represented as a tuple using the same
    tuple without the path component to the dandiset at a particular version and
    with a generalized "loc" with all array indices replaced by "[*]"

    :param err: The tuple representing the Pydantic validation error
    :return: The tuple representing the category that the error belongs to
    """
    type_, msg = err[0], err[1]

    # Generalize the "loc" by replacing all array indices with "[*]"
    loc = cast(
        tuple[str, ...], tuple("[*]" if isinstance(v, int) else v for v in err[2])
    )

    return type_, msg, loc


def pydantic_err_rep(
    err: dict[str, Any], path: Path
) -> tuple[str, str, tuple[str | int, ...], Path]:
    """
    Get a representation of a Pydantic validation error as a tuple

    :param err: The Pydantic validation error as a `dict`
    :param path: The path the data instance that the error pertained to
    :return: The representation of the Pydantic validation error as tuple consisting of
        the values for the `'type'`, `'msg'`, `'loc'` keys of the error and `path`.
        Note: The value of the `'loc'` key is converted to a tuple from a list
    """
    return err["type"], err["msg"], tuple(err["loc"]), path


def count_pydantic_validation_errs(
    err_reps: Iterable[tuple[str, str, tuple[str | int, ...], Path]]
) -> ValidationErrCounter:
    """
    Pydantic validation errors provided by an iterable

    :param err_reps: The iterable of Pydantic validation errors represented as tuples
        defined by the output of `pydantic_err_rep`
    :return: A `ValidationErrCounter` object representing the counts
    """
    ctr = ValidationErrCounter(pydantic_err_categorizer)
    ctr.count(err_reps)

    return ctr
