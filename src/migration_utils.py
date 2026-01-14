import os
import shutil
import logging
import threading
import stat
import subprocess
from datetime import datetime
from typing import Callable, List, Optional
from pathlib import Path


class MigrationUtils:
    """Utilities for migrating configurations and deploying between Active and Stable folders."""

    # Files/folders to exclude during deployment
    DEPLOY_EXCLUDES = {
        '.git',
        '.venv',
        '__pycache__',
        '.pytest_cache',
        '.mypy_cache',
        '.vscode',
        '.idea',
        '.DS_Store',
        'node_modules',
        '*.pyc',
        '*.pyo',
        '*.log',
        'messages_backup_*.json',
        'REAL_REPORT_*.csv',
        'REAL_REPORT_*.pdf',
        # Note: ad_plays_*.json and ad_failures_*.json are intentionally NOT excluded
        # as they contain important ad statistics that should be preserved during migration
    }

    @staticmethod
    def get_default_stable_path(active_root: str) -> str:
        """Get default stable path as sibling with ' - stable' suffix."""
        return os.path.join(os.path.dirname(active_root), os.path.basename(active_root) + " - stable")

    @staticmethod
    def validate_paths(active_root: str, stable_path: str) -> Optional[str]:
        """
        Validate that paths are safe for migration operations.

        Returns None if valid, error message if invalid.
        """
        active_path = Path(active_root).resolve()
        stable_path = Path(stable_path).resolve()

        # Don't allow same paths
        if active_path == stable_path:
            return "Active and Stable paths cannot be the same."

        # Don't allow Stable inside Active or Active inside Stable
        try:
            active_path.relative_to(stable_path)
            return "Active folder cannot be inside Stable folder."
        except ValueError:
            pass

        try:
            stable_path.relative_to(active_path)
            return "Stable folder cannot be inside Active folder."
        except ValueError:
            pass

        return None

    # Core config file that must be copied
    CORE_DATA_FILES = ['config.json']

    @staticmethod
    def get_ad_data_files(source_path: str) -> List[str]:
        """
        Dynamically find all ad-related data files in the source directory.

        Returns list of filenames including config.json and all ad_plays_*.json, ad_failures_*.json files.
        Files are located in user_data/ subfolder.
        """
        import glob

        ad_files = MigrationUtils.CORE_DATA_FILES.copy()

        # Look in user_data subfolder for data files
        user_data_path = os.path.join(source_path, "user_data")

        if not os.path.exists(user_data_path):
            # Fallback to root for backward compatibility with old installations
            user_data_path = source_path

        # Find all ad_plays_*.json files
        plays_pattern = os.path.join(user_data_path, "ad_plays_*.json")
        ad_files.extend([os.path.basename(f) for f in glob.glob(plays_pattern)])

        # Find all ad_failures_*.json files
        failures_pattern = os.path.join(user_data_path, "ad_failures_*.json")
        ad_files.extend([os.path.basename(f) for f in glob.glob(failures_pattern)])

        return ad_files

    @staticmethod
    def copy_config_file(source_path: str, dest_path: str, backup: bool = True) -> bool:
        """
        Copy config.json from source to dest, optionally backing up dest first.
        Files are in user_data/ subfolder.

        Returns True on success.
        """
        config_file = 'config.json'

        # Look for source in user_data subfolder
        source_user_data = os.path.join(source_path, "user_data")
        if os.path.exists(source_user_data):
            source_config = os.path.join(source_user_data, config_file)
        else:
            # Fallback to root for backward compatibility
            source_config = os.path.join(source_path, config_file)

        # Destination is in user_data subfolder
        dest_user_data = os.path.join(dest_path, "user_data")
        os.makedirs(dest_user_data, exist_ok=True)
        dest_config = os.path.join(dest_user_data, config_file)

        try:
            if not os.path.exists(source_config):
                logging.error(f"Source config not found: {source_config}")
                return False

            # Backup destination if it exists and backup requested
            if backup and os.path.exists(dest_config):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = os.path.join(dest_user_data, f"config_backup_{timestamp}.json")
                shutil.copy2(dest_config, backup_file)
                logging.info(f"Backed up existing config to: {backup_file}")

            # Copy the config
            shutil.copy2(source_config, dest_config)
            logging.info(f"Copied config from {source_config} to {dest_config}")
            return True

        except Exception as e:
            logging.exception(f"Failed to copy config from {source_config} to {dest_config}")
            return False

    @staticmethod
    def copy_config_and_stats(source_path: str, dest_path: str, backup: bool = True) -> tuple:
        """
        Copy config.json and all ad statistics/events files from source to dest.
        Files are in user_data/ subfolder.

        Args:
            source_path: Source folder path
            dest_path: Destination folder path
            backup: Whether to backup existing files before overwriting

        Returns:
            Tuple of (success: bool, copied_files: list, failed_files: list)
        """
        copied_files = []
        failed_files = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Get all ad data files dynamically
        ad_data_files = MigrationUtils.get_ad_data_files(source_path)

        # Setup source user_data path
        source_user_data = os.path.join(source_path, "user_data")
        if not os.path.exists(source_user_data):
            # Fallback to root for backward compatibility
            source_user_data = source_path

        # Setup destination user_data path
        dest_user_data = os.path.join(dest_path, "user_data")
        os.makedirs(dest_user_data, exist_ok=True)

        for filename in ad_data_files:
            source_file = os.path.join(source_user_data, filename)
            dest_file = os.path.join(dest_user_data, filename)

            # Skip if source file doesn't exist (stats files may not exist yet)
            if not os.path.exists(source_file):
                if filename == 'config.json':
                    # config.json is required
                    logging.error(f"Source config not found: {source_file}")
                    failed_files.append(filename)
                else:
                    # Stats files are optional
                    logging.debug(f"Optional file not found, skipping: {source_file}")
                continue

            try:
                # Backup destination if it exists and backup requested
                if backup and os.path.exists(dest_file):
                    backup_name = f"{os.path.splitext(filename)[0]}_backup_{timestamp}.json"
                    backup_file = os.path.join(dest_user_data, backup_name)
                    shutil.copy2(dest_file, backup_file)
                    logging.info(f"Backed up existing {filename} to: {backup_file}")

                # Copy the file
                shutil.copy2(source_file, dest_file)
                logging.info(f"Copied {filename} from {source_user_data} to {dest_user_data}")
                copied_files.append(filename)

            except Exception as e:
                logging.exception(f"Failed to copy {filename}: {e}")
                failed_files.append(filename)

        # Success if config.json was copied (the required file)
        success = 'config.json' in copied_files
        return success, copied_files, failed_files

    @staticmethod
    def _should_exclude(path: str, excludes: set) -> bool:
        """Check if a path should be excluded from deployment."""
        name = os.path.basename(path)

        # Check exact matches
        if name in excludes:
            return True

        # Check patterns
        for exclude in excludes:
            if '*' in exclude:
                import fnmatch
                if fnmatch.fnmatch(name, exclude):
                    return True

        return False

    @staticmethod
    def _remove_readonly(func, path, excinfo):
        """Error handler for shutil.rmtree to handle read-only files on Windows."""
        os.chmod(path, stat.S_IWRITE)
        func(path)

    @staticmethod
    def _wipe_directory_contents(dir_path: Path, progress_callback: Optional[Callable] = None) -> tuple:
        """
        Wipe all contents inside a directory without removing the directory itself.
        Returns (success: bool, failed_items: list).
        """
        failed_items = []

        if not dir_path.exists():
            return True, []

        if progress_callback:
            progress_callback("Wiping stable folder contents...")

        # Get all items in the directory (top-level only first)
        items = list(dir_path.iterdir())

        for item in items:
            try:
                if item.is_file():
                    # Handle read-only files
                    try:
                        os.chmod(item, stat.S_IWRITE)
                    except Exception:
                        pass
                    item.unlink()
                elif item.is_dir():
                    # Use shutil.rmtree with read-only handler for directories
                    shutil.rmtree(item, onerror=MigrationUtils._remove_readonly)
                logging.debug(f"Removed: {item}")
            except Exception as e:
                logging.warning(f"Could not remove {item}: {e}")
                failed_items.append(str(item))

        # Check if directory is now empty (except for failed items)
        remaining = list(dir_path.iterdir())
        if remaining:
            logging.warning(f"{len(remaining)} items remain in {dir_path}")

        return len(failed_items) == 0, failed_items

    @staticmethod
    def deploy_active_to_stable(active_root: str, stable_path: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        Deploy entire Active folder to Stable (wipe Stable contents first).

        Excludes common development/artifacts.
        Returns True on success.
        """
        try:
            active_path = Path(active_root)
            stable_path = Path(stable_path)

            # Wipe contents of stable folder (keep the folder itself)
            if stable_path.exists():
                logging.info(f"Wiping contents of stable folder: {stable_path}")
                success, failed_items = MigrationUtils._wipe_directory_contents(stable_path, progress_callback)

                if not success:
                    logging.error(f"Could not remove {len(failed_items)} items: {failed_items}")
                    if progress_callback:
                        progress_callback(f"Error: {len(failed_items)} items couldn't be removed")
                    return False

                logging.info("Stable folder contents wiped successfully")
            else:
                # Stable folder doesn't exist - create it
                stable_path.mkdir(parents=True, exist_ok=True)
                logging.info(f"Created stable folder: {stable_path}")

            # Copy all files/folders from active to stable, excluding specified items
            total_items = sum(1 for _ in active_path.rglob('*') if _.is_file() or _.is_dir())
            processed = 0

            for item in active_path.rglob('*'):
                if MigrationUtils._should_exclude(str(item), MigrationUtils.DEPLOY_EXCLUDES):
                    continue

                # Skip .git directory entirely - don't try to copy it
                if '.git' in str(item):
                    continue

                # Calculate relative path
                rel_path = item.relative_to(active_path)
                dest_path = stable_path / rel_path

                try:
                    if item.is_file():
                        # Ensure parent directory exists
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        # Copy with metadata preservation
                        shutil.copy2(item, dest_path)
                    elif item.is_dir():
                        # Create directory
                        dest_path.mkdir(parents=True, exist_ok=True)

                    processed += 1
                    if progress_callback and processed % 10 == 0:  # Update every 10 items
                        progress_callback(f"Copied {processed}/{total_items} items...")

                except Exception as e:
                    logging.warning(f"Failed to copy {item} -> {dest_path}: {e}")
                    continue

            if progress_callback:
                progress_callback("Deployment complete!")

            logging.info(f"Successfully deployed {processed} items to {stable_path}")
            return True

        except Exception as e:
            logging.exception(f"Failed to deploy active to stable: {active_root} -> {stable_path}")
            return False

    @staticmethod
    def run_in_thread(func: Callable, *args, **kwargs) -> threading.Thread:
        """Run a function in a background thread."""
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        return thread
