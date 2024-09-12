import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from dandi.dandiapi import DandiAPIClient
from pydantic2linkml.cli.tools import LogLevel

from dandisets_linkml_status.cli.tools import compile_validation_report, output_reports

if TYPE_CHECKING:
    from dandisets_linkml_status.cli.models import DandisetValidationReport

logger = logging.getLogger(__name__)
app = typer.Typer()


@app.command()
def main(
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
    log_level: Annotated[
        LogLevel, typer.Option("--log-level", "-l")
    ] = LogLevel.WARNING,
):
    # Set log level of the CLI
    logging.basicConfig(level=getattr(logging, log_level))

    output_path = Path(dandi_instance + "-reports")

    validation_reports: list[DandisetValidationReport] = []

    with DandiAPIClient.for_dandi_instance(dandi_instance) as client:
        # Generate validation reports for danidsets
        for dandiset in client.get_dandisets(draft=include_unpublished, order="id"):
            dandiset_id = dandiset.identifier
            logger.info("Processing dandiset %s", dandiset_id)

            most_recent_published_version = dandiset.most_recent_published_version

            if most_recent_published_version is not None:
                # Make sure a published dandiset is at its latest version
                dandiset = dandiset.for_version(most_recent_published_version)

            validation_reports.append(compile_validation_report(dandiset))

    # Print summary of validation reports
    print(
        "\n".join(
            f"dandiset: {r.dandiset_identifier}, "
            f"linkml: {len(r.linkml_validation_errs)}, "
            f"pydantic: {len(r.pydantic_validation_errs)}"
            for r in validation_reports
        )
    )

    output_reports(validation_reports, output_path)

    logger.info("Success!")
