from json import loads

from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship

from model import Base
from model.base import OperationProvider
from utils import execute_operations

association_table = Table(
    "machine_custom_operation",
    Base.metadata,
    Column(
        "machine_id", ForeignKey("machine.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "operation_id",
        ForeignKey("custom_operation.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class CustomOperation(Base):
    __tablename__ = "custom_operation"

    id = Column(Integer, primary_key=True)
    name = Column(String(127), unique=True)
    description = Column(String(255))
    json = Column(String)

    machines = relationship(
        "Machine", secondary=association_table, back_populates="custom_operations"
    )

    def __init__(self, name, description, json):
        self.name = name
        self.description = description
        self.json = json


class CustomOperationProvider(OperationProvider):
    def __init__(self, machine):
        self.operations = {}
        for custom_op in machine.custom_operations:
            process = loads(custom_op.json)

            def custom_op_func():
                execute_operations(machine, process)

            self.operations[custom_op.name] = (custom_op_func, custom_op.description)

    def get_operations(self):
        return self.operations
