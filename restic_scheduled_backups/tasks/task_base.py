#!/usr/bin/env python3
from abc import ABC, abstractmethod
import argparse
from enum import Enum
import logging

from multiprocessing import Queue
from os import PathLike
from pathlib import Path

import schedule

from restic_scheduled_backups.util import ntfy
from restic_scheduled_backups.util.backup import clean_repo, copy_repo, data_backup, init_repo, unlock_repo
from restic_scheduled_backups.config_def import *
from restic_scheduled_backups.util.containers import start_container, stop_container
from restic_scheduled_backups.util.ntfy import NtfyPriorityLevel, ntfy_message
from restic_scheduled_backups.util.system import *

import restic_scheduled_backups.common

logger = logging.getLogger(__name__)

class TaskBase(ABC):
    def __init__(self,
                 name: str,
                 task_config: TaskConfig,
                 task_queue: Queue,
                 ntfy_config: Optional[NtfyConfig] = None,
    ):
        """ Constructor

        Args:
            name (str): name of the task.
            task_config (TaskConfig): configuration for the task.
            task_queue (Queue): queue for tasks.
            ntfy_config (Optional[NtfyConfig], optional): configuration for notifications. Defaults to None.
        """

        self.name = name
        self.repo_roots = task_config.repo_roots
        self.repo_name = task_config.repo
        self.root_dir = task_config.root
        self.pw_file = task_config.pw_file
        self.update_period = task_config.period
        self.task_queue = task_queue
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
            self.task_queue.put(self)
            logging.info(f'queued task: {self.name}')
            self.scheduled = True

    @abstractmethod
    def run(self):
        """ Run the task """
        logger.warning(f'Task {self.name} has no implementation for run() method. This should be overridden by subclasses.')
        