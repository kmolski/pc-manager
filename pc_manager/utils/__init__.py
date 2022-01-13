from itertools import islice


def display_duration(to_date, from_date):
    duration = to_date - from_date

    total_minutes, seconds = divmod(duration.seconds, 60)
    hours, minutes = divmod(total_minutes, 60)
    units = {"d": duration.days, "h": hours, "m": minutes, "s": seconds}

    parts = islice((f"{unit}{name}" for name, unit in units.items() if unit > 0), 2)
    return " ".join(parts)


def execute_operations(machine, operations):
    for op in operations:
        argument = [op["argument"]] if ("argument" in op and op["argument"]) else []
        machine.execute_action(op["op_name"], argument)
