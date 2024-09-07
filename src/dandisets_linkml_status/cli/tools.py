import json
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
from yaml import dump as yaml_dump

try:
    # Import the C-based YAML dumper if available
    from yaml import CSafeDumper as SafeDumper
except ImportError:
    # Otherwise, import the Python-based YAML dumper
    from yaml import SafeDumper  # type: ignore

from dandisets_linkml_status.cli.models import (
    DANDISET_METADATA_ADAPTER,
    LINKML_VALIDATION_ERRS_ADAPTER,
    PYDANTIC_VALIDATION_ERRS_ADAPTER,
    DandisetValidationReport,
)

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


def output_reports(reports: list[DandisetValidationReport], output_path: Path) -> None:
    """
    Output the given list of dandiset validation reports and a summary of the reports
    , as a `summary.md`, to a given file path

    :param reports: The given list of dandiset validation reports
    :param output_path: The given file path to output the reports to.
        Note: In the case of the given output path already points to an existing object,
        if the object is directory, it will be removed and replaced with a new
        directory; Otherwise, `NotADirectoryError` will be raised.

    raises NotADirectoryError: If the given output path points to a non-directory object
    """
    summary_file_name = "summary.md"
    summary_headers = [
        "dandiset",
        "version",
        "schema_version",
        "api_status",
        "modified",
        "pydantic",
        "linkml",
    ]

    # Remove the existing report output directory if it exists
    if output_path.exists():
        logger.info("Found existing report output directory: %s", output_path)
        rmtree(output_path)
        logger.info("Deleted existing report output directory: %s", output_path)

    # Recreate the report output directory
    output_path.mkdir()
    logger.info("Recreated report output directory: %s", output_path)

    def write_data(data: Any, data_adapter: TypeAdapter, base_file_name: str) -> None:
        serializable_data = data_adapter.dump_python(data, mode="json")

        # Output data to a JSON file
        json_file_path = report_dir / (base_file_name + ".json")
        with json_file_path.open("w") as f:
            json.dump(serializable_data, f, indent=2)

        # Output data to a YAML file
        yaml_file_path = report_dir / (base_file_name + ".yaml")
        with yaml_file_path.open("w") as f:
            yaml_dump(serializable_data, f, Dumper=SafeDumper)

    with (output_path / summary_file_name).open("w") as summary_f:
        # === Write the headers of the summary table ===
        header_row = f'|{"|".join(f" {h} " for h in summary_headers)}|\n'
        alignment_row = f'|{"|".join("-" * (len(h) + 2) for h in summary_headers)}|\n'
        summary_f.write(header_row + alignment_row)

        # Output the individual dandiset validation reports
        for r in reports:
            report_dir = output_path / r.dandiset_identifier
            report_dir.mkdir()

            write_data(r.dandiset_metadata, DANDISET_METADATA_ADAPTER, "metadata")
            write_data(
                r.pydantic_validation_errs,
                PYDANTIC_VALIDATION_ERRS_ADAPTER,
                "pydantic_validation_errs",
            )
            write_data(
                r.linkml_validation_errs,
                LINKML_VALIDATION_ERRS_ADAPTER,
                "linkml_validation_errs",
            )

            logger.info("Output dandiset %s validation report", r.dandiset_identifier)
