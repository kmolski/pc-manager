from flask import render_template, Blueprint, request
from flask_marshmallow import Marshmallow
from marshmallow import fields, post_load, ValidationError, EXCLUDE
from marshmallow.validate import Length, OneOf
from marshmallow_oneofschema import OneOfSchema
from sqlalchemy.exc import IntegrityError

from model import db_session
from model.credential import (
    Credential,
    Password,
    SshKeyNoPassword,
    SshKeyWithPassword,
    SshCredential,
)

credentials = Blueprint("credentials", __name__, template_folder="templates")

CREDENTIAL_TYPES = [Password, SshKeyNoPassword, SshKeyWithPassword]
TYPE_NAMES = {t.PROVIDER_NAME: t for t in CREDENTIAL_TYPES}


@credentials.route("/credentials")
def all_credentials():
    # TODO: add pagination
    return render_template(
        "credentials.html",
        credential_count=Credential.query.count(),
        credentials=Credential.query.all(),
        types=CREDENTIAL_TYPES,
    )


@credentials.route("/add_credential", methods=["GET"])
def add_credential():
    try:
        credential_class = TYPE_NAMES[request.args.get("type")]
        return render_template("add_credential.html", type=credential_class), 200
    except KeyError:
        return render_template(
            "error.html", message="Incorrect credential type", redirect="/credentials"
        )


@credentials.route("/edit_credential/<credential_id>", methods=["GET"])
def edit_credential(credential_id):
    credential = Credential.query.get(credential_id)
    return render_template("edit_credential.html", credential=credential), 200


@credentials.route("/delete_credential/<credential_id>", methods=["GET"])
def delete_credential(credential_id):
    credential = Credential.query.get(credential_id)
    db_session.delete(credential)
    db_session.commit()
    message = f"Successfully deleted '{credential.name}' credential."
    return render_template("success.html", message=message, redirect="/credentials")


ma = Marshmallow()


class PasswordSchema(ma.Schema):
    name = fields.String(validate=Length(min=1, max=127))
    username = fields.String(validate=Length(max=255))
    secret = fields.String(validate=Length(max=255), load_only=True)

    @post_load
    def make_credential(self, data, **_):
        return Password(**data)


class SshKeyNoPasswordSchema(ma.Schema):
    name = fields.String(validate=Length(min=1, max=127))
    username = fields.String(validate=Length(max=255))
    key = fields.String(validate=Length(min=1, max=1023), load_only=True)
    key_type = fields.String(validate=OneOf(SshCredential.KEY_TYPES.keys()))

    @post_load
    def make_credential(self, data, **_):
        return SshKeyNoPassword(**data)


class SshKeyWithPasswordSchema(ma.Schema):
    name = fields.String(validate=Length(min=1, max=127))
    username = fields.String(validate=Length(max=255))
    secret = fields.String(validate=Length(max=255), load_only=True)
    key = fields.String(validate=Length(min=1, max=1023), load_only=True)
    key_type = fields.String(validate=OneOf(SshCredential.KEY_TYPES.keys()))

    @post_load
    def make_credential(self, data, **_):
        return SshKeyWithPassword(**data)


class CredentialSchema(OneOfSchema):
    subtypes = {
        Password: PasswordSchema,
        SshKeyNoPassword: SshKeyNoPasswordSchema,
        SshKeyWithPassword: SshKeyWithPasswordSchema,
    }
    type_schemas = {k.PROVIDER_NAME: v for k, v in subtypes.items()}

    def get_obj_type(self, obj):
        return obj.PROVIDER_NAME


credential_schema = CredentialSchema()


@credentials.route("/add_credential", methods=["POST"])
def create_credential():
    form = request.form | {k: v.stream.read() for k, v in request.files.items()}

    type = TYPE_NAMES[form["type"]]
    if ("secret" in form) and (form["secret"] != form["confirm_password"]):
        errors = ["Field 'password' does not match 'confirm password'"]
        return (
            render_template("add_credential.html", type=type, errors=errors),
            200,
        )
    try:
        new_credential = credential_schema.load(form, unknown=EXCLUDE)
        db_session.add(new_credential)
        db_session.commit()
        message = f"Successfully created '{new_credential.name}' credential."
        return render_template("success.html", message=message, redirect="/credentials")
    except ValidationError as e:
        db_session.rollback()
        errors = [
            f"Field '{name}': {', '.join(desc)}" for name, desc in e.messages.items()
        ]
        return (
            render_template("add_credential.html", type=type, errors=errors),
            200,
        )
    except IntegrityError:
        db_session.rollback()
        errors = ["Credential with this name already exists"]
        return (
            render_template("add_credential.html", type=type, errors=errors),
            200,
        )


@credentials.route("/edit_credential/<credential_id>", methods=["POST"])
def update_credential(credential_id):
    previous = Credential.query.get(credential_id)
    form = request.form | {k: v.stream.read() for k, v in request.files.items()}
    if ("key" not in form) or (not form["key"]):
        form["key"] = previous.key
        form["key_type"] = previous.key_type

    if ("secret" in form) and (form["secret"] != form["confirm_password"]):
        errors = ["Field 'password' does not match 'confirm password'"]
        return (
            render_template("edit_credential.html", credential=previous, errors=errors),
            200,
        )
    try:
        updated = credential_schema.load(form, unknown=EXCLUDE)
        updated.id = credential_id

        if previous.type != updated.type:
            message = "Changing credential type is not allowed"
            return render_template(
                "error.html", message=message, redirect="/credentials"
            )

        db_session.merge(updated)
        db_session.commit()
        message = f"Successfully updated '{updated.name}' credential."
        return render_template("success.html", message=message, redirect="/credentials")
    except ValidationError as e:
        db_session.rollback()
        errors = [
            f"Field '{name}': {', '.join(desc)}" for name, desc in e.messages.items()
        ]
        return (
            render_template("edit_credential.html", credential=previous, errors=errors),
            200,
        )
    except IntegrityError:
        db_session.rollback()
        errors = ["Credential with this name already exists"]
        return (
            render_template("edit_credential.html", credential=previous, errors=errors),
            200,
        )
