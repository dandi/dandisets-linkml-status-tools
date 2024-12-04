import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer
from dandi.dandiapi import DandiAPIClient
from dandischema.models import Asset, Dandiset, PublishedAsset, PublishedDandiset
from pydantic import TypeAdapter, ValidationError
from pydantic2linkml.cli.tools import LogLevel

from dandisets_linkml_status_tools.models import (
    DANDI_METADATA_LIST_ADAPTER,
    AssetValidationReport,
    Config,
    DandiMetadata,
    DandisetValidationReport,
)
from dandisets_linkml_status_tools.tools import (
    compile_dandiset_linkml_translation_report,
    iter_direct_subdirs,
    output_reports,
    pydantic_validate,
    write_reports,
)

if TYPE_CHECKING:
    from dandisets_linkml_status_tools.models import DandisetLinkmlTranslationReport

logger = logging.getLogger(__name__)

# Pydantic type adapters
DANDISET_PYDANTIC_REPORT_LIST_ADAPTER = TypeAdapter(list[DandisetValidationReport])
ASSET_PYDANTIC_REPORT_LIST_ADAPTER = TypeAdapter(list[AssetValidationReport])

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

    # Print summary of validation reports
    print(  # noqa: T201
        "\n".join(
            f"dandiset: {r.dandiset_identifier}, "
            f"linkml: {len(r.linkml_validation_errs)}, "
            f"pydantic: {len(r.pydantic_validation_errs)}"
            for r in validation_reports
        )
    )

    output_reports(validation_reports, output_path)

    logger.info("Success!")


# metadata file names
DANDISET_FILE_NAME = "dandiset.jsonld"  # File with dandiset metadata
ASSETS_FILE_NAME = "assets.jsonld"  # File with assets metadata

DANDISET_PYDANTIC_VALIDATION_REPORTS_FILE_NAME = (
    "dandiset_pydantic_validation_reports.json"
)
ASSET_PYDANTIC_VALIDATION_REPORTS_FILE_NAME = "asset_pydantic_validation_reports.json"


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
    reports_dir_path = config["output_dir_path"] / "manifests"
    dandiset_pydantic_validation_reports_file_path = (
        reports_dir_path / DANDISET_PYDANTIC_VALIDATION_REPORTS_FILE_NAME
    )
    asset_pydantic_validation_reports_file_path = (
        reports_dir_path / ASSET_PYDANTIC_VALIDATION_REPORTS_FILE_NAME
    )

    def append_dandiset_validation_report() -> None:
        """
        Append a `DandisetValidationReport` object to `dandiset_validation_reports`
        if the current dandiset version directory contains a dandiset metadata file.
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
        # noinspection PyTypeChecker
        dandiset_validation_reports.append(
            DandisetValidationReport(
                dandiset_identifier=dandiset_identifier,
                dandiset_version=dandiset_version,
                pydantic_validation_errs=pydantic_validation_errs,
            )
        )

    def extend_asset_validation_reports() -> None:
        """
        Extend `asset_validation_reports` with `AssetValidationReport` objects if the
        current dandiset version directory contains an assets metadata file.
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

        for asset_metadata in assets_metadata_python:
            asset_id = asset_metadata.get("id")
            asset_path = asset_metadata.get("path")
            pydantic_validation_errs = pydantic_validate(asset_metadata, model)
            # noinspection PyTypeChecker
            asset_validation_reports.append(
                AssetValidationReport(
                    dandiset_identifier=dandiset_identifier,
                    dandiset_version=dandiset_version,
                    asset_id=asset_id,
                    asset_path=asset_path,
                    pydantic_validation_errs=pydantic_validation_errs,
                )
            )

    dandiset_validation_reports: list[DandisetValidationReport] = []
    asset_validation_reports: list[AssetValidationReport] = []
    for n, dandiset_dir in enumerate(
        sorted(iter_direct_subdirs(manifest_path), key=lambda p: p.name)
    ):
        # === In a dandiset directory ===
        dandiset_identifier = dandiset_dir.name
        print(f"{n}:{dandiset_identifier}: {dandiset_dir}")

        for version_dir in iter_direct_subdirs(dandiset_dir):
            # === In a dandiset version directory ===
            dandiset_version = version_dir.name
            print(f"\tdandiset_version: {dandiset_version}")

            append_dandiset_validation_report()
            extend_asset_validation_reports()

    # Ensure directory for reports exists
    reports_dir_path.mkdir(parents=True, exist_ok=True)

    # Write the dandiset Pydantic validation reports to a file
    write_reports(
        dandiset_pydantic_validation_reports_file_path,
        dandiset_validation_reports,
        DANDISET_PYDANTIC_REPORT_LIST_ADAPTER,
    )

    # Write the asset Pydantic validation reports to a file
    write_reports(
        asset_pydantic_validation_reports_file_path,
        asset_validation_reports,
        ASSET_PYDANTIC_REPORT_LIST_ADAPTER,
    )
