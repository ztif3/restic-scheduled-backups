import logging
from multiprocessing import Queue

from restic_scheduled_backups.config_def import BackupConfig, TaskType
from restic_scheduled_backups.tasks.backup_task import BackupTask
from restic_scheduled_backups.tasks.check_task import CheckTask
from restic_scheduled_backups.tasks.container_backup_task import DCBackupTask
from restic_scheduled_backups.tasks.task_base import TaskBase

import restic_scheduled_backups.common

logger = logging.getLogger(__name__)

def create_tasks(config: BackupConfig, no_cloud: bool = False) -> list[TaskBase]:
    """ Get list of backup tasks from config dictionary

    Args:
        config (dict): config dictionary
        no_cloud (bool): If True, skip cloud backups. Defaults to False.

    Returns:
        list[BackupTask]: list of backup tasks
    """
    tasks = []

    for name, task_config in config.tasks.items():

        task = None
        match(task_config.type):
            case TaskType.DATA_BACKUP:
                task = BackupTask(
                    name=name,
                    task_config = task_config, # type: ignore
                    no_cloud=no_cloud,
                    ntfy_config=config.ntfy
                )
            case TaskType.DOCKER_COMPOSE_BACKUP:
                task = DCBackupTask(
                    name=name,
                    task_config = task_config, # type: ignore
                    no_cloud=no_cloud,
                    ntfy_config=config.ntfy
                )
            case TaskType.CHECK:
                task = CheckTask(
                    name=name,
                    task_config = task_config, # type: ignore
                    ntfy_config=config.ntfy
                )
            case _:
                logger.warning(f"Unknown task type for task {name}: {task_config.type}")

        tasks.append(task)

    return tasks