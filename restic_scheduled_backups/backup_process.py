#!/usr/bin/env python3
from json import JSONDecodeError
import argparse
import logging

from pathlib import Path
from multiprocessing import Process, Queue

import time
from pydantic import ValidationError
import schedule

from restic_scheduled_backups.config_def import *
from restic_scheduled_backups.util.ntfy import NtfyPriorityLevel, ntfy_message
from restic_scheduled_backups.util.system import *
from restic_scheduled_backups.tasks import task_queue
from restic_scheduled_backups.tasks.backup_task import BackupTask


def run_backups():
    """ Run backups for each task
    Args:
        tasks (list[BackupTask]): list of backup tasks
    """
    logger.info('Task queue worker process started')

    while True:
        task = task_queue.get()

        if task is None:
            logger.info('Received None task, exiting worker process')
            break
        else:
            logger.info(f'Running task {task.name}')
            task.run()

    logger.critical('Worker process completed')


task_queue_worker = Process(target=run_backups)

import restic_scheduled_backups.common

logger = logging.getLogger(__name__)

def create_backup_tasks(config: BackupConfig, no_cloud: bool = False) -> list[BackupTask]:
    """ Get list of backup tasks from config dictionary

    Args:
        config (dict): config dictionary
        no_cloud (bool): If True, skip cloud backups. Defaults to False.

    Returns:
        list[BackupTask]: list of backup tasks
    """
    def_period = None
    def_repo_roots = None
    def_retention = None

    if config.default is not None:
        def_period = config.default.period
        def_repo_roots = config.default.repo_roots
        def_retention = config.default.retention

    tasks = []

    for name, task_config in config.backups.items():
        period = task_config.period or def_period
        repo_roots = task_config.repo_roots or def_repo_roots
        retention = task_config.retention or def_retention

        # Verify backup task has all required parameters
        if period is None:
            raise ValueError(f"Backup task {name} has no period defined")
        if retention is None:
            raise ValueError(f"Backup task {name} has no retention defined")
        if repo_roots is None:
            raise ValueError(
                f"Backup task {name} has no repo roots defined")

        task = BackupTask(
            name=name,
            repo_roots=repo_roots,
            repo_name=task_config.repo,
            root_dir=task_config.root,
            pw_file=task_config.pw_file,
            paths=task_config.paths,
            update_period=period,
            retention_period=retention,
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

    parser.add_argument('-c', '--config', type=str,
                        help='Configuration JSON File.')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='Show debug logging level.')
    parser.add_argument('--immediate', action='store_true', default=False,
                        help='Run backup immediately instead of waiting for scheduled time.')
    parser.add_argument('--no_cloud', action='store_true', default=False,
                        help='Do not perform cloud backups.')
    parser.add_argument('-t', '--tasks', nargs='*',
                        help='Specify tasks to run. If omitted all tasks will be run.', required=False)
    parser.add_argument('--validate', action='store_true',
                        default=False, help='Validate configuration and exit.')

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
                except JSONDecodeError as e:
                    logger.exception(f'Failed to parse configuration file {config_path}')
                    raise
                except UnicodeDecodeError as e:
                    logger.exception(f'Unicode decoding error in configuration file {config_path}')
                    raise
                except ValidationError as e:
                    logger.exception(f'Config file failed validation {config_path}')
                    raise
                else:
                    logger.info(f'Config file loaded successfully {config_path}')

                if not args.validate:
                    # Get backup tasks based on the configuration
                    try:
                        tasks = create_backup_tasks(config, args.no_cloud)
                    except:
                        logger.exception(f'Failed to create backup tasks')

                        if config.ntfy is not None:
                            ntfy_message(config.ntfy, "Backup Failed",
                                        f"Unable to load tasks", NtfyPriorityLevel.HIGH)
                        raise
                    else:
                        logger.info(f'{len(tasks)} Backup tasks created successfully')

                    # Get list of enabled tasks to run
                    scheduled_tasks = tasks

                    if args.tasks is not None and len(args.tasks) > 0:
                        scheduled_tasks = [
                            task for task in tasks if task.name in args.tasks]

                    # Run tasks
                    if args.immediate:
                        # Run backup tasks
                        for task in scheduled_tasks:
                            task.run()
                    else:
                        # Schedule enable enabled
                        for task in scheduled_tasks:
                            task.schedule()

                        # Start task queue worker process
                        task_queue_worker.start()

                        # run scheduler
                        while True:
                            schedule.run_pending()
                            time.sleep(1)
        else:
            logger.error(f'Config file "{config_path}" does not exist.')

    else:
        logger.error('No config file provided.')
