import socket

from paramiko.client import SSHClient

from app import db
from model.base import (
    OperationProvider,
    MachineStatus,
    StatusManager,
    SHUTDOWN_OP,
    SUSPEND_OP,
    REBOOT_OP,
    GET_STATUS_OP,
    ENSURE_STATUS_OP,
    EXECUTE_COMMAND_OP,
)


class SoftwarePlatform(db.Model, OperationProvider, StatusManager):
    __tablename__ = "software_platform"
    __mapper_args__ = {"polymorphic_on": "type"}

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(
        db.Integer, db.ForeignKey("machine.id", ondelete="CASCADE"), nullable=False
    )
    type = db.Column(db.String(31))
    priority = db.Column(db.Integer, nullable=False)

    machine = db.relationship(
        "Machine", back_populates="software_platforms", uselist=False
    )

    def is_active(self):
        raise NotImplementedError()


class SshAccessiblePlatform(SoftwarePlatform):
    hostname = db.Column(db.String(127))
    credential_id = db.Column(
        db.Integer, db.ForeignKey("credential.id", ondelete="SET NULL")
    )

    credential = db.relationship("SshCredential", uselist=False)

    def __init__(self, hostname, credential_id, id=None):
        self.id = id
        self.hostname = hostname
        self.credential_id = credential_id

    def connect_to_server(self):
        ssh_client = SSHClient()
        ssh_client.load_system_host_keys()

        (username, password, pkey) = self.credential.get_ssh_credentials()
        ssh_client.connect(
            self.hostname, username=username, password=password, pkey=pkey
        )

        return ssh_client

    def remote_execute_command(self, command, read_output=True):
        ssh_client = self.connect_to_server()
        try:
            (_, stdout, stderr) = ssh_client.exec_command(command)

            if read_output:
                stdout_lines = stdout.readlines()
                stderr_lines = stderr.readlines()
                return stdout_lines, stderr_lines
            else:
                return None
        finally:
            ssh_client.close()

    def execute_command(self, command):
        self.remote_execute_command(command)

    def get_operations(self):
        return {
            SHUTDOWN_OP.name: (self.shutdown, SHUTDOWN_OP.description),
            SUSPEND_OP.name: (self.suspend, SUSPEND_OP.description),
            REBOOT_OP.name: (self.reboot, REBOOT_OP.description),
            GET_STATUS_OP.name: (self.get_status, GET_STATUS_OP.description),
            ENSURE_STATUS_OP.name: (self.ensure_status, ENSURE_STATUS_OP.description),
            EXECUTE_COMMAND_OP.name: (
                self.execute_command,
                EXECUTE_COMMAND_OP.description,
            ),
        }

    def get_status(self):
        try:
            ssh_client = self.connect_to_server()
            ssh_client.close()
            return MachineStatus.POWER_ON
        except socket.error:
            return MachineStatus.UNKNOWN

    def ensure_status(self, target_status):
        current_status = self.get_status()
        if current_status == MachineStatus.POWER_ON:
            if target_status == MachineStatus.POWER_OFF:
                self.shutdown()
                return MachineStatus.POWER_OFF
            elif target_status == MachineStatus.SUSPENDED:
                self.suspend()
                return MachineStatus.SUSPENDED
            return MachineStatus.POWER_ON

        return current_status


class LinuxPlatform(SshAccessiblePlatform):
    PROVIDER_NAME = "linux"
    __mapper_args__ = {"polymorphic_identity": PROVIDER_NAME}

    def shutdown(self):
        self.remote_execute_command("sudo systemctl poweroff", read_output=False)

    def suspend(self):
        self.remote_execute_command("sudo systemctl suspend", read_output=False)

    def reboot(self):
        self.remote_execute_command("sudo systemctl reboot", read_output=False)

    def is_active(self):
        try:
            (stdout, _) = self.remote_execute_command("uname")
            return any("Linux" in line for line in stdout)
        except socket.error:
            return False


class FreeBsdPlatform(SshAccessiblePlatform):
    PROVIDER_NAME = "freebsd"
    __mapper_args__ = {"polymorphic_identity": PROVIDER_NAME}

    def shutdown(self):
        self.remote_execute_command("sudo poweroff", read_output=False)

    def suspend(self):
        self.remote_execute_command("sudo acpiconf -s 3", read_output=False)

    def reboot(self):
        self.remote_execute_command("sudo reboot", read_output=False)

    def is_active(self):
        try:
            (stdout, _) = self.remote_execute_command("uname")
            return any("FreeBSD" in line for line in stdout)
        except socket.error:
            return False


class WindowsPlatform(SshAccessiblePlatform):
    PROVIDER_NAME = "windows"
    __mapper_args__ = {"polymorphic_identity": PROVIDER_NAME}

    def shutdown(self):
        self.remote_execute_command("shutdown /s /f /t 0", read_output=False)

    def suspend(self):
        self.remote_execute_command(
            "powercfg -hibernate off && rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            read_output=False,
        )

    def reboot(self):
        self.remote_execute_command("shutdown /r /f /t 0", read_output=False)

    def is_active(self):
        try:
            (stdout, _) = self.remote_execute_command("ver")
            return any("Windows" in line for line in stdout)
        except socket.error:
            return False
