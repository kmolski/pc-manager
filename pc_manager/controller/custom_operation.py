from flask import render_template, Blueprint, request, session, redirect
from flask_marshmallow import Marshmallow
from marshmallow import fields, post_load, ValidationError, EXCLUDE
from marshmallow.validate import Length, OneOf
from sqlalchemy.exc import IntegrityError

from app import db
from model.base import BASIC_OPS
from model.custom_operation import CustomOperation

custom_operations = Blueprint(
    "custom_operations", __name__, template_folder="templates"
)

ma = Marshmallow()


class OperationSchema(ma.Schema):
    op_name = fields.Str(required=True, validate=OneOf([op.name for op in BASIC_OPS]))
    argument = fields.Str(allow_none=True, validate=Length(max=127))


class CustomOperationSchema(ma.Schema):
    name = fields.Str(required=True, validate=Length(min=1, max=127))
    description = fields.Str(required=True, validate=Length(max=255))
    ops = fields.List(fields.Nested(OperationSchema()), required=True)

    @post_load
    def make_operation(self, data, **_):
        return CustomOperation(**data)


operation_schema = OperationSchema()
custom_op_schema = CustomOperationSchema()


@custom_operations.route("/custom_operations")
def all_custom_operations():
    return render_template(
        "custom_operations.html",
        custom_operations=CustomOperation.query.paginate(),
    )


@custom_operations.route("/add_custom_operation", methods=["GET"])
def add_custom_operation():
    if "custom_operation" not in session:
        session["custom_operation"] = []
    custom_op = session["custom_operation"]
    return (
        render_template(
            "add_custom_operation.html", custom_op=custom_op, basic_ops=BASIC_OPS
        ),
        200,
    )


@custom_operations.route(
    "/edit_custom_operation/<custom_operation_id>", methods=["GET"]
)
def edit_custom_operation(custom_operation_id):
    custom_operation = CustomOperation.query.get_or_404(custom_operation_id)
    return (
        render_template(
            "edit_custom_operation.html", custom_operation=custom_operation
        ),
        200,
    )


@custom_operations.route(
    "/delete_custom_operation/<custom_operation_id>", methods=["GET"]
)
def delete_custom_operation(custom_operation_id):
    custom_operation = CustomOperation.query.get_or_404(custom_operation_id)
    db.session.delete(custom_operation)
    db.session.commit()
    message = f"Successfully deleted '{custom_operation.name}' custom operation."
    return render_template(
        "success.html", message=message, redirect="/custom_operations"
    )


ma = Marshmallow()


@custom_operations.route("/add_operation_step", methods=["POST"])
def add_operation_step():
    if "custom_operation" not in session:
        return redirect("/add_custom_operation")
    custom_op = session["custom_operation"]

    try:
        new_step = operation_schema.load(request.form, unknown=EXCLUDE)
        if new_step["op_name"] not in (op.name for op in BASIC_OPS if op.with_argument):
            new_step["argument"] = None

        custom_op.append(new_step)
        session["custom_operation"] = custom_op
        return redirect("/add_custom_operation")
    except ValidationError as e:
        errors = [
            f"Field '{name}': {', '.join(desc)}" for name, desc in e.messages.items()
        ]
        return (
            render_template(
                "add_custom_operation.html",
                custom_op=custom_op,
                basic_ops=BASIC_OPS,
                errors=errors,
            ),
            200,
        )


@custom_operations.route("/delete_operation_step/<index>")
def delete_operation_step(index):
    if "custom_operation" not in session:
        return redirect("/add_custom_operation")
    custom_op = session["custom_operation"]

    custom_op.pop(int(index) - 1)
    session["custom_operation"] = custom_op
    return redirect("/add_custom_operation")


@custom_operations.route("/clear_custom_operation")
def clear_custom_operation():
    session.pop("custom_operation")
    return redirect("/add_custom_operation")


@custom_operations.route("/add_custom_operation", methods=["POST"])
def create_custom_operation():
    if "custom_operation" not in session:
        return redirect("/add_custom_operation")
    new_custom_op = request.form.to_dict()
    custom_op = session["custom_operation"]
    new_custom_op["ops"] = custom_op

    try:
        new_custom_op = custom_op_schema.load(new_custom_op, unknown=EXCLUDE)
        db.session.add(new_custom_op)
        db.session.commit()

        session.pop("custom_operation")
        message = f"Successfully created '{new_custom_op.name}' custom operation."
        return render_template(
            "success.html", message=message, redirect="/custom_operations"
        )
    except ValidationError as e:
        db.session.rollback()
        errors = [
            f"Field '{name}': {', '.join(desc)}" for name, desc in e.messages.items()
        ]
        return (
            render_template(
                "add_custom_operation.html",
                custom_op=custom_op,
                basic_ops=BASIC_OPS,
                errors=errors,
            ),
            200,
        )
    except IntegrityError:
        db.session.rollback()
        errors = ["Custom operation with this name already exists"]
        return (
            render_template(
                "add_custom_operation.html",
                custom_op=custom_op,
                basic_ops=BASIC_OPS,
                errors=errors,
            ),
            200,
        )


@custom_operations.route(
    "/edit_custom_operations/<custom_operations_id>", methods=["POST"]
)
def update_custom_operations(custom_operations_id):
    previous = CustomOperation.query.get_or_404(custom_operations_id)
    form = request.form | {k: v.stream.read() for k, v in request.files.items()}

    try:
        updated = custom_op_schema.load(form, unknown=EXCLUDE)
        updated.id = custom_operations_id

        if previous.type != updated.type:
            message = "Changing custom_operations type is not allowed"
            return render_template(
                "error.html", message=message, redirect="/custom_operations"
            )

        db.session.merge(updated)
        db.session.commit()
        message = f"Successfully updated '{updated.name}' custom operation."
        return render_template(
            "success.html", message=message, redirect="/custom_operations"
        )
    except ValidationError as e:
        db.session.rollback()
        errors = [
            f"Field '{name}': {', '.join(desc)}" for name, desc in e.messages.items()
        ]
        return (
            render_template(
                "edit_custom_operation.html", custom_operation=previous, errors=errors
            ),
            200,
        )
    except IntegrityError:
        db.session.rollback()
        errors = ["Custom operation with this name already exists"]
        return (
            render_template(
                "edit_custom_operation.html", custom_operation=previous, errors=errors
            ),
            200,
        )
