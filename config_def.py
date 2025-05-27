from enum import Enum
import os
from typing import Optional
from pydantic import BaseModel, field_validator


class PeriodType(str, Enum):
    """ Represents the type of update period """
    HOURLY = 'hourly'
    DAILY = 'daily'
    WEEKLY = 'weekly'

    
class CloudType(str, Enum):
    S3_COMPATIBLE = "s3-compatible"
    
class BackupType(str, Enum):
    STANDARD="standard"
    CONTAINER="container"

class PeriodConfig(BaseModel):
        
    type: PeriodType = PeriodType.DAILY 
    frequency: int = 1
    run_time: str = "00:00"
    
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
    type: BackupType = BackupType.STANDARD
    period: Optional[PeriodConfig] = None
    local_devices: Optional[list[LocalDeviceConfig]] = None
    cloud_repos: list[CloudRepoConfig] = []
    retention: Optional[RetentionConfig] = None

class DefaultConfig(BaseModel):
    period: Optional[PeriodConfig] = None
    local_devices: Optional[list[LocalDeviceConfig]] = None
    cloud_repos: Optional[list[CloudRepoConfig]] = None
    retention: Optional[RetentionConfig] = None

class BackupConfig(BaseModel):
    default: Optional[DefaultConfig] = None
    backups: dict[str, BackupTaskConfig]