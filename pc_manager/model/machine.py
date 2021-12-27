from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.orm import relationship

from model import Base
from model.base import MachineStatus
from model.custom_operation import association_table, CustomOperationProvider


class Machine(Base):
    __tablename__ = "machine"

    id = Column(Integer, primary_key=True)
    name = Column(String(127), nullable=False, unique=True)
    place = Column(String(127))

    hardware_features = relationship(
        "HardwareFeatures",
        foreign_keys="HardwareFeatures.machine_id",
        back_populates="machine",
        uselist=False,
        cascade="all, delete-orphan",
    )
    software_platforms = relationship(
        "SoftwarePlatform",
        back_populates="machine",
        cascade="all, delete-orphan",
        order_by="SoftwarePlatform.priority",
        collection_class=ordering_list("priority"),
    )
    custom_operations = relationship(
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
                *self.software_platforms,
            )
            if p is not None
        ]

    def get_status_managers(self):
        return [
            p
            for p in (self.hardware_features, *self.software_platforms)
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
            raise Exception(f"execute_action failed: all providers failed", errors)
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
                return status
        return self.get_status()
