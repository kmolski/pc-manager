from flask import Flask, render_template

from api import rest_api
from controller.credential import credentials
from model import db_session, init_db
from model.machine import Machine

app = Flask(__name__)
app.register_blueprint(credentials)


@app.route("/")
def machines():
    return render_template("index.html", machines=Machine.query.all())


rest_api.init_app(app)

init_db()


@app.route("/info/health")
def healthcheck():
    return "", 204


@app.teardown_appcontext
def shutdown_db_session(exception=None):
    db_session.remove()
