#!/usr/bin/env python3
from abc import ABC, abstractmethod
import logging

from threading import Event
from queue import Queue

import schedule

from restic_scheduled_backups.config_def import *
from restic_scheduled_backups.util.system import *

import restic_scheduled_backups.common

task_queue = Queue()

logger = logging.getLogger(__name__)


class TaskBase(ABC):
    def __init__(self,
                 name: str,
                 task_config: TaskConfig,
                 ntfy_config: Optional[NtfyConfig] = None,
                 ):
        """ Constructor

        Args:
            name (str): name of the task.
            task_config (TaskConfig): configuration for the task.
            ntfy_config (Optional[NtfyConfig], optional): configuration for notifications. Defaults to None.
        """

        self.name = name
        self.repo_roots = task_config.repo_roots
        self.repo_name = task_config.repo
        self.root_dir = task_config.root
        self.pw_file = task_config.pw_file
        self.update_period = task_config.period
        self.ntfy_config = ntfy_config

        self.skip_count = 0

        self.task_queued = Event()

    def schedule(self) -> None:
        logger.info(
            f'Scheduling task: {self.name} - {self.update_period.type} - freq:{self.update_period.frequency} - at:{self.update_period.run_time}')
        # Queue task
        match(self.update_period.type):
            case PeriodType.HOURLY:
                schedule.every(self.update_period.frequency).hours.do(
                    self.__queue_task)
            case PeriodType.DAILY:
                schedule.every(self.update_period.frequency).days.at(
                    self.update_period.run_time).do(self.__queue_task)
            case PeriodType.WEEKLY:
                match(self.update_period.weekday):
                    case WeekdayType.SUNDAY:
                        schedule.every().sunday.at(self.update_period.run_time).do(self.__queue_task)
                    case WeekdayType.MONDAY:
                        schedule.every().monday.at(self.update_period.run_time).do(self.__queue_task)
                    case WeekdayType.TUESDAY:
                        schedule.every().tuesday.at(self.update_period.run_time).do(self.__queue_task)
                    case WeekdayType.WEDNESDAY:
                        schedule.every().wednesday.at(self.update_period.run_time).do(self.__queue_task)
                    case WeekdayType.THURSDAY:
                        schedule.every().thursday.at(self.update_period.run_time).do(self.__queue_task)
                    case WeekdayType.FRIDAY:
                        schedule.every().friday.at(self.update_period.run_time).do(self.__queue_task)
                    case WeekdayType.SATURDAY:
                        schedule.every().saturday.at(self.update_period.run_time).do(self.__queue_task)
                    case _:
                        schedule.every().weeks.at(self.update_period.run_time).do(self.__queue_task)

    def __queue_task(self):
        """ Schedule the task """

        if not self.task_queued.is_set():
            skipped = self.update_period.type != PeriodType.WEEKLY or self.update_period.weekday is None or self.skip_count >= self.update_period.frequency - 1

            if skipped:
                self.skip_count = 0

                try:
                    self.task_queued.set()
                    task_queue.put(self)
                    logging.info(f'queued task: {self.name}')
                except:
                    logging.error(f'Failed to queue task {self.name}')
                    self.task_queued.clear()
            else:
                self.skip_count += 1
                logger.info(
                    f'Skipping task: {self.name} due to frequency or weekday settings. Skipping count: {self.skip_count} of {self.update_period.frequency}')

        else:
            logging.warning(
                f'Attempted to queue already scheduled task: {self.name}')

    def start_task(self):
        """ Handles running tasks """

        logger.info(f'Starting task: {self.name}')
        self.run()
        logger.info(f'Task Complete: {self.name}')

        self.task_queued.clear()

    @abstractmethod
    def run(self):
        """ Run the task """
        logger.warning(
            f'Task {self.name} has no implementation for run() method. This should be overridden by subclasses.')
