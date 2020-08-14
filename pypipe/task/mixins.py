
import datetime
import logging
from pathlib import Path

from pypipe.conditions import task_ran
from pypipe.conditions import AlwaysTrue, AlwaysFalse
from pypipe.log import TaskAdapter, CsvHandler

from pypipe.time import period_factory, StaticInterval

class _ExecutionMixin:

    @property
    def execution(self):
        return self._execution

    @execution.setter
    def execution(self, value):
        self._execution = value

        if value is None:
            self._execution_condition = AlwaysTrue()
            return

        if isinstance(value, str):
            self._execution_condition = ~task_ran(task=self).in_cycle(value)
        else:
            # period is the execution variable
            cond = task_ran(task=self)
            cond.period = value
            self._execution_condition = ~cond

# Additional way to define execution
    def between(self, *args, **kwargs):
        execution = period_factory.between(*args, **kwargs)
        if self.execution is None:
            self.execution = execution
        else:
            # TODO
            self.execution &= execution
        return self

    def every(self, *args, **kwargs):
        execution = period_factory.past(*args, **kwargs)
        if self.execution is None:
            self.execution = execution
        else:
            # TODO
            self.execution &= execution
        return self

    def in_(self, *args, **kwargs):
        execution = period_factory.in_(*args, **kwargs)
        if self.execution is None:
            self.execution = execution
        else:
            # TODO
            self.execution &= execution
        return self

    def from_(self, *args, **kwargs):
        execution = period_factory.from_(*args, **kwargs)
        if self.execution is None:
            self.execution = execution
        else:
            # TODO
            self.execution &= execution
        return self

    def in_cycle(self, *args, **kwargs):
        execution = period_factory.in_cycle(*args, **kwargs)
        if self.execution is None:
            self.execution = execution
        else:
            # TODO
            self.execution &= execution
        return self

    @property
    def period(self):
        "Determine Time object for the interval (maximum possible if time independent as 'or')"
        execution = self._execution_condition
        if hasattr(execution, "period"):
            return execution.period 
        elif hasattr(execution, "__magicmethod__"):
            return functools.reduce(lambda a, b : getattr(a, "__magicmethod__")(b), execution.subconditions)
        else:
            return StaticInterval()

    @property
    def next_start(self):
        "Next datetime when the task can be potentially run (more of a guess)"
        now = datetime.datetime.now()
        
        if bool(self._execution_condition):
            return now
        cond = self._execution_condition
        events = cond.function()
        latest_run = max(events)
        
        
        period = cond.period
        next_interval = period.next(latest_run) # Current interval
        return next_interval.left

class _LoggingMixin:


    def set_logger(self, logger=None):
        "Set the logger (and adapter)"
        if logger is None:
            logger = self.get_logger(self.group_name) # Getting class/instance logger

            if not logger.handlers:
                # Setting default handlers to allow 2 way by default
                self.set_default_logger(logger)
        self.logger = TaskAdapter(logger, task=self)

    @classmethod
    def get_logger(cls, group_name=None):
        "Get the Task logger"
        logger_name = cls._logger_basename
        if group_name is not None:
            logger_name += '.' + group_name
        return logging.getLogger(logger_name)

    @classmethod
    def set_default_logger(cls, logger=None, group_name=None, filename="log/task.csv"):
        
        if logger is None:
            logger = cls.get_logger(group_name=group_name)

        # Emptying existing handlers
        logger.handlers = []

        # Making sure the log folder is found
        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        # Adding the default handler
        handler = CsvHandler(
            filename,
            fields=[
                "asctime",
                "levelname",
                "action",
                "task_name",
                "exc_text",
            ]
        )

        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    @classmethod
    def add_logger_handler(cls, handler, group=None):
        logger = cls.get_logger(group=group)
        logger.addHandler(handler)

    def log_running(self):
        self.logger.info(f"Running '{self.name}'", extra={"action": "run"})

    def log_failure(self):
        self.logger.error(f"Task '{self.name}' failed", exc_info=True, extra={"action": "fail"})

    def log_success(self):
        self.logger.info(f"Task '{self.name}' succeeded", extra={"action": "success"})

    def log_termination(self, reason=None):
        reason = reason or "unknown reason"
        self.logger.info(f"Task '{self.name}' terminated due to: {reason}", extra={"action": "terminate"})

    def log_record(self, record):
        "For multiprocessing in which the record goes from copy of the task to scheduler before it comes back to the original task"
        self.logger.handle(record)

    @property
    def status(self):
        record = self.logger.get_latest()
        if record is None:
            # No previous status
            return None
        return record["action"]

    def get_history(self):
        records = self.logger.get_records()
        return records