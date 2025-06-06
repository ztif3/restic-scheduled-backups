import logging
from multiprocessing import Queue
from pathlib import Path
from typing import Optional
from restic_scheduled_backups.config_def import CheckTaskConfig
from restic_scheduled_backups.tasks.task_base import TaskBase
from restic_scheduled_backups.util import ntfy
from restic_scheduled_backups.util.backup import check_repo
from restic_scheduled_backups.util.system import list_mounted_partitions

import restic_scheduled_backups.common

logger = logging.getLogger(__name__)


class CheckTask(TaskBase):
    def __init__(self, name: str, task_config: CheckTaskConfig, task_queue: Queue, ntfy_config: Optional[ntfy.NtfyConfig]=None):
        super().__init__(name, task_config, task_queue, ntfy_config)
        self.read_data = task_config.read_data
        self.subset = task_config.subset

    def run(self):
        
        mount_list = list_mounted_partitions()

        for repo_root in self.repo_roots.local_devices:
            msgs = []
            if repo_root.device_id in mount_list:
                repo_path = Path(mount_list[repo_root.device_id][0]) / self.repo_name

                # Check the repository
                msgs = check_repo(repo_path, self.pw_file, read_data=False)

                if self.ntfy_config is not None:
                    if len(msgs) > 0:
                        prefix = ("An Error", "Errors")[len(msgs) > 1]
                        
                        ntfy.ntfy_message(self.ntfy_config, f'[{prefix}] while running read data check task  {self.name} - {repo_path}', '\n'.join(msgs), ntfy.NtfyPriorityLevel.HIGH)
            else:
                msg = f"Local repo device {repo_root.device_id} has no mount points"
                logger.error(msg)
                if self.ntfy_config is not None:
                    ntfy.ntfy_message(self.ntfy_config, f'Error while running read data check task {self.name}', msg, ntfy.NtfyPriorityLevel.HIGH)
        
        if self.repo_roots.cloud_repos is not None:
            for repo_root in self.repo_roots.cloud_repos:
                repo_path = f'{repo_root}/{self.repo_name}'


                # Check the repository
                msgs = check_repo(repo_path, self.pw_file, read_data=False)

                if self.ntfy_config is not None:
                    if len(msgs) > 0:
                        prefix = ("An Error", "Errors")[len(msgs) > 1]
                        
                        ntfy.ntfy_message(self.ntfy_config, f'[{prefix}] while running read data check task  {self.name} - {repo_path}', '\n'.join(msgs), ntfy.NtfyPriorityLevel.HIGH)
                

