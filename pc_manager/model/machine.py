from datetime import datetime

from sqlalchemy.ext.orderinglist import ordering_list

from app import db
from model.base import MachineStatus
from model.custom_operation import association_table, CustomOperationProvider


class Machine(db.Model):
    __tablename__ = "machine"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False, unique=True)
    place = db.Column(db.String(127))

    last_status = db.Column(
        db.Enum(MachineStatus, name="machine_status", validate_strings=True),
        nullable=False,
        default=MachineStatus.UNKNOWN,
    )
    last_status_time = db.Column(db.TIMESTAMP(), nullable=False, server_default="now()")

    hardware_features = db.relationship(
        "HardwareFeatures",
        foreign_keys="HardwareFeatures.machine_id",
        back_populates="machine",
        uselist=False,
        cascade="all, delete-orphan",
    )
    software_platforms = db.relationship(
        "SoftwarePlatform",
        back_populates="machine",
        cascade="all, delete-orphan",
        order_by="SoftwarePlatform.priority",
        collection_class=ordering_list("priority"),
    )
    custom_operations = db.relationship(
        "CustomOperation",
        secondary=association_table,
        back_populates="machines",
        cascade="all",
    )

    def __init__(self, name, place, hardware_features, software_platforms):
        self.name = name
        self.place = place
        self.hardware_features = hardware_features
        self.software_platforms = software_platforms

    def get_operation_providers(self):
        return [
            p
            for p in (
                CustomOperationProvider(self),
                self.hardware_features,
                *(self.software_platforms or []),
            )
            if p is not None
        ]

    def get_status_managers(self):
        return [
            p
            for p in (self.hardware_features, *(self.software_platforms or []))
            if p is not None
        ]

    def execute_action(self, name, action_args):
        operation_providers = self.get_operation_providers()
        errors = []
        for provider in operation_providers:
            operations = provider.get_operations()
            try:
                op = operations[name][0]
                return op(*action_args)
            except KeyError:
                continue
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise Exception("execute_action failed: all providers failed", errors)
        else:
            raise Exception(f"operation not found for machine {self.name}", name)

    def get_status(self):
        status_managers = self.get_status_managers()
        for provider in status_managers:
            status = provider.get_status()
            if status != MachineStatus.UNKNOWN:
                return status
        return MachineStatus.UNKNOWN

    def ensure_status(self, target_status):
        status_managers = self.get_status_managers()
        for provider in status_managers:
            status = provider.ensure_status(target_status)
            if status == target_status:
                self.last_status = status
                self.last_status_time = datetime.now()
                return status
        return self.get_status()
