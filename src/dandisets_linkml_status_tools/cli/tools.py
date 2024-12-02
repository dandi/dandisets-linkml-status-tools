import json
import logging
from collections.abc import Iterable
from pathlib import Path
from shutil import rmtree
from typing import Any

from pydantic import TypeAdapter
from yaml import dump as yaml_dump

from dandisets_linkml_status_tools.tools import (
    get_pydantic_err_counts,
    get_linkml_err_counts,
    output_dandi_linkml_schema,
)

try:
    # Import the C-based YAML dumper if available
    from yaml import CSafeDumper as SafeDumper
except ImportError:
    # Otherwise, import the Python-based YAML dumper
    from yaml import SafeDumper  # type: ignore

from dandisets_linkml_status_tools.models import (
    DandisetLinkmlTranslationReport,
    dandiset_metadata_adapter,
    pydantic_validation_errs_adapter,
    linkml_validation_errs_adapter,
)

logger = logging.getLogger(__name__)

# The names of the collection of modules in which the DANDI models are defined
DANDI_MODULE_NAMES = ["dandischema.models"]


def output_reports(
    reports: list[DandisetLinkmlTranslationReport], output_path: Path
) -> None:
    """
    Output the given list of dandiset validation reports, a summary of the reports
    , as a `summary.md`, and the schema used in the LinkML validations,
    as a `dandi_linkml_schema.yml`, to a given file path

    Note: This function will replace the output directory if it already exists.

    :param reports: The given list of dandiset validation reports
    :param output_path: The given file path to output the reports to.
        Note: In the case of the given output path already points to an existing object,
        if the object is directory, it will be removed and replaced with a new
        directory; Otherwise, `NotADirectoryError` will be raised.

    raises NotADirectoryError: If the given output path points to a non-directory object
    """
    summary_file_name = "summary.md"
    dandi_linkml_schema_file_name = "dandi-linkml-schema.yml"
    summary_headers = [
        "dandiset",
        "version",
        "pydantic",
        "linkml",
        "modified",
        "api_status",
        "schema_version",
    ]

    # Remove the existing report output directory if it exists
    if output_path.exists():
        logger.info("Found existing report output directory: %s", output_path)
        rmtree(output_path)
        logger.info("Deleted existing report output directory: %s", output_path)

    # Recreate the report output directory
    output_path.mkdir()
    logger.info("Recreated report output directory: %s", output_path)

    output_dandi_linkml_schema(output_path / dandi_linkml_schema_file_name)

    with (output_path / summary_file_name).open("w") as summary_f:
        # === Provide a reference to the DANDI LinkML schema in the summary ===
        summary_f.write(
            f"[DANDI LinkML schema](./{dandi_linkml_schema_file_name}) "
            f"(LinkML schema used in the LinkML validations)\n"
        )

        # Write line break before the start of the summary table
        summary_f.write("\n")

        # === Write the headers of the summary table ===
        header_row = _gen_row(f" {h} " for h in summary_headers)
        alignment_row = _gen_row("-" * (len(h) + 2) for h in summary_headers)
        summary_f.write(header_row + alignment_row)

        # Output the individual dandiset validation reports
        for r in reports:
            report_dir = output_path / r.dandiset_identifier / r.dandiset_version
            report_dir.mkdir(parents=True)

            _write_data(
                r.dandiset_metadata, dandiset_metadata_adapter, "metadata", report_dir
            )
            _write_data(
                r.pydantic_validation_errs,
                pydantic_validation_errs_adapter,
                "pydantic_validation_errs",
                report_dir,
            )
            _write_data(
                r.linkml_validation_errs,
                linkml_validation_errs_adapter,
                "linkml_validation_errs",
                report_dir,
            )

            logger.info("Output dandiset %s validation report", r.dandiset_identifier)

            # === Write the summary table row for the dandiset validation report ===
            # Directory for storing all metadata validation results of the dandiset
            dandiset_dir = f"./{r.dandiset_identifier}"
            # Directory for storing all metadata validation results of the dandiset
            # at a particular version
            version_dir = f"{dandiset_dir}/{r.dandiset_version}"

            pydantic_err_counts = get_pydantic_err_counts(r.pydantic_validation_errs)
            linkml_err_counts = get_linkml_err_counts(r.linkml_validation_errs)

            row_cells = (
                f" {c} "  # Add spaces around the cell content for better readability
                for c in [
                    # For the dandiset column
                    f"[{r.dandiset_identifier}]({dandiset_dir}/)",
                    # For the version column
                    f"[{r.dandiset_version}]({version_dir}/metadata.yaml)",
                    # For the pydantic column
                    (
                        f"[{len(r.pydantic_validation_errs)} "
                        f"({', '.join(f'{v} {k}' for k, v in pydantic_err_counts.items())})]"
                        f"({version_dir}/pydantic_validation_errs.yaml)"
                        if r.pydantic_validation_errs
                        else "0"
                    ),
                    # For the linkml column
                    (
                        f"[{len(r.linkml_validation_errs)} "
                        f"({' + '.join(str(c) for _, c in linkml_err_counts)})]"
                        f"({version_dir}/linkml_validation_errs.yaml)"
                        if r.linkml_validation_errs
                        else "0"
                    ),
                    # For the modified column
                    r.dandiset_version_modified.isoformat(),
                    # For the api_status column
                    r.dandiset_version_status.value,
                    # For schema_version column
                    r.dandiset_schema_version,
                ]
            )
            summary_f.write(_gen_row(row_cells))

    logger.info("Output of dandiset validation reports completed")


def _write_data(
    data: Any, data_adapter: TypeAdapter, base_file_name: str, output_dir: Path
) -> None:
    """
    Output given data to a JSON file and a YAML file in a given output directory

    :param data: The data to be output
    :param data_adapter: The type adapter used to serialize the data
    :param base_file_name: The base file name for the output files
    :param output_dir: The output directory to write the files to
    """
    serializable_data = data_adapter.dump_python(data, mode="json")

    # Output data to a JSON file
    json_file_path = output_dir / (base_file_name + ".json")
    with json_file_path.open("w") as f:
        json.dump(serializable_data, f, indent=2)

    # Output data to a YAML file
    yaml_file_path = output_dir / (base_file_name + ".yaml")
    with yaml_file_path.open("w") as f:
        yaml_dump(serializable_data, f, Dumper=SafeDumper)


def _gen_row(cell_str_values: Iterable[str]) -> str:
    """
    Construct a row of a Markdown table with given cell string values
    :param cell_str_values: The given iterable of cell string values
    :return: The constructed row of a Markdown table

    Note: The given iterable of cell string values are `str` values
    """
    return f'|{"|".join(cell_str_values)}|\n'
