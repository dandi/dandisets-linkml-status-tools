import logging
from pathlib import Path
from typing import Annotated

import typer
from dandi.dandiapi import DandiAPIClient
from pydantic import TypeAdapter
from pydantic2linkml.cli.tools import LogLevel

from dandisets_linkml_status.cli.models import DandisetValidationReport
from dandisets_linkml_status.cli.tools import DandisetLinkmlValidator, pydantic_validate

logger = logging.getLogger(__name__)
app = typer.Typer()


@app.command()
def main(
    *,
    include_unpublished: Annotated[
        bool, typer.Option("--include-unpublished", "-u")
    ] = False,
    output_file: Annotated[
        Path,
        typer.Option(
            "--output-file",
            "-o",
            help="Output file to be used to store the reports of the validation results.",
        ),
    ] = Path("validation_reports.json"),
    log_level: Annotated[
        LogLevel, typer.Option("--log-level", "-l")
    ] = LogLevel.WARNING,
):
    validation_report_list_adapter = TypeAdapter(list[DandisetValidationReport])

    # Set log level of the CLI
    logging.basicConfig(level=getattr(logging, log_level))

    dandiset_linkml_validator = DandisetLinkmlValidator()
    validation_reports: list[DandisetValidationReport] = []

    with DandiAPIClient.for_dandi_instance("dandi") as client:
        # Generate validation reports for danidsets
        for dandiset in client.get_dandisets(draft=include_unpublished, order="id"):
            dandiset_id = dandiset.identifier
            logger.info("Processing dandiset %s", dandiset_id)

            most_recent_published_version = dandiset.most_recent_published_version

            if most_recent_published_version is not None:
                # Make sure a published dandiset is at its latest version
                dandiset = dandiset.for_version(most_recent_published_version)

            raw_metadata = dandiset.get_raw_metadata()

            # Validate the raw metadata using the Pydantic model
            pydantic_validation_errs = pydantic_validate(raw_metadata)
            if pydantic_validation_errs is not None:
                logger.info(
                    "Captured Pydantic validation errors for dandiset %s",
                    dandiset_id,
                )

            # Validate the raw metadata using the LinkML schema
            linkml_validation_errs = dandiset_linkml_validator.validate(raw_metadata)
            if linkml_validation_errs is not None:
                logger.info(
                    "Captured LinkML validation errors for dandiset %s", dandiset_id
                )

            validation_reports.append(
                DandisetValidationReport(
                    dandiset_identifier=dandiset_id,
                    dandiset_metadata=raw_metadata,
                    pydantic_validation_errs=pydantic_validation_errs,
                    linkml_validation_errs=linkml_validation_errs,
                )
            )

    # Write the validation reports to the output file
    with output_file.open("wb") as f:
        f.write(validation_report_list_adapter.dump_json(validation_reports, indent=2))

    # import pdb; pdb.set_trace()
    print('\n'.join(f"dandiset: {r.dandiset_identifier}, linkml: {len(r.linkml_validation_errs or [])}, pydantic: {len(r.pydantic_validation_errs or [])}" for r in validation_reports))
    #pprint(validation_reports)

    logger.info("Success!")
