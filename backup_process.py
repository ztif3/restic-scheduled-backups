#!/usr/bin/env python3
import argparse
import logging

from json import load
from os import PathLike
from pathlib import Path
from subprocess import CalledProcessError
from multiprocessing import Process
from logging.config import dictConfig

import time
import schedule

from backup import clean_repo, copy_repo, data_backup, init_repo
from containers import start_container, stop_container
from system import list_mounted_partitions
import common

process_list = []

logger = logging.getLogger(__name__)


def get_config_backups(config_path: PathLike) -> list[dict]:
    """ Gets a list of backup tasks from the config file

    Args:
        config_path (PathLike): path to the config file

    Returns:
        list[dict]: list of dictionaries for each backup tasks
    """

    backups = []

    # Ensure config is a Path object
    if not isinstance(config_path, Path):
        config_path = Path(config_path)

    # Open config path
    with open(config_path, 'r') as f:
        config = load(f)

        # Read default config
        def_period = None
        def_repo_roots = None
        def_retention = None

        if 'def' in config:
            if 'period' in config['default']:
                # TODO Validate default period
                def_period = config['default']['period']
            else:
                logger.debug(f'No default period in "{config_path}"')

            if 'repo_roots' in config['default']:
                # TODO Validate default repo roots
                def_repo_roots = config['default']['repo_roots']
            else:
                logger.debug(f'No default repo_roots in "{config_path}"')

            if 'retention' in config['default']:
                # TODO Validate default retention policy
                def_retention = config['default']['repo_roots']
            else:
                logger.debug(f'No default retention in "{config_path}"')
        else:
            logger.debug(f'No default settings exist in "{config_path}"')

        # Get backups
        if 'backups' in config:
            backups = config['backups']
        else:
            logger.warning(f'No Backups present in "{config_path}"')

        # Ensure all backups have repo_roots and retention settings
        for backup in backups:
            # TODO Validate backup config

            if 'period' not in backup:
                backup['period'] = def_period
            else:
                # TODO Validate period
                pass

            if 'repo_roots' not in backup:
                backup['repo_roots'] = def_repo_roots
            else:
                # TODO Validate repo roots
                pass

            
            if 'retention' not in backup:
                backup['retention'] = def_retention
            else:
                # TODO Validate retention policy
                pass

    return backups

def start_backup(proc:Process):
    """ Starts a backup process

    Args:
        proc (Process): Backup process
    """

    if not proc.is_alive():
        proc.start()

def run_backup(backup:dict):
    """ Runs a backup process

    Args:
        backup (dict): backup settings
    """

    # Get paths to available local repos
    local_repos = []
    for local_device in backup['repo_roots']['local_devices']:
        mount_list = list_mounted_partitions()
        if local_device in mount_list:
            local_repos.append(Path(mount_list[0]) / backup['repo'])

    if len(local_repos) > 0:
        # Get remote repos paths
        cloud_repos = []
        if 'local_devices' in backup['repo_roots']:
            for cloud_repo in backup['repo_roots']['local_devices']:
                cloud_repos.append(f'{cloud_repo}/{backup["repo"]}')

        # TODO Fallback to other local repos if first repo doesn't exist
        # TODO Synchronize local repos before starting backup
        # TODO handle errors from repo

        pw_file = backup['pw_file']
        ret_days = backup['retention']['days']
        ret_weeks = backup['retention']['weeks']
        ret_months = backup['retention']['months']
        ret_years = backup['retention']['years']

        # Initialize first local repo if necessary
        first_repo = local_repos[0]
        init_repo(first_repo, backup['pw_file'])

        # Run first backup
        if 'paths' in backup:
            data_backup(
                repo=first_repo,
                pw_file = pw_file,
                paths = [Path(backup['root']) / path for path in backup['paths']]
            )

        if 'containers' in backup:
            for container in backup['containers']:
                try:
                    stop_container(container)
                except CalledProcessError as e:
                    pass
                    # TODO Improve error handling for container stop

                # Run the backup
                data_backup(
                    repo=first_repo,
                    pw_file=pw_file,
                    paths=[container]
                )

                try:
                    start_container(container)
                except CalledProcessError as e:
                    pass
                    # TODO Improve error handling for container starting

        # Cleanup first repo
        clean_repo(
            repo=first_repo,
            pw_file = pw_file,
            ret_days = ret_days,
            ret_weeks = ret_weeks,
            ret_months = ret_months,
            ret_years = ret_years
        )

        # Copy first repo to all local repos
        for i in range(1,len(local_repos)):
            # Initialize first local repo if necessary
            init_repo(local_repos[i], pw_file)

            # Run first backup
            copy_repo(
                src_repo=first_repo,
                dst_repo=local_repos[i],
                pw_file=pw_file
            )

            # Cleanup first repo
            clean_repo(
                repo= local_repos[i],
                pw_file = pw_file,
                ret_days = ret_days,
                ret_weeks = ret_weeks,
                ret_months = ret_months,
                ret_years = ret_years
            )

        # Copy first repo to all cloud repos
        for cloud_repo in cloud_repos:
            # Initialize first local repo if necessary
            init_repo(cloud_repo, pw_file)

            # Run first backup
            copy_repo(
                src_repo=first_repo,
                dst_repo=cloud_repo,
                pw_file=pw_file
            )

            # Cleanup first repo
            clean_repo(
                repo= cloud_repo,
                pw_file = pw_file,
                ret_days = ret_days,
                ret_weeks = ret_weeks,
                ret_months = ret_months,
                ret_years = ret_years
            )

    else:
        logger.error(f'No local repositories available for backup root {backup['root']}')


def main():
    """  Main method for starting the backup process """    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run data backup script.')

    parser.add_argument('config_file', type=PathLike, help='Configuration JSON File')
    parser.add_argument('--debug', action='store_true', help='Show debug logging level')

    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get config path
    if args.config_file is not None:
        config_path = Path(args.config_file)

        if config_path.exists():
            backups = get_config_backups(config_path)

            proc_list = []

            for backup in backups:
                period_type = 'days'
                
                if 'period_type' in backups['period']:
                    period_type = backups['period']['period_type']
                
                match(period_type.lower()):
                    case 'days':

                        frequency= 1
                        run_time = '00:00'

                        if 'frequency' in backups['period']:
                            frequency = int(backups['period']['frequency'])

                        if 'run_time' in backups['period']:
                            run_time = backups['period']['run_time']
                        
                        proc = Process(target=run_backup, args=(backup, ))
                        proc_list.append(proc)
                        schedule.every(frequency).day.at(run_time).do(start_backup, proc=proc)
                        logger.info(f'Scheduling a backup for {backup['root']} every {frequency} days at {run_time}')
                    case _:
                        logger.warning(f'Unsupported period_type {period_type} found, backup task for root {backup['root']}')

            # Run Schedule tasks
            logger.info('Starting scheduler loop')
            while True: # TODO Provide end conditions
                schedule.run_pending()
                time.sleep(1)
        else:
            logger.error(f'Config file "{config_path}" does not exist.')

    else:
        logger.error('No config file provided.')


if __name__ == '__main__':
    main()