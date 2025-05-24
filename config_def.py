import os
from typing import Optional
from pydantic import BaseModel

class PeriodConfig(BaseModel):
    period_type: str = "days"
    frequency: int = 1
    run_time: str = "00:00"

class CloudRepoConfig(BaseModel):
    type: str
    path: str
    key: str
    key_id: str

class ReposRootsConfig(BaseModel):
    local_devices: dict[str, str]
    cloud: dict[str, CloudRepoConfig]

class RetentionConfig(BaseModel):
    days: int = 14
    weeks: int = 16
    months: int = 18
    years: int = 3

class BackupTaskConfig(BaseModel):
    repo: str
    root: os.PathLike
    pw_file: os.PathLike
    paths: list[str]
    type: str = "standard"
    period: Optional[PeriodConfig] = None
    local_devices: Optional[dict[str, str]] = None
    cloud_repos: Optional[dict[str, CloudRepoConfig]] = None
    retention: Optional[RetentionConfig] = None

class DefaultConfig(BaseModel):
    period: Optional[PeriodConfig] = None
    local_devices: Optional[dict[str, str]] = None
    cloud_repos: Optional[dict[str, CloudRepoConfig]] = None
    retention: Optional[RetentionConfig] = None

class BackupConfig(BaseModel):
    default: Optional[DefaultConfig] = None
    backups: dict[str, BackupTaskConfig]