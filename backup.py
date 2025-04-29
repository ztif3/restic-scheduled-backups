#!/usr/bin/env python3

import argparse
import logging
from logging.config import dictConfig
from pathlib import Path
from pprint import pprint

import restic


def main():
    """ Main function to run the data backup script. """

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run data backup script.')
    
    parser.add_argument('repo', type=str, help='repo path for the backup')
    parser.add_argument('pw_file', type=str, help='Password file for the restic repo')
    parser.add_argument('paths', type=str, nargs='+', help='Paths to backup')
    parser.add_argument('--exclude_files',type=str, nargs='*', help='List of files with paths to exclude in the backup')
    parser.add_argument('--ret_days', type=int, help='Number of days to keep the backup', default=14)
    parser.add_argument('--ret_weeks', type=int, help='Number of weeks to keep the backup', default=16)
    parser.add_argument('--ret_months', type=int, help='Number of months to keep the backup', default=18)
    parser.add_argument('--ret_years', type=int, help='Number of years to keep the backup', default=3)
    parser.add_argument('--dry_run', action='store_true', help='Run the script in dry run mode')
    parser.add_argument('--info', action='store_true', help='Show info logging level')
    parser.add_argument('--debug', action='store_true', help='Show debug logging level')
    parser.add_argument('--no_cleanup', action='store_true', default=False, help='Cleanup the repo after backup')
    
    args = parser.parse_args()

    # Configure logging
    log_level = logging.WARN
    if args.debug:
        log_level = logging.DEBUG
    elif args.info:
        log_level = logging.INFO    

    dictConfig(
        {
            "version": 1,
            "formatters": {
                "default": {
                    "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "default",
                }
            },
            "root": {"level": log_level, "handlers": ["console"]},
        }
    )

    # Initialize Repo if necessary
    init_repo(args.repo, args.pw_file)

    # Run the backup
    data_backup(
        repo=args.repo,
        pw_file=args.pw_file,
        paths=args.paths,
        exclude_files=args.exclude_files,
        dry_run=args.dry_run
    )

    # Clean the repo
    if not args.no_cleanup:
        clean_repo(
            repo=args.repo,
            pw_file=args.pw_file,
            ret_days=args.ret_days,
            ret_weeks=args.ret_weeks,
            ret_months=args.ret_months,
            ret_years=args.ret_years,
            dry_run=args.dry_run
        )
    else:
        logging.info('Skipping cleanup of the repo.')

    

def init_repo(repo: Path | str, pw_file: Path | str):
    """ Initialize the repo if it does not already exist.

    Args:
        repo (Path | str): path to the restic repo
        pw_file (Path | str): password file for the restic repo
    """
    
    # Set repo parameters
    restic.repository = repo
    restic.password_file = pw_file

    # Initialize repo if it does not already exist
    try:
        restic.cat.config()
    except restic.errors.ResticFailedError as e:
        # Initialize repo
        results = restic.init()
        logging.warning(f'Repo {repo} created. {results}')
    else:
        logging.info(f'Repo {repo} already exists.')

    
def data_backup(
        repo: Path | str, 
        pw_file: Path | str, 
        paths: list[Path|str],
        include_files: list[Path|str]=[], 
        exclude_files: list[Path|str]=[], 
        dry_run: bool = False
    ):
    """ Function to run the data backup script.

    Args:
        repo (Path | str): path to the restic repo
        pw_file (Path | str): password file for the restic repo
        paths (list[Path | str]): paths to backup
        exclude_files (list[Path | str]): List of files with paths to exclude in the backup
        dry_run (bool): if True, run the script in dry run mode
    """
    # Set repo parameters
    restic.repository = repo
    restic.password_file = pw_file

    # Run Restic Backup
    try:
        logging.info(f'Running backup for {repo}...')
        result = restic.backup(
            paths=paths,
            exclude_files=exclude_files, 
            dry_run=dry_run
        )
    except restic.errors.ResticFailedError as e:
        logging.exception(f'Backup for {repo} failed.')
        # TODO add email notification for backup failure
    else:
        logging.info(f'Backup for {repo} completed successfully. {result}')
        # TODO add email notification for backup success

def clean_repo(repo: Path | str,pw_file: Path | str, ret_days: int, ret_weeks: int, ret_months: int, ret_years: int, dry_run: bool = False):
    """ Clean the repo by removing old snapshots.

    Args:
        repo (Path | str): path to the restic repo
        pw_file (Path | str): password file for the restic repo
        ret_days (int): Number of days to keep the backup
        ret_weeks (int): Number of weeks to keep the backup
        ret_months (int): Number of months to keep the backup
        ret_years (int): Number of years to keep the backup
        dry_run (bool): if True, run the script in dry run mode
    """
    # Set repo parameters
    restic.repository = repo
    restic.password_file = pw_file

    # Remove old snapshots
    try:
        logging.info(f'Running cleanup for {repo}...')
        result = restic.forget(
            prune=True,
            keep_daily=ret_days,
            keep_weekly=ret_weeks,
            keep_monthly=ret_months,
            keep_yearly=ret_years,
            dry_run=dry_run
        )
    except restic.errors.ResticFailedError as e:
        logging.exception(f'Cleanup for {repo} failed.')
        # TODO add email notification for cleanup failure
    else:
        logging.info(f'Cleanup for {repo} completed successfully. {result}')
        # TODO add email notification for cleanup success

if __name__ == '__main__':
    main()