#!/usr/bin/env python3
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

from backup import clean_repo, copy_repo, data_backup, init_repo
from config_def import *
from containers import start_container, stop_container
from system import *



def run_backups(tasks: list['BackupTask']):
    """ Run backups for each task
    Args:
        tasks (list[BackupTask]): list of backup tasks
    """
    while True:
        task = task_queue.get()
        task.run()

update_process = Process(target=run_backups)

import common

logger = logging.getLogger(__name__)

task_queue = Queue()

class LocalDevice:
    """ Stores information about a local device """

    def __init__(self, name: str, dev_id: str):
        """ Initializes local device with a name and list of mountpoints

        Args:
            name (str): device name
            dev_id (str): device name
        """
        self.name = name
        self.dev_id = dev_id


class CloudDevice:
    """ Determines a cloud device    """

    class Type(str, Enum):
        S3_COMPATIBLE = "s3-compatible"

        def __str__(self) -> str:
            return self.value
            
        @staticmethod
        def from_str(value: str) -> 'CloudDevice.Type':
            for e in CloudDevice.Type:
                if e.value.lower() == value.lower():
                    return e
            raise ValueError(f"Invalid type {value}")

    def __init__(self, name: str, type: str, path: ParseResult, key_id: str, key: str):
        self.name = name
        self.type = type
        self.path = path
        self.key_id = key_id
        self.key = key


class BackupTask:
    """ Represents a single backup task """
    class Type(str, Enum):
        STANDARD="standard"
        CONTAINER="container"

        def __str__(self) -> str:
            return self.value
            
        @staticmethod
        def from_str(value: str) -> 'CloudDevice.Type':
            for e in CloudDevice.Type:
                if e.value.lower() == value.lower():
                    return e
            raise ValueError(f"Invalid type {value}")

    def __init__(self,
                 name: str,
                 local_devices: list[LocalDeviceConfig],
                 repo_name: str,
                 root_dir: PathLike,
                 pw_file: PathLike,
                 paths: list[str],
                 update_period: PeriodConfig = PeriodConfig(type=PeriodType.DAILY),
                 retention_period: RetentionConfig = RetentionConfig(),
                 cloud_repos: list[CloudRepoConfig] = [],
                 task_type: 'BackupTask.Type' = Type.STANDARD
    ):
        """ Constructor

        Args:
            name (str): name of the task
            local_devices (dict[str, str]): list of local repo roots
            repo_name (str): name of the repository
            root_dir (PathLike): root directory for the data to be backed up
            pw_file (PathLike): path to the password file 
            paths (list[str]): list of child paths to be backed up
            update_period (UpdatePeriod, optional): update period for the data to be backed up. Defaults to UpdatePeriod(UpdatePeriod.Type.DAILY).
            retention_period (RetentionPeriod, optional): retention period for the data to be backed up. Defaults to RetentionPeriod().
            cloud_repos (list[CloudDevice], optional): list of cloud repo roots. Defaults to [].
            task_type (BackupTask.Type, optional): type of the backup task. Defaults to Type.STANDARD.
        """

        if not isinstance(root_dir, Path):
            root_dir = Path(root_dir)

        if not isinstance(pw_file, Path):
            pw_file = Path(pw_file)
        
        self.name = name
        self.local_devices = local_devices
        self.repo_name = repo_name
        self.root_dir = root_dir
        self.pw_file = pw_file
        self.paths = paths
        self.retention_period = retention_period
        self.cloud_repos = cloud_repos
        self.task_type = task_type
        self.proc = Process(target=self.run)
        self.scheduled = False

        
        # Queue task
        match(update_period.type):
            case PeriodType.HOURLY:
                schedule.every(update_period.frequency).hours.at(update_period.run_time).do(self.schedule)
            case PeriodType.DAILY:
                schedule.every(update_period.frequency).days.at(update_period.run_time).do(self.schedule)
            case PeriodType.WEEKLY:
                schedule.every(update_period.frequency).weeks.at(update_period.run_time).do(self.schedule)
        

    def schedule(self):
        """ Schedule the task """
        if not self.scheduled:
            task_queue.put(self)
            logging.debug(f'Scheduled {self.name}')
            self.scheduled = True

    def run(self):
        """ Run the task """
        
        mount_list = list_mounted_partitions()
        
        logger.info(f"Starting task {self.name}")
        try:
            if len(self.local_devices) > 0:
                # Get primary repo
                primary_repo = self.local_devices[0]

                for repo in self.local_devices:
                    if repo.primary:
                        primary_repo = repo
                        break

                primary_repo_path = self.primary_backup(primary_repo, mount_list)
        
                # Copy backup to other local repos
                if len(self.local_devices) > 1:
                    for repo in self.local_devices[1:]:
                        self.local_backup(primary_repo_path, repo, mount_list)

                for repo in self.cloud_repos:
                    self.cloud_backup(primary_repo_path, repo)        
        except:
            logger.exception("Unable to run backup")

        
        logger.info(f"Finished task {self.name}")
        self.scheduled = False


    def primary_backup(self, repo: LocalDeviceConfig, mount_list:Optional[dict[str, list[PathLike]]] = None) -> Path:
        """ Runs the backup from the source data to the primary backup device

        Args:
            repo (LocalDevice): primary backup device
            mount_list (Optional[dict[str, list[PathLike]]]): List of mounted partitions. If None or omitted, list_mount_partitions() is called.

        Returns:
            Path: Path to the primary backup device.
        
        Errors;
            RuntimeError: If primary repo device is not mounted.
        """
        if mount_list is None:
            mount_list = list_mounted_partitions()
    
        if repo.device_id in mount_list:
            mount_points = mount_list[repo.device_id]

            if mount_points is not None and len(mount_points) > 0:
                primary_repo_path = Path(mount_points[0]) / self.repo_name
                    
                # TODO Unlock repo if necessary. Must be added to resticpy

                # Initialize repo if necessary
                init_repo(primary_repo_path, self.pw_file)
                    
                # Backup data
                match(self.task_type):
                    case BackupTask.Type.STANDARD:
                        data_backup(primary_repo_path, self.pw_file, [self.root_dir / p for p in self.paths])
                    case BackupTask.Type.CONTAINER:
                        for path in self.paths:
                            # Generate path to the data source
                            src_path = self.root_dir / path

                            # If container task type, stop container before running backup
                            stop_container(src_path)

                            # Run backup to primary repo
                            data_backup(primary_repo_path, self.pw_file, [src_path])

                            # If container task type, start container after running backup
                            start_container(src_path)
                    
                # Clean primary repo
                clean_repo(
                    primary_repo_path, 
                    self.pw_file, 
                    self.retention_period.days, 
                    self.retention_period.weeks, 
                    self.retention_period.months, 
                    self.retention_period.years
                )

                return primary_repo_path

            else:
                raise RuntimeError(f"Primary repo device {repo.device_id} has no mount points")

        else:
            raise RuntimeError(f"Primary repo device {repo.device_id} is not mounted")

    def local_backup(self, primary_repo_path: Path,  repo:LocalDeviceConfig, mount_list:Optional[dict[str, list[PathLike]]] = None):
        """ Copies the backup from the primary repo to another local device repo

        Args:
            primary_repo_path (Path): primary repository path
            repo (LocalDevice): local device to backup to
            mount_list (Optional[dict[str, list[PathLike]]]): List of mounted partitions. If None or omitted, list_mount_partitions() is called.
        """

        if mount_list is None:
            mount_list = list_mounted_partitions()

        if repo.device_id in mount_list:
            mount_points = mount_list[repo.device_id]

            if mount_points is not None and len(mount_points) > 0:
                repo_path = Path(mount_points[0]) / self.repo_name
    
                # TODO Unlock repo if necessary. Must be added to resticpy

                # Initialize repo if necessary
                init_repo(repo_path, self.pw_file)

                # Copy data from primary repo to local repo
                copy_repo(primary_repo_path, repo_path, self.pw_file)

                # Clean up local repo
                clean_repo(
                    repo_path, 
                    self.pw_file, 
                    self.retention_period.days, 
                    self.retention_period.weeks, 
                    self.retention_period.months, 
                    self.retention_period.years
                )
            else:
                logger.error(f"Local repo device {repo.device_id} has no mount points")
        else:
            logger.error(f"Local repo device {repo.device_id} is not mounted")

    def cloud_backup(self, primary_repo_path: Path, repo:CloudRepoConfig):
        """ Backup data from the primary repo to a cloud device.

        Args:
            primary_repo_path (Path): path to the primary restic repo
            repo (CloudRepoConfig): cloud device to backup data to
        """
                
        repo_path = repo.get_restic_path()
        
        # TODO Unlock repo if necessary. Must be added to resticpy

        # Initialize repo if necessary
        init_repo(repo_path, self.pw_file)

        # Copy data from primary repo to local repo
        copy_repo(primary_repo_path, repo_path, self.pw_file)

        # Clean up local repo
        clean_repo(
            repo_path, 
            self.pw_file, 
            self.retention_period.days, 
            self.retention_period.weeks, 
            self.retention_period.months, 
            self.retention_period.years
        )

def create_backup_tasks(config: BackupConfig) -> list[BackupTask]:
    """ Get list of backup tasks from config dictionary

    Args:
        config (dict): config dictionary

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
            raise ValueError(f"Backup task {name} has no local devices defined")

        task = BackupTask(
            name = name,
            local_devices= local_devices,
            repo_name = task_config.repo,
            root_dir= task_config.root, 
            pw_file= task_config.pw_file,
            paths=task_config.paths,
            update_period=period,
            retention_period=retention,
            cloud_repos=cloud_repos
        )

        tasks.append(task)
    return []

def main():
    """  Main method for starting the backup process """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run data backup script.')

    parser.add_argument('config_file', type=PathLike,
                        help='Configuration JSON File')
    parser.add_argument('--debug', action='store_true',
                        help='Show debug logging level')

    args = parser.parse_args()

    # Configure logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get config path
    if args.config_file is not None:
        config_path = Path(args.config_file)

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
                    tasks = create_backup_tasks(config)
                except:
                    logger.exception(f'Failed to create backup tasks')
                    raise
                
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
