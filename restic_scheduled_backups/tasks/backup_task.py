#!/usr/bin/env python3
import logging

from os import PathLike
from pathlib import Path
from typing import Optional


from restic_scheduled_backups.tasks.task_base import TaskBase
from restic_scheduled_backups.util import ntfy
from restic_scheduled_backups.util.backup import clean_repo, copy_repo, data_backup, init_repo, unlock_repo
from restic_scheduled_backups.config_def import BackupTaskConfig, LocalDeviceConfig, CloudRepoConfig, NtfyConfig
from restic_scheduled_backups.util.ntfy import NtfyPriorityLevel, ntfy_message
from restic_scheduled_backups.util.system import *

import restic_scheduled_backups.common

logger = logging.getLogger(__name__)

class BackupTask(TaskBase):
    def __init__(self, name: str, task_config: BackupTaskConfig, no_cloud: bool=False, ntfy_config: Optional[NtfyConfig] = None):
        """ Constructor

        Args:
            name (str): name of the task.
            task_config (BackupTaskConfig): configuration for the task.
            no_cloud (bool, optional): whether to slip the cloud backup. Defaults to False.
            ntfy_config (Optional[NtfyConfig], optional): configuration for notifications. Defaults to None.
        """
        super().__init__(name, task_config, ntfy_config)
        self.paths = task_config.paths
        self.retention_period = task_config.retention
        self.no_cloud = no_cloud


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
                msgs.extend(self.source_backup(primary_repo_path))
                    
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


    def source_backup(self, primary_repo_path: Path) -> list[str]:
        """
        Perform a backup of the source directories to the primary repo.

        Args:
            primary_repo_path (Path): The path to the primary repository.

        Returns:
            list[str]: A list of messages generated during the backup process.
        """
        return data_backup(primary_repo_path, self.pw_file, [Path(self.root_dir) / p for p in self.paths])