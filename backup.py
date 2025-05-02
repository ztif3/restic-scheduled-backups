#!/usr/bin/env python3

import logging
import subprocess
from pathlib import Path

import restic

    

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
        result = restic.init()
        logging.warning(f'Repo {repo} created.')
        logging.debug(f'Init result for {repo}\n{result}')
    else:
        logging.info(f'Repo {repo} already exists.')

    
def data_backup(
        repo: Path | str, 
        pw_file: Path | str, 
        paths: list[Path|str],
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
        logging.debug(f'Backup result for {repo}\n{result}')
        # TODO add email notification for backup success

def copy_repo(src_repo:Path | str, dst_repo:Path | str, pw_file: Path | str):
    """ Copy the repo to a secondary location.

    Args:
        src_repo (Path | str): path to the source repo
        dst_repo (Path | str): path for the destination repo
        pw_file (Path | str): password file for the restic repo
    """
    # Set repo parameters
    restic.repository = dst_repo          
    restic.password_file = pw_file

    # Copy repo to secondary location
    try:
        logging.info(f'Copying {src_repo} to {dst_repo}...')
        result = restic.copy(
            from_repo=src_repo,
            from_password_file=pw_file,
        )

    except restic.errors.ResticFailedError as e:
        logging.exception(f'Copy from {src_repo} to {dst_repo} failed.')
        # TODO add email notification for copy failure
    else:
        logging.info(f'Copy from {src_repo} to {dst_repo} completed successfully.')
        logging.debug(f'Copy result from {src_repo} to {dst_repo}\n{result}')
        # TODO add email notification for copy success

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
        logging.info(f'Cleanup for {repo} completed successfully.')
        logging.debug(f'Cleanup result for {repo}\n{result}')
        # TODO add email notification for cleanup success


# TODO Add check method


        

    

def stop_container(container:str):
    """ Function to stop a container.

    Args:
        container (str): path to the container to stop
    """

    logging.info(f'Stopping container {container}...')
    try:
        output=subprocess.run(['docker-compose', 'down'], capture_output=True, cwd=container)
        logging.info(f'Container {container} stopped. {output.stdout.decode()}')
    except subprocess.CalledProcessError as e:
        logging.error(f'Failed to stop container {container}: {e}')
        raise
    else:
        if output.returncode == 0:
            logging.info(f'Container {container} stopped successfully.')
            logging.debug(f'Results from stopping container {container}. \n{output.stdout.decode()}')
        else:
            logging.error(f'Failed to stop container {container}. \n{output.stderr.decode()}')
            raise subprocess.CalledProcessError(output.returncode, output.args, output.stdout, output.stderr) 

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
    else:
        if output.returncode == 0:
            logging.info(f'Container {container} started successfully. \n{output.stdout.decode()}')
            logging.debug(f'Results from starting container {container}. \n{output.stdout.decode()}')
        else:
            logging.error(f'Failed to start container {container}. \n{output.stderr.decode()}')
            raise subprocess.CalledProcessError(output.returncode, output.args, output.stdout, output.stderr) 