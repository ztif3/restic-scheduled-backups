#!/usr/bin/env python3

import logging
from os import PathLike
from pathlib import Path
from pprint import pformat
from typing import Optional

import restic
import restic.errors

import common
from config_def import NtfyConfig

logger = logging.getLogger(__name__)

def init_repo(repo: PathLike|str, pw_file: PathLike) -> list[str]:
    """ Initialize the repo if it does not already exist.

    Args:
        repo (PathLike|str): path to the restic repo
        pw_file (PathLike): password file for the restic repo
        
    Return:
        List of error messages  
    """
    
    msgs = []

    # Set repo parameters
    restic.repository = repo
    restic.password_file = pw_file

    # Initialize repo if it does not already exist
    try:
        restic.cat.config()
    except restic.errors.ResticFailedError as e:
        # Initialize repo
        try:
            result = restic.init()
        except restic.errors.ResticFailedError as e:
            msg = f'Unable to initialize repo {repo}'
            logger.error(msg)
            msgs.append(msg)
        else:
            logger.warning(f'Repo {repo} created.')
            logger.debug(f'Init result for {repo}\n{result}')
    else:
        logger.info(f'Repo {repo} already exists.')

    return msgs
    
def data_backup(
        repo: PathLike|str, 
        pw_file: PathLike, 
        paths: list[PathLike|Path],
        exclude_files: list[PathLike]=[], 
        dry_run: bool = False
    ) -> list[str]:
    """ Function to run the data backup script.

    Args:
        repo (PathLike|str): path to the restic repo
        pw_file (PathLike): password file for the restic repo
        paths (list[PathLike]): paths to backup
        exclude_files (list[PathLike]): List of files with paths to exclude in the backup
        dry_run (bool): if True, run the script in dry run mode
        
    Return:
        List of error messages  
    """
    # Set repo parameters
    restic.repository = repo
    restic.password_file = pw_file

    msgs = []

    # Run Restic Backup
    try:
        logger.info(f'Running backup for {repo}...')
        result = restic.backup(
            paths=paths,
            exclude_files=exclude_files, 
            dry_run=dry_run
        )
    except restic.errors.ResticFailedError as e:
        msg = f'Backup for {repo} failed.'
        logger.exception(msg)
        msgs.append(msg)
    else:
        logger.info(f'Backup for {repo} completed successfully.')
        logger.debug(f'Backup result for {repo}\n{pformat(result)}')

    return msgs

def copy_repo(src_repo:PathLike|str, dst_repo:PathLike|str, pw_file: PathLike) -> list[str]:
    """ Copy the repo to a secondary location.

    Args:
        src_repo (PathLike|str): path to the source repo
        dst_repo (PathLike|str): path for the destination repo
        pw_file (PathLike): password file for the restic repo

    Return:
        List of error messages
    """
    # Set repo parameters
    restic.repository = dst_repo          
    restic.password_file = pw_file

    msgs = []

    # Copy repo to secondary location
    try:
        logger.info(f'Copying {src_repo} to {dst_repo}...')
        result = restic.copy(
            from_repo=src_repo,
            from_password_file=pw_file,
        )

    except restic.errors.ResticFailedError as e:
        msg = f'Copy from {src_repo} to {dst_repo} failed.'
        logger.exception(msg)
        msgs.append(msg)
    else:
        logger.info(f'Copy from {src_repo} to {dst_repo} completed successfully.')
        logger.debug(f'Copy result from {src_repo} to {dst_repo}\n{pformat(result)}')

    return msgs

def clean_repo(repo: PathLike|str, pw_file: PathLike, ret_days: int, ret_weeks: int, ret_months: int, ret_years: int, dry_run: bool = False) -> list[str]:
    """ Clean the repo by removing old snapshots.

    Args:
        repo (PathLike|str): path to the restic repo
        pw_file (PathLike): password file for the restic repo
        ret_days (int): Number of days to keep the backup
        ret_weeks (int): Number of weeks to keep the backup
        ret_months (int): Number of months to keep the backup
        ret_years (int): Number of years to keep the backup
        dry_run (bool): if True, run the script in dry run mode

    Return:
        List of error messages
    """
    msgs = []

    # Set repo parameters
    restic.repository = repo
    restic.password_file = pw_file

    # Remove old snapshots
    try:
        logger.info(f'Running cleanup for {repo}...')
        result = restic.forget(
            prune=True,
            keep_daily=ret_days,
            keep_weekly=ret_weeks,
            keep_monthly=ret_months,
            keep_yearly=ret_years,
            dry_run=dry_run
        )
    except restic.errors.ResticFailedError as e:
        msg =f'Cleanup for {repo} failed.'
        logger.exception(msg)
        msgs.append(msg)
    else:
        logger.info(f'Cleanup for {repo} completed successfully.')
        logger.debug(f'Cleanup result for {repo}\n{pformat(result)}')

    return msgs

# TODO Add check method