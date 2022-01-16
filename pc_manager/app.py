from os import getenv, urandom

from flask import Flask
from flask_httpauth import HTTPBasicAuth
from flask_sqlalchemy import SQLAlchemy

from utils import generate_password

DATABASE_URL = getenv("PC_MANAGER_DB_URL", "postgresql://localhost:5432/pc_manager")
SECRET_KEY = getenv("PC_MANAGER_SECRET_KEY", urandom(32).hex())

USERNAME = getenv("PC_MANAGER_USERNAME", "admin")
PASSWORD = getenv("PC_MANAGER_PASSWORD") or generate_password()

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 2 * 1000 * 1000
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
auth = HTTPBasicAuth()


@auth.verify_password
def authenticate(username, password):
    if not (username and password):
        return False
    return (username == USERNAME) and (password == PASSWORD)


from controller.credential import credentials
from controller.custom_operation import custom_operations
from controller.machine import machines

db.create_all()

app.register_blueprint(credentials)
app.register_blueprint(custom_operations)
app.register_blueprint(machines)


@app.route("/info/health")
def healthcheck():
    return "", 204
