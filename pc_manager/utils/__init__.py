def execute_operations(machine, operations):
    for op in operations:
        argument = op["argument"] if "argument" in op else None
        machine.execute_action(op["op_name"], argument)
