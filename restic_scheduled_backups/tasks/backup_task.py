#!/usr/bin/env python3
import argparse
from enum import Enum
import logging

from os import PathLike
from pathlib import Path

import schedule

from restic_scheduled_backups.util import ntfy
from restic_scheduled_backups.util.backup import clean_repo, copy_repo, data_backup, init_repo, unlock_repo
from restic_scheduled_backups.config_def import *
from restic_scheduled_backups.util.containers import start_container, stop_container
from restic_scheduled_backups.util.ntfy import NtfyPriorityLevel, ntfy_message
from restic_scheduled_backups.util.system import *

from restic_scheduled_backups.tasks import task_queue

import restic_scheduled_backups.common

logger = logging.getLogger(__name__)

class BackupTask:
    def __init__(self,
                 name: str,
                 repo_roots: RepoConfig,
                 repo_name: str,
                 root_dir: PathLike,
                 pw_file: PathLike,
                 paths: list[str],
                 update_period: PeriodConfig = PeriodConfig(type=PeriodType.DAILY),
                 retention_period: RetentionConfig = RetentionConfig(),
                 task_type: BackupType = BackupType.STANDARD,
                 no_cloud: bool = False,
                 ntfy_config: Optional[NtfyConfig] = None,
    ):
        """ Constructor

        Args:
            name (str): name of the task
            repo_roots  (RepoConfig): root directories for the various repositories
            repo_name (str): name of the repository
            root_dir (PathLike): root directory for the data to be backed up
            pw_file (PathLike): path to the password file 
            paths (list[str]): list of child paths to be backed up
            update_period (UpdatePeriod, optional): update period for the data to be backed up. Defaults to UpdatePeriod(UpdatePeriod.Type.DAILY).
            retention_period (RetentionPeriod, optional): retention period for the data to be backed up. Defaults to RetentionPeriod().
            cloud_repos (list[CloudDevice], optional): list of cloud repo roots. Defaults to [].
            task_type (BackupType, optional): type of the backup task. Defaults to BackupType.STANDARD.
            no_cloud (bool, optional): whether to slip the cloud backup. Defaults to False.
        """

        if not isinstance(root_dir, Path):
            root_dir = Path(root_dir)

        if not isinstance(pw_file, Path):
            pw_file = Path(pw_file)
        
        self.name = name
        self.repo_roots = repo_roots
        self.repo_name = repo_name
        self.root_dir = root_dir
        self.pw_file = pw_file
        self.paths = paths
        self.update_period = update_period
        self.retention_period = retention_period
        self.task_type = task_type
        self.no_cloud = no_cloud
        self.ntfy_config = ntfy_config

        self.scheduled = False


    def schedule(self) -> None:
        logger.info(f'Scheduling task: {self.name} - {self.update_period.type} - freq:{self.update_period.frequency} - at:{self.update_period.run_time}')
        # Queue task
        match(self.update_period.type):
            case PeriodType.HOURLY:
                schedule.every(self.update_period.frequency).hours.do(self.__queue_task)
            case PeriodType.DAILY:
                schedule.every(self.update_period.frequency).days.at(self.update_period.run_time).do(self.__queue_task) 
            case PeriodType.WEEKLY:
                match(self.update_period.weekday):
                    case WeekdayType.SUNDAY:
                        schedule.every(self.update_period.frequency).sunday.at(self.update_period.run_time).do(self.__queue_task)
                    case WeekdayType.MONDAY:
                        schedule.every(self.update_period.frequency).monday.at(self.update_period.run_time).do(self.__queue_task)
                    case WeekdayType.TUESDAY:
                        schedule.every(self.update_period.frequency).tuesday.at(self.update_period.run_time).do(self.__queue_task)
                    case WeekdayType.WEDNESDAY:
                        schedule.every(self.update_period.frequency).wednesday.at(self.update_period.run_time).do(self.__queue_task)
                    case WeekdayType.THURSDAY:
                        schedule.every(self.update_period.frequency).thursday.at(self.update_period.run_time).do(self.__queue_task)
                    case WeekdayType.FRIDAY:
                        schedule.every(self.update_period.frequency).friday.at(self.update_period.run_time).do(self.__queue_task)
                    case WeekdayType.SATURDAY:
                        schedule.every(self.update_period.frequency).saturday.at(self.update_period.run_time).do(self.__queue_task) 
                    case _:
                        schedule.every(self.update_period.frequency).weeks.at(self.update_period.run_time).do(self.__queue_task)
        
    def __queue_task(self):
        """ Schedule the task """
        if not self.scheduled:
            task_queue.put(self)
            logging.info(f'queued task: {self.name}')
            self.scheduled = True

    def run(self):
        """ Run the task """
        
        mount_list = list_mounted_partitions()
        
        logger.info(f"Starting task {self.name}")
        try:
            if len(self.repo_roots.local_devices) > 0:
                # Get primary repo
                primary_repo = None

                for repo in self.repo_roots.local_devices:
                    if repo.primary:
                        primary_repo = repo
                        break
                    
                if primary_repo is not None:
                    primary_repo_path = self.primary_backup(primary_repo, mount_list)
            
                    # Copy backup to other local repos
                    if len(self.repo_roots.local_devices) > 1:
                        for repo in self.repo_roots.local_devices[1:]:
                            self.local_backup(primary_repo_path, repo, mount_list)

                    if not self.no_cloud and self.repo_roots.cloud_repos is not None:
                        for repo in self.repo_roots.cloud_repos:
                            self.cloud_backup(primary_repo_path, repo)   

                    if self.ntfy_config is not None:
                        ntfy_message(self.ntfy_config, "Backup Complete", f"Backup completed for {self.name}", NtfyPriorityLevel.LOW)
                else:
                    if self.ntfy_config is not None:
                        ntfy_message(self.ntfy_config, "Backup Failed", f"No primary device found for {self.name}", NtfyPriorityLevel.HIGH)
            else:
                
                    if self.ntfy_config is not None:
                        ntfy_message(self.ntfy_config, "Backup Failed", f"No local devices found for {self.name}", NtfyPriorityLevel.HIGH)
        except:
            logger.exception("Unable to run backup")
            
            if self.ntfy_config is not None:
                ntfy_message(self.ntfy_config, "Backup Failed", f"Error occurred during backup for {self.name}", NtfyPriorityLevel.HIGH)

        
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
        msgs = []  

        if mount_list is None:
            mount_list = list_mounted_partitions()
    
        if repo.device_id in mount_list:
            mount_points = mount_list[repo.device_id]

            if mount_points is not None and len(mount_points) > 0:
                primary_repo_path = Path(mount_points[0]) / self.repo_name

                # Initialize repo if necessary
                msgs.extend(init_repo(primary_repo_path, self.pw_file))

                # Unlock repo if necessary
                unlock_repo(primary_repo_path, self.pw_file)  

                # Backup data
                match(self.task_type):
                    case BackupType.STANDARD:
                        msgs.extend(data_backup(primary_repo_path, self.pw_file, [self.root_dir / p for p in self.paths]))
                    case BackupType.DOCKER_COMPOSE:
                        for path in self.paths:
                            # Generate path to the data source
                            src_path = self.root_dir / path

                            # If container task type, stop container before running backup
                            try:
                                stop_container(src_path)
                            except subprocess.CalledProcessError as e:
                                logger.exception(f'Error while stopping container at path {src_path}')
                        
                            # Run backup to primary repo
                            msgs.extend(data_backup(primary_repo_path, self.pw_file, [src_path]))

                            # If container task type, start container after running backup
                            try:
                                start_container(src_path)
                            except subprocess.CalledProcessError as e:
                                logger.exception(f'Error while starting container at path {src_path}')
                    
                # Clean primary repo
                msgs.extend(
                    clean_repo(
                        primary_repo_path, 
                        self.pw_file, 
                        self.retention_period.days, 
                        self.retention_period.weeks, 
                        self.retention_period.months, 
                        self.retention_period.years
                    )
                )

                if self.ntfy_config is not None:
                    if len(msgs) > 0:
                        prefix = ("An Error", "Errors")[len(msgs) > 1]
                        
                        ntfy.ntfy_message(self.ntfy_config, f'[{prefix}] while running backup task {self.name} - {primary_repo_path}', '\n'.join(msgs), NtfyPriorityLevel.HIGH)

                return primary_repo_path

            else:
                msg = f"Primary repo device {repo.device_id} has no mount points"
                if self.ntfy_config is not None:
                    ntfy.ntfy_message(self.ntfy_config, f'Error backup up to primary repo for {self.name}', msg, NtfyPriorityLevel.HIGH)
                raise RuntimeError(msg)

        else:
            msg = f"Primary repo device {repo.device_id} is not mounted"
            if self.ntfy_config is not None:
                ntfy.ntfy_message(self.ntfy_config, f'Error backup up to primary repo for {self.name}', msg, NtfyPriorityLevel.HIGH)
            raise RuntimeError(f"Primary repo device {repo.device_id} is not mounted")

    def local_backup(self, primary_repo_path: Path,  repo:LocalDeviceConfig, mount_list:Optional[dict[str, list[PathLike]]] = None):
        """ Copies the backup from the primary repo to another local device repo

        Args:
            primary_repo_path (Path): primary repository path
            repo (LocalDevice): local device to backup to
            mount_list (Optional[dict[str, list[PathLike]]]): List of mounted partitions. If None or omitted, list_mount_partitions() is called.
        """

        msgs = []
        
        if mount_list is None:
            mount_list = list_mounted_partitions()

        if repo.device_id in mount_list:
            mount_points = mount_list[repo.device_id]

            if mount_points is not None and len(mount_points) > 0:
                repo_path = Path(mount_points[0]) / self.repo_name

                # Initialize repo if necessary
                msgs.extend(init_repo(repo_path, self.pw_file))

                # Unlock repo if necessary
                unlock_repo(primary_repo_path, self.pw_file)  

                # Copy data from primary repo to local repo
                msgs.extend(copy_repo(primary_repo_path, repo_path, self.pw_file))

                # Clean up local repo
                msgs.extend(
                    clean_repo(
                        repo_path, 
                        self.pw_file, 
                        self.retention_period.days, 
                        self.retention_period.weeks, 
                        self.retention_period.months, 
                        self.retention_period.years
                    )
                )


                if self.ntfy_config is not None:
                    if len(msgs) > 0:
                        prefix = ("An Error", "Errors")[len(msgs) > 1]
                        
                        ntfy.ntfy_message(self.ntfy_config, f'[{prefix}] while running backup task {self.name} - {repo_path}', '\n'.join(msgs), NtfyPriorityLevel.HIGH)
                
            else:
                msg = f"Local repo device {repo.device_id} has no mount points"
                logger.error(msg)
                if self.ntfy_config is not None:
                    ntfy.ntfy_message(self.ntfy_config, f'Error backup up to {primary_repo_path}', msg, NtfyPriorityLevel.HIGH)
        else:
            msg = f"Local repo device {repo.device_id} is not mounted"
            logger.error(msg)
            if self.ntfy_config is not None:
                ntfy.ntfy_message(self.ntfy_config, f'Error backup up to {primary_repo_path}', msg, NtfyPriorityLevel.HIGH)

    def cloud_backup(self, primary_repo_path: Path, repo:CloudRepoConfig):
        """ Backup data from the primary repo to a cloud device.

        Args:
            primary_repo_path (Path): path to the primary restic repo
            repo (CloudRepoConfig): cloud device to backup data to
        """
        msgs = []
        repo.set_cloud_keys_evs()
        repo_root = repo.get_restic_path()
        if repo_root[-1] != '/':
            repo_root += '/'

        repo_path = f'{repo_root}{self.repo_name}'

        # Initialize repo if necessary
        msgs.extend(init_repo(repo_path, self.pw_file))

        # Unlock repo if necessary
        unlock_repo(primary_repo_path, self.pw_file)  

        # Copy data from primary repo to local repo
        msgs.extend(copy_repo(primary_repo_path, repo_path, self.pw_file))

        # Clean up local repo
        msgs.extend(
            clean_repo(
                repo_path, 
                self.pw_file, 
                self.retention_period.days, 
                self.retention_period.weeks, 
                self.retention_period.months, 
                self.retention_period.years
            )
        )

        if self.ntfy_config is not None:
            if len(msgs) > 0:
                prefix = ("An Error", "Errors")[len(msgs) > 1]
                
                ntfy.ntfy_message(self.ntfy_config, f'[{prefix}] while running backup task {self.name} - {repo_path}', '\n'.join(msgs), NtfyPriorityLevel.HIGH)