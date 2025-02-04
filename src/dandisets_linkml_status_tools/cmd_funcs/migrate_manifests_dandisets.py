import json
import logging
from pathlib import Path

from dandischema.metadata import migrate

from dandisets_linkml_status_tools.tools import (
    create_or_replace_dir,
    get_direct_subdirs,
)

logger = logging.getLogger(__name__)


def migrate_manifests_dandisets(manifest_path: Path, output_dir: Path) -> None:
    """
    Migrate `Dandiset` metadata in manifests to the latest version of the `Dandiset`
    model

    :param manifest_path: Path of the directory containing dandiset manifests
    :param output_dir: Path of the directory to save the migrated manifests
    """
    from dandisets_linkml_status_tools.cli import DANDISET_FILE_NAME

    logger.info("Creating directory %s for the migrated manifests", output_dir)
    create_or_replace_dir(output_dir)

    for dandiset_dir in get_direct_subdirs(manifest_path):
        # === In a dandiset directory ===
        dandiset_identifier = dandiset_dir.name

        for version_dir in get_direct_subdirs(dandiset_dir):
            # === In a dandiset version directory ===
            dandiset_version = version_dir.name

            # Dandiset metadata file path
            dandiset_md_file: Path = version_dir / DANDISET_FILE_NAME

            # Skip if the dandiset metadata file does not exist
            if not dandiset_md_file.is_file():
                continue

            # Load the dandiset metadata
            dandiset_md = json.loads(dandiset_md_file.read_text())

            # Migrate the dandiset metadata
            try:
                dandiset_md_migrated = migrate(dandiset_md, skip_validation=True)
            except (NotImplemented, ValueError) as e:
                logger.warning(
                    "Failed to migrate dandiset metadata in %s/%s: %s",
                    dandiset_identifier,
                    dandiset_version,
                    e,
                )
                # Construct a dummy dandiset metadata instance indicating the error
                dandiset_md_migrated = {
                    "metadata_migration_failed": f"This is an invalid dandiset metadata"
                    f" instance. Migration of the original metadata instance failed "
                    f"with error: {e!r}"
                }
            else:
                logger.info(
                    "Migrated dandiset metadata in %s/%s",
                    dandiset_identifier,
                    dandiset_version,
                )

            # Save the migrated dandiset metadata
            dandiset_md_migrated_dir: Path = (
                output_dir / dandiset_identifier / dandiset_version
            )
            dandiset_md_migrated_dir.mkdir(parents=True)
            dandiset_md_migrated_file: Path = (
                dandiset_md_migrated_dir / DANDISET_FILE_NAME
            )
            dandiset_md_migrated_file.write_text(json.dumps(dandiset_md_migrated))
