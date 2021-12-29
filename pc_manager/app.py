from os import getenv, urandom

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy


DATABASE_URL = getenv("PC_MANAGER_DB_URL", "postgresql://localhost:5432/pc_manager")

app = Flask(__name__)
app.config["SECRET_KEY"] = urandom(32).hex()
app.config["MAX_CONTENT_LENGTH"] = 2 * 1000 * 1000
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

from controller.credential import credentials
from controller.custom_operation import custom_operations
from model import (
    credential,
    custom_operation,
    machine,
    hardware_features,
    software_platform,
)
from model.machine import Machine

db.create_all()

app.register_blueprint(credentials)
app.register_blueprint(custom_operations)


@app.route("/")
def machines():
    return render_template("index.html", machines=Machine.query.all())


# rest_api.init_app(app)


@app.route("/info/health")
def healthcheck():
    return "", 204
