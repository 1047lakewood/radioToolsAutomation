#!/usr/bin/env python3
"""
Deployment script for radioToolsAutomation.

This script handles:
1. Migrating user data from stable to active
2. Deploying active to stable
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from migration_utils import MigrationUtils
from config_manager import ConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_paths():
    """Get active and stable paths from config or defaults."""
    try:
        config_manager = ConfigManager()
        active_root = os.path.dirname(os.path.abspath(__file__))
        stable_path = config_manager.config.get('shared', {}).get('migration', {}).get('stable_path')

        if not stable_path:
            stable_path = MigrationUtils.get_default_stable_path(active_root)

        return active_root, stable_path
    except Exception as e:
        logger.warning(f"Could not load config: {e}")
        active_root = os.path.dirname(os.path.abspath(__file__))
        stable_path = MigrationUtils.get_default_stable_path(active_root)
        return active_root, stable_path


def migrate_from_stable(active_root, stable_path):
    """Copy user data from stable to active."""
    logger.info("=" * 60)
    logger.info("MIGRATION: Copying user data from STABLE to ACTIVE")
    logger.info("=" * 60)

    # Validate paths
    error = MigrationUtils.validate_paths(active_root, stable_path)
    if error:
        logger.error(f"Invalid paths: {error}")
        return False

    logger.info(f"Active folder: {active_root}")
    logger.info(f"Stable folder: {stable_path}")

    if not os.path.exists(stable_path):
        logger.error(f"Stable folder not found: {stable_path}")
        return False

    success, copied_files, failed_files = MigrationUtils.copy_config_and_stats(stable_path, active_root, backup=True)

    logger.info(f"\nMigration Results:")
    logger.info(f"  Copied files: {', '.join(copied_files) if copied_files else 'None'}")
    if failed_files:
        logger.warning(f"  Failed files: {', '.join(failed_files)}")

    return success


def deploy_to_stable(active_root, stable_path):
    """Deploy active to stable."""
    logger.info("=" * 60)
    logger.info("DEPLOYMENT: Copying ACTIVE to STABLE")
    logger.info("=" * 60)

    # Validate paths
    error = MigrationUtils.validate_paths(active_root, stable_path)
    if error:
        logger.error(f"Invalid paths: {error}")
        return False

    logger.info(f"Active folder: {active_root}")
    logger.info(f"Stable folder: {stable_path}")

    def progress(msg):
        logger.info(f"  {msg}")

    success = MigrationUtils.deploy_active_to_stable(active_root, stable_path, progress_callback=progress)

    if success:
        logger.info("\nDeployment completed successfully!")
    else:
        logger.error("\nDeployment failed!")

    return success


def main():
    parser = argparse.ArgumentParser(
        description='Deploy radioToolsAutomation between Active and Stable folders',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python deploy.py --migrate          # Copy config/stats from stable to active
  python deploy.py --deploy           # Copy active to stable
  python deploy.py --full             # Migrate then deploy (full cycle)
  python deploy.py --stable-path /path/to/stable  # Specify custom stable path
        '''
    )

    parser.add_argument('--migrate', action='store_true',
                        help='Migrate user data from stable to active')
    parser.add_argument('--deploy', action='store_true',
                        help='Deploy active to stable')
    parser.add_argument('--full', action='store_true',
                        help='Full cycle: migrate from stable, then deploy to stable')
    parser.add_argument('--stable-path', type=str,
                        help='Path to stable folder (overrides config)')

    args = parser.parse_args()

    # Get paths
    active_root, stable_path = get_paths()
    if args.stable_path:
        stable_path = args.stable_path

    # If no action specified, show help
    if not (args.migrate or args.deploy or args.full):
        parser.print_help()
        return 1

    try:
        # Full cycle: migrate then deploy
        if args.full:
            logger.info("FULL DEPLOYMENT CYCLE: Migrate from stable, then deploy to stable")
            if not migrate_from_stable(active_root, stable_path):
                logger.error("Migration failed!")
                return 1
            logger.info("")
            if not deploy_to_stable(active_root, stable_path):
                logger.error("Deployment failed!")
                return 1
            return 0

        # Just migrate
        if args.migrate:
            if not migrate_from_stable(active_root, stable_path):
                return 1
            return 0

        # Just deploy
        if args.deploy:
            if not deploy_to_stable(active_root, stable_path):
                return 1
            return 0

    except KeyboardInterrupt:
        logger.info("\nDeployment cancelled by user")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
