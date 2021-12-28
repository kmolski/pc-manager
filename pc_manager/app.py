from os import getenv

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy


DATABASE_URL = getenv("PC_MANAGER_DB_URL", "postgresql://localhost:5432/pc_manager")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
db.create_all()

from controller.credential import credentials
from model import credential, custom_operation, machine, hardware_features, software_platform
from model.machine import Machine

app.register_blueprint(credentials)


@app.route("/")
def machines():
    return render_template("index.html", machines=Machine.query.all())


# rest_api.init_app(app)


@app.route("/info/health")
def healthcheck():
    return "", 204
