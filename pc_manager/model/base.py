from collections import namedtuple
from enum import Enum, auto

BasicOp = namedtuple("BasicOp", ["name", "description"])

START_OP = BasicOp("start", "Start the target machine.")
SHUTDOWN_OP = BasicOp("shutdown", "Shut down the target machine.")
SUSPEND_OP = BasicOp("suspend", "Suspend the target machine.")
RESUME_OP = BasicOp("resume", "Wake the target machine up.")
REBOOT_OP = BasicOp("reboot", "Reboot the target machine.")
GET_STATUS_OP = BasicOp("get_status", "Get the status of the target machine.")
ENSURE_STATUS_OP = BasicOp("ensure_status", "Ensure the status of the target machine.")
EXECUTE_COMMAND_OP = BasicOp(
    "execute_command", "Execute the given command on the target machine."
)


class MachineStatus(Enum):
    UNKNOWN = auto()
    POWER_OFF = auto()
    POWER_ON = auto()
    SUSPENDED = auto()


class OperationProvider:
    def get_operations(self):
        raise NotImplementedError()


class StatusManager:
    def get_status(self):
        raise NotImplementedError()

    def ensure_status(self, target_status):
        raise NotImplementedError()
