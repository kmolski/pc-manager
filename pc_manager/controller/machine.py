from flask import render_template, Blueprint, request, session, redirect
from flask_marshmallow import Marshmallow
from marshmallow import fields, post_load, ValidationError, EXCLUDE
from marshmallow.validate import Length, Regexp
from marshmallow_oneofschema import OneOfSchema
from sqlalchemy.exc import IntegrityError

from app import db
from model.base import MachineStatus
from model.credential import Credential
from model.hardware_features import WakeOnLan, LibvirtGuest
from model.machine import Machine
from model.software_platform import LinuxPlatform, WindowsPlatform

machines = Blueprint("machines", __name__, template_folder="templates")

REDIRECTS = {
    "ADD": lambda: ("/add_machine", "add_machine.html"),
    "EDIT": lambda id: (f"/edit_machine/{id}", "edit_machine.html"),
}

ma = Marshmallow()


class WakeOnLanSchema(ma.Schema):
    mac_address = fields.Str(
        required=True, validate=Regexp(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")
    )

    @post_load
    def make_wakeonlan(self, data, **_):
        return WakeOnLan(**data)


class LibvirtGuestSchema(ma.Schema):
    host_id = fields.Integer(required=True)
    vm_uuid = fields.UUID(required=True)

    @post_load
    def make_libvirt_guest(self, data, **_):
        return LibvirtGuest(**data)


class HardwareFeaturesSchema(OneOfSchema):
    subtypes = {WakeOnLan: WakeOnLanSchema, LibvirtGuest: LibvirtGuestSchema}
    type_schemas = {k.PROVIDER_NAME: v for k, v in subtypes.items()}

    def get_obj_type(self, obj):
        return obj.PROVIDER_NAME


class LinuxPlatformSchema(ma.Schema):
    hostname = fields.Str(required=True)
    credential_id = fields.Integer(required=True)

    @post_load
    def make_linux_platform(self, data, **_):
        return LinuxPlatform(**data)


class WindowsPlatformSchema(ma.Schema):
    hostname = fields.Str(required=True)
    credential_id = fields.Integer(required=True)

    @post_load
    def make_windows_platform(self, data, **_):
        return WindowsPlatform(**data)


class SoftwarePlatformSchema(OneOfSchema):
    subtypes = {
        LinuxPlatform: LinuxPlatformSchema,
        WindowsPlatform: WindowsPlatformSchema,
    }
    type_schemas = {k.PROVIDER_NAME: v for k, v in subtypes.items()}

    def get_obj_type(self, obj):
        return obj.PROVIDER_NAME


class MachineSchema(ma.Schema):
    name = fields.Str(required=True, validate=Length(max=127))
    place = fields.Str(validate=Length(max=127))
    hardware_features = fields.Nested(HardwareFeaturesSchema, allow_none=True)
    software_platforms = fields.List(fields.Nested(SoftwarePlatformSchema))
    custom_operations = fields.List(fields.Integer())

    @post_load
    def make_machine(self, data, **_):
        return Machine(**data)


hardware_features_schema = HardwareFeaturesSchema()
software_platform_schema = SoftwarePlatformSchema()
machine_schema = MachineSchema()


@machines.route("/")
def all_machines():
    return render_template(
        "machines.html",
        machines=Machine.query.paginate(),
    )


@machines.route("/add_machine", methods=["GET"])
def add_machine():
    if ("action" not in session) or (session["action"] != "MACHINE_ADD"):
        session.clear()
        session["action"] = "MACHINE_ADD"
        session["redirect"] = REDIRECTS["ADD"]()
    if "machine" not in session:
        session["machine"] = {"hardware_features": None, "software_platforms": []}
    machine = session["machine"]
    return (
        render_template(
            "add_machine.html",
            machine=machine,
            linux_hosts=LinuxPlatform.query.all(),
            credentials=Credential.query,
        ),
        200,
    )


@machines.route("/edit_machine/<machine_id>", methods=["GET"])
def edit_machine(machine_id):
    machine = Machine.query.get_or_404(machine_id)
    if ("action" not in session) or (session["action"] != "MACHINE_EDIT"):
        session.clear()
        session["action"] = "MACHINE_EDIT"
        session["redirect"] = REDIRECTS["EDIT"](machine_id)
    if ("id" not in session) or (session["id"] != machine_id):
        session["id"] = machine_id
        hw = machine.hardware_features
        sw = machine.software_platforms
        session["machine"] = {
            "hardware_features": hardware_features_schema.dump(hw) if hw else None,
            "software_platforms": software_platform_schema.dump(sw, many=True)
            if sw
            else [],
        }
        session["redirect"] = REDIRECTS["EDIT"](machine_id)
    providers = session["machine"]
    return (
        render_template(
            "edit_machine.html",
            name=machine.name,
            place=machine.place,
            providers=providers,
            linux_hosts=LinuxPlatform.query.all(),
            credentials=Credential.query,
        ),
        200,
    )


@machines.route("/delete_machine/<machine_id>", methods=["GET"])
def delete_machine(machine_id):
    machine = Machine.query.get_or_404(machine_id)
    db.session.delete(machine)
    db.session.commit()
    message = f"Successfully deleted '{machine.name}' machine."
    return render_template("success.html", message=message, redirect="/")


@machines.route("/change_status/<machine_id>", methods=["GET"])
def change_status(machine_id):
    machine = Machine.query.get_or_404(machine_id)

    target_status = MachineStatus[request.args.get("target_status")]
    new_status = machine.ensure_status(target_status)
    db.session.commit()

    if new_status != target_status:
        message = f"Could not set status for machine '{machine.name}'"
        return render_template("error.html", message=message, redirect="/")

    message = f"Successfully set machine '{machine.name}' status to {new_status.value}"
    return render_template("success.html", message=message, redirect="/")


@machines.route("/add_hardware_features", methods=["POST"])
def add_hardware_features():
    redirects = session["redirect"]
    if "machine" not in session:
        return redirect(redirects[0])

    machine = session["machine"]
    try:
        new_features = hardware_features_schema.load(request.form, unknown=EXCLUDE)
        machine["hardware_features"] = hardware_features_schema.dump(new_features)
        session["machine"] = machine
        return redirect(redirects[0])
    except ValidationError as e:
        errors = [
            f"Field '{name}': {', '.join(desc)}" for name, desc in e.messages.items()
        ]
        return (
            render_template(
                redirects[1],
                machine=machine,
                linux_hosts=LinuxPlatform.query.all(),
                credentials=Credential.query,
                errors=errors,
            ),
            200,
        )


@machines.route("/delete_hardware_features")
def delete_hardware_features():
    redirects = session["redirect"]
    if "machine" not in session:
        return redirect(redirects[0])
    machine = session["machine"]
    machine["hardware_features"] = None

    session["machine"] = machine
    return redirect(redirects[0])


@machines.route("/add_software_platform", methods=["POST"])
def add_software_platform():
    redirects = session["redirect"]
    if "machine" not in session:
        return redirect(redirects[0])

    machine = session["machine"]
    try:
        new_platform = software_platform_schema.load(request.form, unknown=EXCLUDE)
        machine["software_platforms"].append(
            software_platform_schema.dump(new_platform)
        )
        session["machine"] = machine
        return redirect(redirects[0])
    except ValidationError as e:
        errors = [
            f"Field '{name}': {', '.join(desc)}" for name, desc in e.messages.items()
        ]
        return (
            render_template(
                redirects[1],
                machine=machine,
                linux_hosts=LinuxPlatform.query.all(),
                credentials=Credential.query,
                errors=errors,
            ),
            200,
        )


@machines.route("/delete_software_platform/<index>")
def delete_software_platform(index):
    redirects = session["redirect"]
    if "machine" not in session:
        return redirect(redirects[0])
    machine = session["machine"]

    machine["software_platforms"].pop(int(index) - 1)
    session["machine"] = machine
    return redirect(redirects[0])


@machines.route("/clear_machine")
def clear_machine():
    session.clear()
    return redirect("/add_machine")


@machines.route("/add_machine", methods=["POST"])
def create_machine():
    if "machine" not in session:
        return redirect("/add_machine")
    machine = session["machine"]
    new_machine = request.form.to_dict() | machine

    try:
        new_machine = machine_schema.load(new_machine, unknown=EXCLUDE)
        db.session.add(new_machine)
        db.session.commit()

        session.clear()
        message = f"Successfully created '{new_machine.name}' machine."
        return render_template("success.html", message=message, redirect="/")
    except ValidationError as e:
        db.session.rollback()
        errors = [
            f"Field '{name}': {', '.join(desc)}" for name, desc in e.messages.items()
        ]
        return (
            render_template(
                "add_machine.html",
                machine=machine,
                linux_hosts=LinuxPlatform.query.all(),
                credentials=Credential.query,
                errors=errors,
            ),
            200,
        )
    except IntegrityError:
        db.session.rollback()
        errors = ["Machine with this name already exists"]
        return (
            render_template(
                "add_machine.html",
                machine=machine,
                linux_hosts=LinuxPlatform.query.all(),
                credentials=Credential.query,
                errors=errors,
            ),
            200,
        )


@machines.route("/edit_machine/<machine_id>", methods=["POST"])
def update_machine(machine_id):
    if "id" not in session:
        return redirect("/edit_machine")
    previous = Machine.query.get(machine_id)
    providers = session["machine"]
    form = request.form.to_dict() | providers

    db.session.delete(previous.hardware_features)
    for sw in previous.software_platforms:
        db.session.delete(sw)

    try:
        updated = machine_schema.load(form, unknown=EXCLUDE)
        updated.id = machine_id
        db.session.merge(updated)
        db.session.commit()

        session.clear()
        message = f"Successfully updated '{updated.name}' machine."
        return render_template("success.html", message=message, redirect="/")
    except ValidationError as e:
        db.session.rollback()
        errors = [
            f"Field '{name}': {', '.join(desc)}" for name, desc in e.messages.items()
        ]
        return (
            render_template(
                "edit_machine.html",
                name=form["name"],
                place=form["place"],
                providers=providers,
                linux_hosts=LinuxPlatform.query.all(),
                credentials=Credential.query,
                errors=errors,
            ),
            200,
        )
    except IntegrityError:
        db.session.rollback()
        errors = ["Machine with this name already exists"]
        return (
            render_template(
                "edit_machine.html",
                name=form["name"],
                place=form["place"],
                providers=providers,
                linux_hosts=LinuxPlatform.query.all(),
                credentials=Credential.query,
                errors=errors,
            ),
            200,
        )
