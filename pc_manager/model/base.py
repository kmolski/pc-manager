from collections import namedtuple
from enum import Enum

BasicOp = namedtuple("BasicOp", ["name", "description", "with_argument"])

START_OP = BasicOp("start", "Start the target machine.", False)
SHUTDOWN_OP = BasicOp("shutdown", "Shut down the target machine.", False)
SUSPEND_OP = BasicOp("suspend", "Suspend the target machine.", False)
RESUME_OP = BasicOp("resume", "Wake the target machine up.", False)
REBOOT_OP = BasicOp("reboot", "Reboot the target machine.", False)
GET_STATUS_OP = BasicOp("get_status", "Get the status of the target machine.", False)
ENSURE_STATUS_OP = BasicOp(
    "ensure_status", "Ensure the status of the target machine.", True
)
EXECUTE_COMMAND_OP = BasicOp(
    "execute_command", "Execute the given command on the target machine.", True
)

BASIC_OPS = [
    START_OP,
    SHUTDOWN_OP,
    SUSPEND_OP,
    RESUME_OP,
    REBOOT_OP,
    GET_STATUS_OP,
    ENSURE_STATUS_OP,
    EXECUTE_COMMAND_OP,
]


class MachineStatus(Enum):
    UNKNOWN = "unknown"
    POWER_OFF = "power off"
    POWER_ON = "power on"
    SUSPENDED = "suspended"


class OperationProvider:
    def get_operations(self):
        raise NotImplementedError()


class StatusManager:
    def get_status(self):
        raise NotImplementedError()

    def ensure_status(self, target_status):
        raise NotImplementedError()
