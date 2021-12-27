from json import loads

from app import db
from model.base import OperationProvider
from utils import execute_operations

association_table = db.Table(
    "machine_custom_operation",
    db.metadata,
    db.Column(
        "machine_id", db.ForeignKey("machine.id", ondelete="CASCADE"), primary_key=True
    ),
    db.Column(
        "operation_id",
        db.ForeignKey("custom_operation.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class CustomOperation(db.Model):
    __tablename__ = "custom_operation"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), unique=True)
    description = db.Column(db.String(255))
    json = db.Column(db.String)

    machines = db.relationship(
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
