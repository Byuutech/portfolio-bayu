import logging
import os
import secrets
from pathlib import Path

from flask import Flask, render_template

from chat import chat_blueprint, get_visitor_id, init_chat, socketio


app = Flask(__name__, instance_relative_config=True)
secret_key = os.environ.get("FLASK_SECRET_KEY")
if not secret_key:
    logging.warning("FLASK_SECRET_KEY is unset; operator sessions will not survive restarts")
app.config["SECRET_KEY"] = secret_key or secrets.token_urlsafe(32)
app.config["CHAT_DATABASE"] = os.environ.get(
    "CHAT_DATABASE",
    str(Path(app.instance_path) / "chat.sqlite3"),
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE") == "1"

Path(app.instance_path).mkdir(parents=True, exist_ok=True)
app.register_blueprint(chat_blueprint)
init_chat(app)


@app.route("/")
def home():
    return render_template("index.html", visitor_id=get_visitor_id())


if __name__ == "__main__":
    socketio.run(app, debug=os.environ.get("FLASK_DEBUG") == "1")