import logging
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from dandi.dandiapi import DandiAPIClient
from dandischema.models import Asset, Dandiset, PublishedAsset, PublishedDandiset
from pydantic import ValidationError
from pydantic2linkml.cli.tools import LogLevel

from dandisets_linkml_status_tools.models import (
    ASSET_VALIDATION_REPORTS_ADAPTER,
    DANDI_METADATA_LIST_ADAPTER,
    DANDISET_VALIDATION_REPORTS_ADAPTER,
    AssetValidationReport,
    AssetValidationReportsType,
    Config,
    DandiMetadata,
    DandisetValidationReport,
    DandisetValidationReportsType,
)
from dandisets_linkml_status_tools.tools import (
    compile_dandiset_linkml_translation_report,
    create_or_replace_dir,
    get_direct_subdirs,
    output_reports,
    pydantic_validate,
    write_reports,
)

if TYPE_CHECKING:
    from dandisets_linkml_status_tools.models import DandisetLinkmlTranslationReport

logger = logging.getLogger(__name__)

# Configuration settings for this app (to be initialized in the main function)
config: Config

app = typer.Typer()


@app.callback()
def main(
    output_dir_path: Annotated[
        Path,
        typer.Option("--output-dir-path", "-o", help="Path of the output directory"),
    ] = Path("reports"),
    log_level: Annotated[
        LogLevel, typer.Option("--log-level", "-l")
    ] = LogLevel.WARNING,
):
    """
    Commands for generating various reports on DANDI metadata
    """
    # Store configuration settings for this app
    global config
    config = Config(output_dir_path=output_dir_path, log_level=log_level)

    # Set log level of the CLI
    logging.basicConfig(
        format="[%(asctime)s]%(levelname)s:%(name)s:%(message)s",
        level=getattr(logging, log_level),
    )


@app.command()
def linkml_translation(
    *,
    include_unpublished: Annotated[
        bool, typer.Option("--include-unpublished", "-u")
    ] = False,
    dandi_instance: Annotated[
        str,
        typer.Option(
            "--dandi-instance",
            "-i",
            help="The DANDI server instance from which the dandiset metadata are "
            "downloaded",
        ),
    ] = "dandi",
):
    """
    Generate reports of DANDI model translation from Pydantic to LinkML with a summary
    """
    output_path = config["output_dir_path"] / "linkml_translation" / dandi_instance

    validation_reports: list[DandisetLinkmlTranslationReport] = []

    with DandiAPIClient.for_dandi_instance(dandi_instance) as client:
        # Generate validation reports for danidsets
        for dandiset in client.get_dandisets(draft=include_unpublished, order="id"):
            dandiset_id = dandiset.identifier
            logger.info("Processing dandiset %s", dandiset_id)

            most_recent_published_version = dandiset.most_recent_published_version

            if most_recent_published_version is not None:
                # === The dandiset has been published ===
                # Get the draft version
                dandiset_draft = dandiset.for_version(dandiset.draft_version)

                # Get the latest published version
                dandiset_latest = dandiset.for_version(most_recent_published_version)

                # Handle the latest published version
                report_on_latest = compile_dandiset_linkml_translation_report(
                    dandiset_latest, is_dandiset_published=True
                )
                validation_reports.append(report_on_latest)
            else:
                # === The dandiset has never been published ===
                # === Only a draft version is available ===
                dandiset_draft = dandiset

            # Handle the draft version
            report_on_draft = compile_dandiset_linkml_translation_report(
                dandiset_draft, is_dandiset_published=False
            )
            validation_reports.append(report_on_draft)

    output_reports(validation_reports, output_path)

    logger.info("Success!")


# Subdirectory for reports on manifests
MANIFESTS_REPORTS_SUBDIR = Path("manifests")

# metadata file names
DANDISET_FILE_NAME = "dandiset.jsonld"  # File with dandiset metadata
ASSETS_FILE_NAME = "assets.jsonld"  # File with assets metadata

DANDISET_VALIDATION_REPORTS_FILE_NAME = "dandiset_validation_reports.json"
ASSET_VALIDATION_REPORTS_FILE_NAME = "asset_validation_reports.json"

# Relative path to the dandiset validation reports file
DANDISET_VALIDATION_REPORTS_FILE: Path = (
    MANIFESTS_REPORTS_SUBDIR / DANDISET_VALIDATION_REPORTS_FILE_NAME
)
# Relative path to the asset validation reports file
ASSET_VALIDATION_REPORTS_FILE: Path = (
    MANIFESTS_REPORTS_SUBDIR / ASSET_VALIDATION_REPORTS_FILE_NAME
)


@app.command()
def manifests(
    *,
    manifest_path: Annotated[
        Path, typer.Argument(help="Path of the directory containing dandiset manifests")
    ],
):
    """
    Generate reports of validations of metadata in dandiset manifests
    """

    # Directory and file paths for reports
    output_dir: Path = config["output_dir_path"]
    reports_dir_path = output_dir / MANIFESTS_REPORTS_SUBDIR
    dandiset_validation_reports_file_path = (
        output_dir / DANDISET_VALIDATION_REPORTS_FILE
    )
    asset_validation_reports_file_path = output_dir / ASSET_VALIDATION_REPORTS_FILE

    def add_dandiset_validation_report_if_err() -> None:
        """
        Add a `DandisetValidationReport` object to `dandiset_validation_reports`
        if the current dandiset version directory contains a dandiset metadata file
        and a validation of the dandiset metadata produces an error.

        Note: A validation report is only added if the dandiset metadata fails
            validation
        """
        dandiset_metadata_file_path = version_dir / DANDISET_FILE_NAME

        # Return immediately if the dandiset metadata file does not exist in the current
        # dandiset version directory
        if not dandiset_metadata_file_path.is_file():
            return

        # Get the Pydantic model to validate against
        if dandiset_version == "draft":
            model = Dandiset
        else:
            model = PublishedDandiset

        dandiset_metadata = dandiset_metadata_file_path.read_text()
        pydantic_validation_errs = pydantic_validate(dandiset_metadata, model)

        if any([pydantic_validation_errs]):
            dandiset_validation_reports[dandiset_identifier][dandiset_version] = (
                DandisetValidationReport(
                    dandiset_identifier=dandiset_identifier,
                    dandiset_version=dandiset_version,
                    pydantic_validation_errs=pydantic_validation_errs,
                )
            )

            logger.info(
                "Dandiset %s:%s: Generated and added a dandiset validation report",
                dandiset_identifier,
                dandiset_version,
            )
        else:
            logger.info(
                "Dandiset %s:%s: dandiset metadata is valid",
                dandiset_identifier,
                dandiset_version,
            )

    def add_asset_validation_reports_if_err() -> None:
        """
        Add `AssetValidationReport` objects to `asset_validation_reports` if the
        current dandiset version directory contains an assets metadata file and
        a validation of some instance of asset metadata produces an error.

        Note: Validation reports are only added for instances of asset metadata that
            fail a validation
        """
        assets_metadata_file_path = version_dir / ASSETS_FILE_NAME

        # Return immediately if the assets metadata file does not exist in the current
        # dandiset version directory
        if not assets_metadata_file_path.is_file():
            return

        # Get the Pydantic model to validate against
        if dandiset_version == "draft":
            model = Asset
        else:
            model = PublishedAsset

        # JSON string read from the assets metadata file
        assets_metadata_json = assets_metadata_file_path.read_text()

        try:
            # Assets metadata as a list of dictionaries
            assets_metadata_python: list[DandiMetadata] = (
                DANDI_METADATA_LIST_ADAPTER.validate_json(assets_metadata_json)
            )
        except ValidationError as e:
            msg = (
                f"The assets metadata file for "
                f"{dandiset_identifier}:{dandiset_version} is of unexpected format."
            )
            raise RuntimeError(msg) from e

        for idx, asset_metadata in enumerate(assets_metadata_python):
            asset_id = asset_metadata.get("id")
            asset_path = asset_metadata.get("path")
            pydantic_validation_errs = pydantic_validate(asset_metadata, model)

            if any([pydantic_validation_errs]):
                r = AssetValidationReport(
                    dandiset_identifier=dandiset_identifier,
                    dandiset_version=dandiset_version,
                    asset_id=asset_id,
                    asset_path=asset_path,
                    pydantic_validation_errs=pydantic_validation_errs,
                )
                asset_validation_reports[
                    Path(dandiset_identifier, dandiset_version, str(idx))
                ] = r

                logger.info(
                    "Dandiset %s:%s: Added validation report for asset %sat index %d",
                    dandiset_identifier,
                    dandiset_version,
                    f"{r.asset_id} " if r.asset_id else "",
                    idx,
                )

    dandiset_validation_reports: DandisetValidationReportsType = defaultdict(dict)
    asset_validation_reports = AssetValidationReportsType()
    for dandiset_dir in get_direct_subdirs(manifest_path):
        # === In a dandiset directory ===
        dandiset_identifier = dandiset_dir.name

        for version_dir in get_direct_subdirs(dandiset_dir):
            # === In a dandiset version directory ===
            dandiset_version = version_dir.name

            add_dandiset_validation_report_if_err()
            add_asset_validation_reports_if_err()

    # Ensure directory for reports exists
    logger.info("Creating report directory: %s", reports_dir_path)
    create_or_replace_dir(reports_dir_path)

    # Write the dandiset validation reports to a file
    write_reports(
        dandiset_validation_reports_file_path,
        dandiset_validation_reports,
        DANDISET_VALIDATION_REPORTS_ADAPTER,
    )
    logger.info(
        "Wrote dandiset validation reports to %s",
        dandiset_validation_reports_file_path,
    )

    # Write the asset validation reports to a file
    write_reports(
        asset_validation_reports_file_path,
        asset_validation_reports,
        ASSET_VALIDATION_REPORTS_ADAPTER,
    )
    logger.info(
        "Wrote asset validation reports to %s",
        asset_validation_reports_file_path,
    )


@app.command("diff-manifests-reports")
def diff_manifests_reports_(
    reports_dir1_path: Annotated[
        Path,
        typer.Argument(
            help="Path of the directory containing the first set of reports for "
            "contrast"
        ),
    ],
    reports_dir2_path: Annotated[
        Path,
        typer.Argument(
            help="Path of the directory containing the second set of reports for "
            "contrast"
        ),
    ],
):
    """
    Generate a report of differences between two sets of reports on the same manifests
    """
    from dandisets_linkml_status_tools.cmd_funcs.diff_manifests_reports import (
        diff_manifests_reports,
    )

    diff_manifests_reports(
        reports_dir1_path, reports_dir2_path, config["output_dir_path"]
    )
