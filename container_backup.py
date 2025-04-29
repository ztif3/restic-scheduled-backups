#!/usr/bin/env python3
import argparse
import logging
import subprocess
from logging.config import dictConfig

from backup import init_repo, data_backup, clean_repo

def main():
    """ Main function to run the data backup script. """

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run data backup script.')
    
    parser.add_argument('repo', type=str, help='repo path for the backup')
    parser.add_argument('pw_file', type=str, help='Password file for the restic repo')
    parser.add_argument('containers', type=str, nargs='+', help='Paths of container directories to backup')
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

    for container in args.containers:
        try:
            stop_container(container)
        except subprocess.CalledProcessError as e:
            pass
        else:
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

def stop_container(container:str):
    """ Function to stop a container.

    Args:
        container (str): path to the container to stop
    """

    logging.info(f'Stopping container {container}...')
    try:
        output=subprocess.run(['docker-compose', 'down'], check=True, capture_output=True, cwd=container)
        logging.info(f'Container {container} stopped. {output.stdout.decode()}')
    except subprocess.CalledProcessError as e:
        logging.error(f'Failed to stop container {container}: {e}')
        raise

def start_container(container:str):
    """ Function to start a container.

    Args:
        container (str): path to the container to start
    """

    logging.info(f'Starting container {container}...')
    try:
        output = subprocess.run(['docker-compose', 'up', '-d'], check=True, capture_output=True, cwd=container)
        logging.info(f'Container {container} started. {output.stdout.decode()}')
    except subprocess.CalledProcessError as e:
        logging.error(f'Failed to start container {container}: {e}')
        raise

if __name__ == '__main__':
    main()