#!/usr/bin/env python3
from abc import ABC, abstractmethod
import logging
from datetime import date

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

        # Queue task
        match(self.update_period.type):
            case PeriodType.HOURLY:        
                logger.info(
                    f'Scheduling task: {self.name} - {self.update_period.type} - freq:{self.update_period.frequency} - at:{self.update_period.run_time}')
                schedule.every(self.update_period.frequency).hours.do(
                    self.__queue_task)
            case PeriodType.DAILY:
                logger.info(
                    f'Scheduling task: {self.name} - {self.update_period.type} - freq:{self.update_period.frequency} - at:{self.update_period.run_time}')
                schedule.every(self.update_period.frequency).days.at(
                    self.update_period.run_time).do(self.__queue_task)
            case PeriodType.WEEKLY:
                logger.info(
                    f'Scheduling task: {self.name} - {self.update_period.type} - freq:{self.update_period.frequency} - at:{self.update_period.run_time} - day: {self.update_period.weekday}')
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
            case PeriodType.MONTHLY:
                logger.info(
                    f'Scheduling task: {self.name} - {self.update_period.type} - freq:{self.update_period.frequency} - at:{self.update_period.run_time} - day: {self.update_period.day}')
                schedule.every(1).days.at(
                    self.update_period.run_time).do(self.__queue_task)

    def __queue_task(self):
        """ Schedule the task """

        if not self.task_queued.is_set():

            if self.__task_ready():
                self.skip_count = 0

                try:
                    self.task_queued.set()
                    task_queue.put(self)
                    logging.info(f'queued task: {self.name}')
                except:
                    logging.error(f'Failed to queue task {self.name}')
                    self.task_queued.clear()

        else:
            logging.warning(
                f'Attempted to queue already scheduled task: {self.name}')
            
    def __task_ready(self) -> bool:
        """ Checks if a task is ready to run

        Returns:
            bool: True if a task is ready to run, False otherwise
        """
        cur_day = date.today().day
        task_ready = False
        if self.update_period == PeriodType.HOURLY:
            if self.skip_count >= self.update_period.frequency - 1:
                logger.debug(f'Queueing task {self.name} since it is Hourly and skip count:{self.skip_count} >= frequency:{self.update_period.frequency - 1}')
                task_ready = True
            else:
                logger.debug(f'Skipped task {self.name} since it is Hourly and skip count {self.skip_count} < frequency:{self.update_period.frequency - 1}')
                self.skip_count += 1
        elif self.update_period.type == PeriodType.DAILY:
            if self.skip_count >= self.update_period.frequency - 1:
                logger.debug(f'Queueing task {self.name} since it is Daily and skip count:{self.skip_count} >= frequency:{self.update_period.frequency - 1}')
                task_ready = True
            else:
                logger.debug(f'Skipped task {self.name} since it is Daily and skip count {self.skip_count} < frequency:{self.update_period.frequency - 1}')
                self.skip_count += 1
        elif self.update_period.type == PeriodType.WEEKLY:
            if self.update_period.weekday is not None:
                logger.debug(f'Queueing task {self.name} since it is Weekly and weekday is set to {self.update_period.weekday}')
                task_ready = True
            else:
                if self.skip_count >= self.update_period.frequency - 1:
                    logger.debug(f'Queueing task {self.name} since it is Weekly and skip count:{self.skip_count} >= frequency:{self.update_period.frequency - 1}')
                    task_ready = True
                else:
                    logger.debug(f'Skipped task {self.name} since it is Weekly and skip count {self.skip_count} < frequency:{self.update_period.frequency - 1} and weekday is not set')
                    self.skip_count += 1
        elif self.update_period.type == PeriodType.MONTHLY:
            if cur_day == self.update_period.day:
                if self.skip_count >= self.update_period.frequency - 1:
                    logger.debug(f'Queueing task {self.name} since it is Monthly and day:{self.update_period.day} != today:{cur_day} and skip count:{self.skip_count} >= frequency:{self.update_period.frequency - 1}')
                    task_ready = True
                else:
                    logger.debug(f'Skipped task {self.name} since it is Monthly and day:{self.update_period.day} != today:{cur_day} but skip count {self.skip_count} < frequency:{self.update_period.frequency - 1}')
                    self.skip_count += 1
            else:
                logger.debug(f'Skipped task {self.name} since it is Monthly and day:{self.update_period.day} != today:{cur_day}')

        return task_ready

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
