from enum import Enum
import os
from typing import Any, Optional
from pydantic import BaseModel, ValidationError, field_validator, model_validator


class PeriodType(str, Enum):
    """ Represents the type of update period """
    HOURLY = 'hourly'
    DAILY = 'daily'
    WEEKLY = 'weekly'


class WeekdayType(str, Enum):
    """ Represents the type of weekday """
    SUNDAY = 'sunday'
    MONDAY = 'monday'
    TUESDAY = 'tuesday'
    WEDNESDAY = 'wednesday'
    THURSDAY = 'thursday'
    FRIDAY = 'friday'
    SATURDAY = 'saturday'


class CloudType(str, Enum):
    S3_COMPATIBLE = "s3-compatible"


class TaskType(str, Enum):
    DATA_BACKUP = "data-backup"
    DOCKER_COMPOSE_BACKUP = "docker-compose-backup"
    CHECK = 'check'


class PeriodConfig(BaseModel):

    type: PeriodType = PeriodType.DAILY
    frequency: int = 1
    run_time: str = "00:00"
    weekday: Optional[WeekdayType] = None

    @field_validator("type", mode="before")
    @classmethod
    def transform(cls, raw: str) -> PeriodType:
        return PeriodType(raw.lower())


class LocalDeviceConfig(BaseModel):
    name: str
    device_id: str
    primary: bool = False


class CloudRepoConfig(BaseModel):
    type: CloudType
    path: str
    key: str
    key_id: str

    @field_validator("type", mode="before")
    @classmethod
    def transform(cls, raw: str) -> CloudType:
        return CloudType(raw.lower())

    def set_cloud_keys_evs(self):
        """ Sets the cloud keys and events for this device """

        if self.type == CloudType.S3_COMPATIBLE:
            os.environ["AWS_ACCESS_KEY_ID"] = self.key_id
            os.environ["AWS_SECRET_ACCESS_KEY"] = self.key

    def get_restic_path(self) -> str:
        """ Returns the restic path for this device

        Returns:
            str: restic path
        """

        prefix = ""
        if self.type == CloudType.S3_COMPATIBLE:
            prefix = "s3:"

        return f"{prefix}{self.path}"


class RepoConfig(BaseModel):
    local_devices: list[LocalDeviceConfig]
    cloud_repos: Optional[list[CloudRepoConfig]] = None


class RetentionConfig(BaseModel):
    days: int = 14
    weeks: int = 16
    months: int = 18
    years: int = 3


class TaskConfig(BaseModel):
    repo: str
    root: os.PathLike
    pw_file: os.PathLike
    type: TaskType
    period: PeriodConfig
    repo_roots: RepoConfig
    stop_container: bool = True


class BackupTaskConfig(TaskConfig):
    paths: list[str]
    retention: RetentionConfig


class CheckTaskConfig(TaskConfig):
    read_data: bool
    subset: Optional[str] = None


class DefaultConfig(BaseModel):
    repo_roots: Optional[RepoConfig] = None
    retention: Optional[RetentionConfig] = None


class NtfyConfig(BaseModel):
    topic_url: str
    token: str


class BackupConfig(BaseModel):
    ntfy: Optional[NtfyConfig] = None
    default: Optional[DefaultConfig] = None
    tasks: dict[str, BackupTaskConfig | CheckTaskConfig]

    @model_validator(mode='before')
    @classmethod
    def set_defaults(cls, data: Any) -> Any:

        if isinstance(data, dict):
            defaults = data.get('default', {})

            if 'tasks' in data and isinstance(data['tasks'], dict):
                tasks = data['tasks']

                for key, task in tasks.items():
                    if 'repo_roots' not in task:
                        if 'repo_roots' in defaults:
                            task['repo_roots'] = defaults['repo_roots']
                        else:
                            raise ValueError(
                                f"Repository roots must be specified for task '{key}'")

                    if 'type' in task and (task['type'] == 'data-backup' or task['type'] == 'docker-compose-backup') and 'retention' not in task:
                        if 'retention' in defaults:
                            task['retention'] = defaults['retention']
                        else:
                            raise ValueError(
                                f"Retention policy must be specified for backup task '{key}'")

        return data

    @model_validator(mode='after')
    def check_type_config(self):
        for key, task in self.tasks.items():
            if isinstance(task, CheckTaskConfig) and task.type != TaskType.CHECK:
                raise ValueError(
                    f"task '{key}' has a check configuration but type is not 'check'")

            if isinstance(task, BackupTaskConfig) and task.type != TaskType.DATA_BACKUP and task.type != TaskType.DOCKER_COMPOSE_BACKUP:
                raise ValueError(
                    f"task '{key}' has a backup configuration but type is not 'data-backup' or 'docker-compose-backup'")

        return self
