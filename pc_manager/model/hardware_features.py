from time import sleep, time
from urllib.parse import urlunparse

import libvirt
from sqlalchemy.dialects.postgresql import UUID, MACADDR
from wakeonlan import send_magic_packet

from app import db
from model.base import (
    OperationProvider,
    MachineStatus,
    StatusManager,
    RESUME_OP,
    GET_STATUS_OP,
    ENSURE_STATUS_OP,
    START_OP,
    SHUTDOWN_OP,
    SUSPEND_OP,
    REBOOT_OP,
)


class HardwareFeatures(db.Model, OperationProvider, StatusManager):
    __tablename__ = "hardware_features"
    __mapper_args__ = {"polymorphic_on": "type"}

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(
        db.Integer,
        db.ForeignKey("machine.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    type = db.Column(db.String(31))

    machine = db.relationship(
        "Machine",
        foreign_keys=[machine_id],
        back_populates="hardware_features",
        uselist=False,
    )


class WakeOnLan(HardwareFeatures):
    PROVIDER_NAME = "wakeonlan"
    READABLE_NAME = "Wake-on-LAN"

    __mapper_args__ = {"polymorphic_identity": PROVIDER_NAME}

    RESUME_TIMEOUT = 20

    mac_address = db.Column(MACADDR)

    def __init__(self, mac_address, id=None):
        self.id = id
        self.mac_address = mac_address

    def __resume(self):
        send_magic_packet(self.mac_address)

    def get_properties(self):
        return {"MAC address": self.mac_address}

    def get_operations(self):
        return {
            RESUME_OP.name: (self.__resume, RESUME_OP.description),
            ENSURE_STATUS_OP.name: (self.ensure_status, ENSURE_STATUS_OP.description),
        }

    def get_status(self):
        return MachineStatus.UNKNOWN

    def ensure_status(self, target_status):
        current_status = self.machine.get_status()
        if target_status == MachineStatus.POWER_ON and target_status != current_status:
            self.__resume()

            timeout = time() + self.RESUME_TIMEOUT
            while current_status != MachineStatus.POWER_ON and time() < timeout:
                sleep(2)
                current_status = self.machine.get_status()

        return current_status


class LibvirtGuest(HardwareFeatures):
    PROVIDER_NAME = "libvirt"
    READABLE_NAME = "KVM/Libvirt guest"

    __mapper_args__ = {"polymorphic_identity": PROVIDER_NAME}

    OPERATION_TIMEOUT = 10

    host_id = db.Column(
        db.Integer, db.ForeignKey("software_platform.id", ondelete="SET NULL")
    )
    vm_uuid = db.Column(UUID(as_uuid=True))

    libvirt_host_platform = db.relationship(
        "SoftwarePlatform", foreign_keys=[host_id], uselist=False
    )

    def __init__(self, host_id, vm_uuid, id=None):
        self.id = id
        self.host_id = host_id
        self.vm_uuid = vm_uuid

    def get_connection_to_host(self):
        software_platform = self.libvirt_host_platform
        host_machine = software_platform.machine

        if host_machine.ensure_status(MachineStatus.POWER_ON) != MachineStatus.POWER_ON:
            raise Exception("could not wake libvirt host")

        url = urlunparse(("qemu+ssh", software_platform.hostname, "system", None, None, None))
        return libvirt.open(url)

    def get_domain(self):
        conn = self.get_connection_to_host()
        return conn.lookupByUUID(self.vm_uuid.bytes)

    def start(self):
        domain = self.get_domain()
        domain.create()

    def shutdown(self):
        domain = self.get_domain()
        domain.shutdown()

    def resume(self):
        domain = self.get_domain()
        domain.resume()

    def suspend(self):
        domain = self.get_domain()
        domain.suspend()

    def reboot(self):
        domain = self.get_domain()
        domain.reboot()

    def get_properties(self):
        return {
            "Host machine": self.libvirt_host_platform.machine.name,
            "Machine UUID": self.vm_uuid,
        }

    def get_operations(self):
        return {
            START_OP.name: (self.start, START_OP.description),
            SHUTDOWN_OP.name: (self.shutdown, SHUTDOWN_OP.description),
            SUSPEND_OP.name: (self.suspend, SUSPEND_OP.description),
            RESUME_OP.name: (self.resume, RESUME_OP.description),
            REBOOT_OP.name: (self.reboot, REBOOT_OP.description),
            GET_STATUS_OP.name: (self.get_status, GET_STATUS_OP.description),
            ENSURE_STATUS_OP.name: (self.ensure_status, ENSURE_STATUS_OP.description),
        }

    def get_status(self):
        if self.libvirt_host_platform.machine.get_status() != MachineStatus.POWER_ON:
            return MachineStatus.UNKNOWN

        status, _ = self.get_domain().state()
        match status:
            case libvirt.VIR_DOMAIN_RUNNING | libvirt.VIR_DOMAIN_SHUTDOWN:
                return MachineStatus.POWER_ON
            case libvirt.VIR_DOMAIN_SHUTOFF | libvirt.VIR_DOMAIN_CRASHED:
                return MachineStatus.POWER_OFF
            case libvirt.VIR_DOMAIN_PMSUSPENDED | libvirt.VIR_DOMAIN_PAUSED:
                return MachineStatus.SUSPENDED
            case _:
                return MachineStatus.UNKNOWN

    def ensure_status(self, target_status):
        current_status = self.get_status()
        if target_status != current_status:
            domain = self.get_domain()

            match (target_status, self.get_status()):
                case (MachineStatus.POWER_ON, MachineStatus.POWER_OFF):
                    domain.create()
                case (MachineStatus.POWER_ON, MachineStatus.SUSPENDED):
                    domain.resume()
                case (MachineStatus.POWER_OFF, _):
                    domain.shutdown()
                case (MachineStatus.SUSPENDED, _):
                    domain.suspend()

            timeout = time() + self.OPERATION_TIMEOUT
            while current_status != target_status and time() < timeout:
                sleep(1)
                current_status = self.get_status()

        return current_status
