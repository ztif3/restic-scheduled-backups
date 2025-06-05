#!/usr/bin/env python3
import logging

from multiprocessing import Queue
from pathlib import Path
from typing import Optional

from restic_scheduled_backups.config_def import BackupTaskConfig, NtfyConfig
from restic_scheduled_backups.tasks.backup_task import BackupTask
from restic_scheduled_backups.util.backup import data_backup
from restic_scheduled_backups.util.containers import start_container, stop_container
from restic_scheduled_backups.util.system import *

import restic_scheduled_backups.common

logger = logging.getLogger(__name__)

class DCBackupTask(BackupTask):
    """ Backup task that backs up a docker compose container's filesystem """

    def __init__(self, name: str, task_config: BackupTaskConfig, task_queue:Queue, no_cloud: bool=False, ntfy_config: Optional[NtfyConfig] = None):
        """ Constructor

        Args:
            name (str): name of the task.
            task_config (BackupTaskConfig): configuration for the task.
            no_cloud (bool, optional): whether to slip the cloud backup. Defaults to False.
            ntfy_config (Optional[NtfyConfig], optional): configuration for notifications. Defaults to None.
        """
        super().__init__(name, task_config, task_queue, no_cloud, ntfy_config)


    def source_backup(self, primary_repo_path: Path) -> list[str]:
        """
        Perform a backup of the source directories to the primary repo.

        Args:
            primary_repo_path (Path): The path to the primary repository.

        Returns:
            list[str]: A list of messages generated during the backup process.
        """

        msgs = [] 

        for path in self.paths:
            # Generate path to the data source
            src_path = Path(self.root_dir) / path

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

        return msgs