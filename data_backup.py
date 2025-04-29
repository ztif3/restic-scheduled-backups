#!/usr/bin/env python3

import argparse
from pathlib import Path
import restic

def main():
    """ Main function to run the data backup script. """

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run data backup script.')
    
    parser.add_argument('repo', type=str, help='repo path for the backup')
    parser.add_argument('pw_file', type=str, help='Password file for the restic repo')
    parser.add_argument('paths', type=str, nargs='+', help='Paths to backup')
    parser.add_argument('--include_files', type=str, nargs='*', help='List of files with paths to include in the backup')
    parser.add_argument('--exclude_files',type=str, nargs='*', help='List of files with paths to exclude in the backup')
    parser.add_argument('--ret_days', type=int, help='Number of days to keep the backup', default=14)
    parser.add_argument('--ret_weeks', type=int, help='Number of weeks to keep the backup', default=16)
    parser.add_argument('--ret_months', type=int, help='Number of months to keep the backup', default=18)
    parser.add_argument('--ret_years', type=int, help='Number of years to keep the backup', default=3)
    parser.add_argument('--dry_run', action='store_true', help='Run the script in dry run mode')

    args = parser.parse_args()

    print(args.src)

    

def init_repo(repo: Path | str,pw_file: Path | str, dry_run: bool = False):
    """ Initialize the repo if it does not already exist.

    Args:
        repo (Path | str): path to the restic repo
        pw_file (Path | str): password file for the restic repo
        dry_run (bool): if True, run the script in dry run mode
    """
    
    # Set repo parameters
    restic.repo = repo
    restic.password_file = pw_file

    # TODO Initialize repo if it does not already exist

    # TODO Log results of the initialization
    
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
        include_files (list[Path | str]): List of files with paths to include in the backup
        exclude_files (list[Path | str]): List of files with paths to exclude in the backup
        dry_run (bool): if True, run the script in dry run mode
    """
    # Set repo parameters
    restic.repo = repo
    restic.password_file = pw_file
    
    # TODO Check if repo exists

    # Run Restic Backup
    result = restic.backup(
        paths=paths,
        include_files=include_files, 
        exclude_files=exclude_files, 
        skip_if_unchanged=True, 
        dry_run=dry_run
    )

    # TODO Log results of the backup
    # TODO Send notifications of backup results

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
    restic.repo = repo
    restic.password_file = pw_file

    # Remove old snapshots
    result = restic.forget(
        prune=True,
        keep_daily=ret_days,
        keep_weekly=ret_weeks,
        keep_monthly=ret_months,
        keep_yearly=ret_years,
        dry_run=dry_run
    )

    # TODO Log results of the cleanup

if __name__ == '__main__':
    main()