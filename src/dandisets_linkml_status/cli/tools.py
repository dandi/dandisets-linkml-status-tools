import logging
from pathlib import Path
from shutil import rmtree
from typing import Any, Optional

from dandischema.models import Dandiset
from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin, ValidationPlugin
from linkml.validator.report import ValidationResult
from pydantic import TypeAdapter, ValidationError
from pydantic2linkml.gen_linkml import translate_defs

from dandisets_linkml_status.cli.models import DandisetValidationReport

logger = logging.getLogger(__name__)


def pydantic_validate(dandiset_metadata: dict[str, Any]) -> str:
    """
    Validate the given dandiset metadata against the Pydantic dandiset metadata model

    :param dandiset_metadata: The dandiset metadata to validate.
    :return: A JSON string that is an array of errors encountered in the validation
        (The JSON string returned in a case of any validation failure is one returned by
        the Pydantic `ValidationError.json()` method. In the case of no validation
        error, the empty array JSON expression, `"[]"`, is returned.)
    """
    try:
        Dandiset.model_validate(dandiset_metadata)
    except ValidationError as e:
        return e.json()

    return "[]"


class DandisetLinkmlValidator:
    """
    A class to validate dandiset metadata against the dandiset metadata model in
    the LinkML schema produced by the pydantic2linkml translator for DANDI models
    expressed in Pydantic
    """

    def __init__(self, validation_plugins: Optional[list[ValidationPlugin]] = None):
        """
        Initialize a `DandisetLinkmlValidator` instance that wraps a LinkML validator
        instance set up with schema produced by the pydantic2linkml translator,
        for DANDI models expressed in Pydantic, and given validation plugins.

        :param validation_plugins: The list of given validation plugins to set up
        the LinkML validator with. If no validation plugins are given, the default of a
        list containing a `JsonschemaValidationPlugin` instance with `closed=True`.
        """

        # The names of the collection of modules in which the DANDI models are defined
        dandiset_module_names = ["dandischema.models"]

        if validation_plugins is None:
            validation_plugins = [JsonschemaValidationPlugin(closed=True)]

        self._inner_validator = Validator(
            translate_defs(dandiset_module_names),
            validation_plugins=validation_plugins,
        )

    def validate(self, dandiset_metadata: dict[str, Any]) -> list[ValidationResult]:
        """
        Validate the given dandiset metadata against the dandiset metadata model in
        LinkML

        :param dandiset_metadata: The dandiset metadata to validate
        :return: A list of validation errors encountered
        """
        # The name of the class in the LinkML schema representing Dandiset metadata
        dandiset_metadata_class = "Dandiset"

        validation_report = self._inner_validator.validate(
            dandiset_metadata, target_class=dandiset_metadata_class
        )
        return validation_report.results


def output_reports(reports: list[DandisetValidationReport]) -> None:
    """
    In the current working directory, output the given list of dandiset validation
    reports to the subdirectory `validation-reports` and summarize the reports
    in the `README.md` file.

    :param reports: The given list of dandiset validation reports
    """
    reports_dir_name = "validation-reports"
    reports_dir = Path(reports_dir_name)

    # Remove the existing report output directory if it exists
    if reports_dir.exists():
        logger.info("Found existing report output directory: %s", reports_dir_name)
        rmtree(reports_dir)
        logger.info("Deleted existing report output directory: %s", reports_dir_name)

    # Recreate the report output directory
    reports_dir.mkdir()
    logger.info("Recreated report output directory: %s", reports_dir_name)

    # Output the individual dandiset validation reports
    for r in reports:
        report_dir = reports_dir / r.dandiset_identifier
        report_dir.mkdir()

        dataset_metadata_file = report_dir / "metadata.json"
        pydantic_validation_errs_file = report_dir / "pydantic_validation_errs.json"
        linkml_validation_errs_file = report_dir / "linkml_validation_errs.json"

        with dataset_metadata_file.open("wb") as f:
            dandiset_metadata_adapter = TypeAdapter(dict[str, Any])
            f.write(dandiset_metadata_adapter.dump_json(r.dandiset_metadata, indent=2))
        with pydantic_validation_errs_file.open("wb") as f:
            pydantic_validation_errs_adapter = TypeAdapter(list[dict[str, Any]])
            f.write(
                pydantic_validation_errs_adapter.dump_json(
                    r.pydantic_validation_errs, indent=2
                )
            )
        with linkml_validation_errs_file.open("wb") as f:
            linkml_validation_errs_adapter = TypeAdapter(list[ValidationResult])
            f.write(
                linkml_validation_errs_adapter.dump_json(
                    r.linkml_validation_errs, indent=2
                )
            )

        logger.info("Output dandiset %s validation report", r.dandiset_identifier)
