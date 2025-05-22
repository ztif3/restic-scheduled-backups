#!/usr/bin/env python3
import argparse
import logging
from logging.config import dictConfig
import subprocess

from backup import copy_repo, init_repo, data_backup, clean_repo
from containers import start_container, stop_container

logger = logging.getLogger(__name__)

def main():
    """ Main function to run the data backup script. """

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run data backup script.')
    
    parser.add_argument('repo', type=str, help='repo path for the backup')
    parser.add_argument('pw_file', type=str, help='Password file for the restic repo')
    parser.add_argument('--containers', type=str, nargs='+', help='Paths of container directories to backup')
    parser.add_argument('--secondary_repos', type=str, nargs='*', help='list of paths for secondary repos', default=[])
    parser.add_argument('--exclude_files',type=str, nargs='*', help='List of files with paths to exclude in the backup')
    parser.add_argument('--ret_days', type=int, help='Number of days to keep the backup', default=14)
    parser.add_argument('--ret_weeks', type=int, help='Number of weeks to keep the backup', default=16)
    parser.add_argument('--ret_months', type=int, help='Number of months to keep the backup', default=18)
    parser.add_argument('--ret_years', type=int, help='Number of years to keep the backup', default=3)
    parser.add_argument('--dry_run', action='store_true', help='Run the script in dry run mode')
    parser.add_argument('--debug', action='store_true', help='Show debug logging level')
    parser.add_argument('--no_cleanup', action='store_true', default=False, help='Cleanup the repo after backup')
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logging.setLevel(logging.DEBUG)


    if args.containers is not None:
        # Initialize Repo if necessary
        init_repo(args.repo, args.pw_file)

        for container in args.containers:
            try:
                stop_container(container)
            except subprocess.CalledProcessError as e:
                pass
                # TODO Improve error handling for container stop
            
            # Run the backup
            data_backup(
                repo=args.repo,
                pw_file=args.pw_file,
                paths=[container],
                exclude_files=args.exclude_files,
                dry_run=args.dry_run
            )

            try:
                start_container(container)
            except subprocess.CalledProcessError as e:
                pass
                # TODO Improve error handling for container starting

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
            logging.info(f'Skipping cleanup of repo {args.repo}.')

        # Copy the repo to secondary locations
        for secondary_repo in args.secondary_repos:
            try:
                # Initialize secondary repo if necessary
                init_repo(secondary_repo, args.pw_file)

                # Copy primary repo to secondary repo
                copy_repo(
                    src_repo=args.repo,
                    dst_repo=secondary_repo,
                    pw_file=args.pw_file
                )

                # Cleanup secondary repo
                clean_repo(
                    repo=secondary_repo,
                    pw_file=args.pw_file,
                    ret_days=args.ret_days,
                    ret_weeks=args.ret_weeks,
                    ret_months=args.ret_months,
                    ret_years=args.ret_years,
                    dry_run=args.dry_run
                )
            except subprocess.CalledProcessError as e:
                pass
    else:
        logging.warning('No Containers provided - Backup Skipped')

if __name__ == '__main__':
    main()