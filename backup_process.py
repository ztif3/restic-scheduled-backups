#!/usr/bin/env python3
import common
import argparse
from enum import Enum
import logging

from json import load
from os import PathLike
import os
from pathlib import Path
from subprocess import CalledProcessError
from multiprocessing import Process, Queue

from urllib.parse import urlparse, ParseResult
import time
from pydantic import ValidationError
import schedule

from config_def import *
from util.ntfy import NtfyPriorityLevel, ntfy_message
from util.system import *
from tasks import task_queue
from tasks.backup_task import BackupTask


def run_backups(tasks: list['BackupTask']):
    """ Run backups for each task
    Args:
        tasks (list[BackupTask]): list of backup tasks
    """
    while True:
        task = task_queue.get()
        task.run()


update_process = Process(target=run_backups)


logger = logging.getLogger(__name__)

task_queue = Queue()


def create_backup_tasks(config: BackupConfig, no_cloud: bool = False) -> list[BackupTask]:
    """ Get list of backup tasks from config dictionary

    Args:
        config (dict): config dictionary
        no_cloud (bool): If True, skip cloud backups. Defaults to False.

    Returns:
        list[BackupTask]: list of backup tasks
    """
    def_period = None
    def_local = None
    def_cloud = None
    def_retention = None

    if config.default is not None:
        def_period = config.default.period
        def_local = config.default.local_devices
        def_cloud = config.default.cloud_repos
        def_retention = config.default.retention

    tasks = []

    for name, task_config in config.backups.items():
        period = task_config.period or def_period
        local_devices = task_config.local_devices or def_local
        cloud_repos = task_config.cloud_repos or def_cloud or []
        retention = task_config.retention or def_retention

        # Verify backup task has all required parameters
        if period is None:
            raise ValueError(f"Backup task {name} has no period defined")
        if retention is None:
            raise ValueError(f"Backup task {name} has no retention defined")
        if local_devices is None:
            raise ValueError(
                f"Backup task {name} has no local devices defined")

        task = BackupTask(
            name=name,
            local_devices=local_devices,
            repo_name=task_config.repo,
            root_dir=task_config.root,
            pw_file=task_config.pw_file,
            paths=task_config.paths,
            update_period=period,
            retention_period=retention,
            cloud_repos=cloud_repos,
            task_type=task_config.type or BackupType.STANDARD,
            no_cloud=no_cloud,
            ntfy_config=config.ntfy
        )

        tasks.append(task)

    return tasks


def main():
    """  Main method for starting the backup process """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run data backup script.')

    parser.add_argument('-c','--config', type=str,
                        help='Configuration JSON File.')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='Show debug logging level.')
    parser.add_argument('--immediate', action='store_true', default=False,
                        help='Run backup immediately instead of waiting for scheduled time.')
    parser.add_argument('--no_cloud', action='store_true', default=False,
                        help='Do not perform cloud backups.')
    parser.add_argument('-t', '--tasks', nargs='*',
                        help='Specify tasks to run. If omitted all tasks will be run.', required=False)

    args = parser.parse_args()

    # Configure logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get config path
    if args.config is not None:
        config_path = Path(args.config)

        if config_path.exists():
            # Load configuration from JSON file
            with open(config_path, 'r') as f:
                # Load the configuration
                try:
                    config = BackupConfig(**json.load(f))
                except ValidationError as e:
                    logger.exception(f'Invalid configuration')
                    raise

                # Get backup tasks based on the configuration
                try:
                    tasks = create_backup_tasks(config, args.no_cloud)
                except:
                    logger.exception(f'Failed to create backup tasks')

                    if config.ntfy is not None:
                        ntfy_message(config.ntfy, "Backup Failed",
                                     f"Unable to load tasks", NtfyPriorityLevel.HIGH)
                    raise
                
                # Get list of enabled tasks to run
                scheduled_tasks = tasks

                if len(args.tasks) > 0:
                    scheduled_tasks = [task for task in tasks if task.name in args.tasks]
                
                # Run tasks
                if args.immediate:
                    # Run backup tasks
                    for task in scheduled_tasks:
                        task.run()
                else:
                    # Schedule enable enabled
                    for task in scheduled_tasks:
                        task.schedule() 

                    # run scheduler
                    while True:
                        schedule.run_pending()
                        time.sleep(1)
        else:
            logger.error(f'Config file "{config_path}" does not exist.')

    else:
        logger.error('No config file provided.')


if __name__ == '__main__':
    main()
