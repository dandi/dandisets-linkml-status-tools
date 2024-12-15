import json
import logging
from collections import Counter
from collections.abc import Iterable
from copy import deepcopy
from functools import partial
from itertools import chain
from pathlib import Path
from shutil import rmtree
from typing import Any, NamedTuple

from dandi.dandiapi import RemoteDandiset
from dandischema.models import Dandiset, PublishedDandiset
from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin, ValidationPlugin
from linkml.validator.report import ValidationResult
from linkml_runtime.dumpers import yaml_dumper
from linkml_runtime.linkml_model import SchemaDefinition
from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic2linkml.gen_linkml import translate_defs
from yaml import dump as yaml_dump

from .models import (
    DANDI_METADATA_ADAPTER,
    LINKML_VALIDATION_ERRS_ADAPTER,
    PYDANTIC_VALIDATION_ERRS_ADAPTER,
    DandiMetadata,
    DandisetLinkmlTranslationReport,
    JsonschemaValidationErrorType,
    LinkmlValidationErrsType,
    PydanticValidationErrsType,
    ValidationReportsType,
)

try:
    # Import the C-based YAML dumper if available
    from yaml import CSafeDumper as SafeDumper
except ImportError:
    # Otherwise, import the Python-based YAML dumper
    from yaml import SafeDumper  # type: ignore

logger = logging.getLogger(__name__)

# The names of the collection of modules in which the DANDI models are defined
DANDI_MODULE_NAMES = ["dandischema.models"]

# A callable that sorts a given iterable of strings in a case-insensitive manner
isorted = partial(sorted, key=str.casefold)


def iter_direct_subdirs(dir_path: Path) -> Iterable[Path]:
    """
    Get an iterable of the direct subdirectories of a given directory

    :param dir_path: The path of the given directory
    :return: The iterable of the direct subdirectories of the given directory.
        Note: The subdirectories are yielded in arbitrary order.
    :raises: ValueError if the given path doesn't point to a directory
    """
    if not dir_path.is_dir():
        raise ValueError(f"The given path is not a directory: {dir_path}")
    return (p for p in dir_path.iterdir() if p.is_dir())


def get_direct_subdirs(dir_path: Path) -> list[Path]:
    """
    Get a list of the direct subdirectories of a given directory

    :param dir_path: The path of the given directory
    :return: The list of the direct subdirectories of the given directory in sorted
        order by the final component of their path
    :raises: ValueError if the given path doesn't point to a directory
    """
    return sorted(iter_direct_subdirs(dir_path), key=lambda p: p.name)


def pydantic_validate(data: DandiMetadata | str, model: type[BaseModel]) -> list:
    """
    Validate the given data against a Pydantic model

    :param data: The data, as a `DandiMetadata` instance or JSON string, to be validated
    :param model: The Pydantic model to validate the data against
    :return: A list of errors encountered in the validation.
        In the case of validation failure, this is the deserialization of the JSON
        string returned by the Pydantic `ValidationError.json()` method.
        In the case of validation success, this is an empty list.
    """
    if isinstance(data, str):
        validate_method = model.model_validate_json
    else:
        validate_method = model.model_validate

    try:
        validate_method(data)
    except ValidationError as e:
        return json.loads(e.json())

    return []


def write_reports(
    file_path: Path, reports: ValidationReportsType, type_adapter: TypeAdapter
) -> None:
    """
    Write a given collection of validation reports to a specified file

    :param file_path: The path specifying the file to write the reports to
    :param reports: The collection of validation reports to write
    :param type_adapter: The type adapter to use for serializing the collection of
        reports
    """
    file_path.write_bytes(type_adapter.dump_json(reports, indent=2))


def read_reports(file: Path, type_adapter: TypeAdapter) -> ValidationReportsType:
    """
    Read a collection of validation reports from a specified file

    :param file: The path of the file to read the reports from
    :param type_adapter: The type adapter to use for deserializing the collection of
        reports
    :return: The collection of validation reports read from the file
    """
    return type_adapter.validate_json(file.read_bytes())


class DandiModelLinkmlValidator:
    """
    A class to validate DANDI metadata against the DANDI metadata models in
    the LinkML schema produced by the pydantic2linkml translator for DANDI models
    expressed in Pydantic
    """

    # The LinkML schema produced by the pydantic2linkml translator for DANDI models
    _dandi_linkml_schema: SchemaDefinition | None = None

    def __init__(self, validation_plugins: list[ValidationPlugin] | None = None):
        """
        Initialize a `DandiModelLinkmlValidator` instance that wraps a LinkML validator
        instance set up with schema produced by the pydantic2linkml translator,
        for DANDI models expressed in Pydantic, and given validation plugins.

        :param validation_plugins: The list of given validation plugins to set up
        the LinkML validator with. If no validation plugins are given, the default of a
        list containing a `JsonschemaValidationPlugin` instance with `closed=True`.
        """
        if validation_plugins is None:
            validation_plugins = [JsonschemaValidationPlugin(closed=True)]

        self._inner_validator = Validator(
            # TODO: The deep copying may not be needed if
            #  https://github.com/linkml/linkml/issues/2359 is resolved
            deepcopy(self.get_dandi_linkml_schema()),
            validation_plugins=validation_plugins,
        )

    @classmethod
    def get_dandi_linkml_schema(cls) -> SchemaDefinition:
        """
        Get the LinkML schema produced by the pydantic2linkml translator
        for DANDI models

        :return: The LinkML schema
        """
        if cls._dandi_linkml_schema is None:
            cls._dandi_linkml_schema = translate_defs(DANDI_MODULE_NAMES)

        return cls._dandi_linkml_schema

    def validate(
        self, dandi_metadata: DandiMetadata, dandi_metadata_class: str
    ) -> list[ValidationResult]:
        """
        Validate given DANDI metadata against a DANDI metadata model
        specified by its class name in the LinkML schema

        :param dandi_metadata: The DANDI metadata to validate
        :param dandi_metadata_class: The class name of the DANDI metadata model
        :return: A list of validation errors encountered
        """
        validation_report = self._inner_validator.validate(
            dandi_metadata, target_class=dandi_metadata_class
        )
        return validation_report.results


def compile_dandiset_linkml_translation_report(
    dandiset: RemoteDandiset, *, is_dandiset_published: bool
) -> DandisetLinkmlTranslationReport:
    """
    Compile a LinkML translation report against the metadata of a given dandiset

    :param dandiset: The given dandiset
    :param is_dandiset_published: A boolean indicating whether the given dandiset
        is published
    :return: The compiled report

    :raises KeyError: If the metadata of the given dandiset does not contain
        a `"@context"` field

    Note: This function should only be called in the context of a `DandiAPIClient`
        context manager associated with the given dandiset.
    """
    # Determine validation targets
    if is_dandiset_published:
        pydantic_validation_target = PublishedDandiset  # Specified as a Pydantic model
        linkml_validation_target = "PublishedDandiset"  # Specified as a LinkML class
    else:
        pydantic_validation_target = Dandiset  # Specified as a Pydantic model
        linkml_validation_target = "Dandiset"  # Specified as a LinkML class

    dandi_model_linkml_validator = DandiModelLinkmlValidator()

    dandiset_id = dandiset.identifier
    dandiset_version = dandiset.version_id

    raw_metadata = dandiset.get_raw_metadata()

    if "@context" not in raw_metadata:
        msg = (
            f"There is no '@context' key in the metadata of "
            f"dandiset {dandiset_id} @ version {dandiset_version}"
        )
        logger.critical(msg)
        raise KeyError(msg)

    # Remove the "@context" key from the metadata.
    # This key is not part of the `Dandiset`
    # or `PublishedDandiset` metadata model, so it shouldn't
    # be validated as part of the model.
    del raw_metadata["@context"]

    # === Fetch dandiset version info ===
    dandiset_version_info = dandiset.get_version(dandiset_version)
    # Get dandiset version status
    dandiset_version_status = dandiset_version_info.status
    # Get dandiset version modified datetime
    dandiset_version_modified = dandiset_version_info.modified

    # Validate the raw metadata using the Pydantic model
    pydantic_validation_errs = pydantic_validate(
        raw_metadata, pydantic_validation_target
    )
    if pydantic_validation_errs:
        logger.info(
            "Captured Pydantic validation errors for dandiset %s @ %s",
            dandiset_id,
            dandiset_version,
        )

    # Validate the raw metadata using the LinkML schema
    linkml_validation_errs = dandi_model_linkml_validator.validate(
        raw_metadata, linkml_validation_target
    )
    if linkml_validation_errs:
        logger.info(
            "Captured LinkML validation errors for dandiset %s @ %s",
            dandiset_id,
            dandiset_version,
        )

    return DandisetLinkmlTranslationReport(
        dandiset_identifier=dandiset_id,
        dandiset_version=dandiset_version,
        dandiset_version_status=dandiset_version_status,
        dandiset_version_modified=dandiset_version_modified,
        dandiset_metadata=raw_metadata,
        pydantic_validation_errs=pydantic_validation_errs,
        linkml_validation_errs=linkml_validation_errs,
    )


def get_pydantic_err_counts(errs: PydanticValidationErrsType) -> Counter[str]:
    """
    Get a `Counter` object that counts the Pydantic validation errors by type

    :param errs: The list of Pydantic validation errors to be counted
    :return: The `Counter` object
    """
    return Counter(isorted(e["type"] for e in errs))


class _JsonschemaValidationErrorCounts(NamedTuple):
    """
    A record of the counts of individual types of JSON schema validation error
    """

    types: list[JsonschemaValidationErrorType]
    """
    The unique types of JSON schema validation errors
    """

    counts: list[int]
    """
    The corresponding counts, by index, of the types of JSON schema validation errors
    """


def get_linkml_err_counts(
    errs: LinkmlValidationErrsType,
) -> list[tuple[JsonschemaValidationErrorType, int]]:
    """
    Counts given LinkML validation errors by type

    :param errs: A list of LinkML validation errors to be counted
    :return: A list of tuples where each tuple contains a
        `JsonschemaValidationErrorType` object and the count of the errors of the type
        represented by that object
    """

    def count_err(e_: ValidationResult) -> None:
        validator = e_.source.validator
        err_type = JsonschemaValidationErrorType(validator, e_.source.validator_value)

        if validator in counter:
            for i, t in enumerate(counter[validator].types):
                if t == err_type:
                    counter[validator].counts[i] += 1
                    break
            else:
                counter[validator].types.append(err_type)
                counter[validator].counts.append(1)
        else:
            counter[validator] = _JsonschemaValidationErrorCounts(
                types=[err_type], counts=[1]
            )

    def compile_counts() -> list[tuple[JsonschemaValidationErrorType, int]]:
        def sorting_key(
            c: tuple[JsonschemaValidationErrorType, int],
        ) -> tuple[str, int]:
            return c[0].validator, -c[1]

        return sorted(
            chain.from_iterable(zip(t, c, strict=False) for t, c in counter.values()),
            key=sorting_key,
        )

    # A dictionary that keeps the counts of individual types of JSON schema validation
    # errors. The keys of the dictionary are the `validator` of
    # the `JsonschemaValidationErrorType` objects, and the values are
    # the `_JsonschemaValidationErrorCounts` that tallies the errors represented by
    # `JsonschemaValidationErrorType` objects with the same `validator` value.
    counter: dict[str, _JsonschemaValidationErrorCounts] = {}

    for e in errs:
        count_err(e)

    return compile_counts()


def output_dandi_linkml_schema(output_path: Path) -> None:
    """
    Output the DANDI LinkML schema, in YAML, to a file

    :param output_path: The path specifying the location of the file
    """
    # Output the LinkML schema used in the validations
    dandi_linkml_schema_yml = yaml_dumper.dumps(
        DandiModelLinkmlValidator.get_dandi_linkml_schema()
    )
    with output_path.open("w") as f:
        f.write(dandi_linkml_schema_yml)
    logger.info("Output the DANDI LinkML schema to %s", output_path)


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

    logger.info("Creating report directory: %s", output_path)
    create_or_replace_dir(output_path)

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
                r.dandiset_metadata, DANDI_METADATA_ADAPTER, "metadata", report_dir
            )
            _write_data(
                r.pydantic_validation_errs,
                PYDANTIC_VALIDATION_ERRS_ADAPTER,
                "pydantic_validation_errs",
                report_dir,
            )
            _write_data(
                r.linkml_validation_errs,
                LINKML_VALIDATION_ERRS_ADAPTER,
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


def create_or_replace_dir(dir_path: Path):
    """
    Create or replace a directory at a given path

    :param dir_path: The path to the directory to be created or replaced. If `dir_path`
        does not point to any existing object, a new directory will be created at the
        path. If `dir_path` points to an existing object, this object must be a
        directory (not a file or a symlink), and it will be removed and replaced with a
        new directory.
    """
    # Remove the existing report output directory if it exists
    if dir_path.exists():
        logger.info("Found existing directory: %s", dir_path)
        rmtree(dir_path)
        logger.info("Deleted existing directory: %s", dir_path)

    # Create a directory at the given path
    dir_path.mkdir(parents=True)
    logger.info("Created directory: %s", dir_path)


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
