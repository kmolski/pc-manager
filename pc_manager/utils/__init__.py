def execute_operations(machine, operations):
    for op in operations:
        arguments = op["args"] if "args" in op else []
        machine.execute_action(op["op_name"], arguments)
