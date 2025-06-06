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
from restic_scheduled_backups.tasks import create_tasks
from restic_scheduled_backups.tasks.container_backup_task import DCBackupTask
from restic_scheduled_backups.util.ntfy import NtfyPriorityLevel, ntfy_message
from restic_scheduled_backups.util.system import *
from restic_scheduled_backups.tasks.backup_task import BackupTask

from pprint import pformat


def _run_backups(task_queue: Queue):
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
            task.run_base()

    logger.critical('Worker process completed')


task_queue = Queue()
task_queue_worker = Process(target=_run_backups, args=(task_queue,))

import restic_scheduled_backups.common

logger = logging.getLogger(__name__)

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
                    logger.info(f'Config file loaded successfully {config_path}: \n{pformat(config.model_dump())}')

                if not args.validate:
                    # Get backup tasks based on the configuration
                    try:
                        tasks = create_tasks(config, task_queue, args.no_cloud)
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

                            # Restart task queue worker if it has died
                            if not task_queue_worker.is_alive():
                                logger.warning('Task queue worker process has died. Restarting...')
                                task_queue_worker.start()

                            time.sleep(1)
        else:
            logger.error(f'Config file "{config_path}" does not exist.')

    else:
        logger.error('No config file provided.')
