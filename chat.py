import hmac
import logging
import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_socketio import SocketIO, emit, join_room


chat_blueprint = Blueprint("chat", __name__)
socketio = SocketIO(async_mode="threading")
logger = logging.getLogger(__name__)
OPERATOR_ROOM = "chat-operators"
MAX_MESSAGE_LENGTH = 1000
operator_auth_tokens: set[str] = set()
operator_sockets: dict[str, set[str]] = {}
operator_state_lock = threading.Lock()


@contextmanager
def _database():
    connection = sqlite3.connect(current_app.config["CHAT_DATABASE"])
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection
    finally:
        connection.close()


def _timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _conversation_room(conversation_id):
    return f"chat-{conversation_id}"


def _ensure_conversation(conversation_id):
    now = _timestamp()
    with _database() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO conversations (id, created_at, updated_at)
            VALUES (?, ?, ?)
            """,
            (conversation_id, now, now),
        )


def _operator_credentials_configured():
    return bool(os.environ.get("CHAT_OPERATOR_USERNAME")) and bool(
        os.environ.get("CHAT_OPERATOR_PASSWORD")
    )


def _operator_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _operator_is_authenticated():
            return redirect(url_for("chat.operator_login"))
        return view(*args, **kwargs)

    return wrapped


def _operator_is_authenticated():
    token = session.get("operator_auth_token")
    if not isinstance(token, str):
        return False
    with operator_state_lock:
        return token in operator_auth_tokens


def get_visitor_id():
    if "chat_visitor_id" not in session:
        session["chat_visitor_id"] = secrets.token_urlsafe(24)
    return session["chat_visitor_id"]


def init_chat(app):
    socketio.init_app(app)
    with app.app_context(), _database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                sender TEXT NOT NULL CHECK (sender IN ('visitor', 'operator')),
                body TEXT NOT NULL,
                sent_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS messages_conversation_id_id
                ON messages (conversation_id, id);
            """
        )


@chat_blueprint.route("/operator/login", methods=["GET", "POST"])
def operator_login():
    error = None
    if request.method == "POST":
        csrf_token = session.get("operator_csrf_token")
        submitted_token = request.form.get("csrf_token", "")
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if not csrf_token or not hmac.compare_digest(csrf_token, submitted_token):
            error = "Sesi formulir tidak valid. Muat ulang halaman lalu coba lagi."
        elif not _operator_credentials_configured():
            logger.error("Chat operator login is unavailable because credentials are not configured")
            error = "Login operator belum dikonfigurasi di server."
        elif hmac.compare_digest(username, os.environ["CHAT_OPERATOR_USERNAME"]) and hmac.compare_digest(
            password, os.environ["CHAT_OPERATOR_PASSWORD"]
        ):
            session.clear()
            auth_token = secrets.token_urlsafe(32)
            with operator_state_lock:
                operator_auth_tokens.add(auth_token)
                operator_sockets[auth_token] = set()
            session["operator_auth_token"] = auth_token
            session["operator_csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("chat.operator_dashboard"))
        else:
            error = "Username atau password salah."

    session["operator_csrf_token"] = secrets.token_urlsafe(32)
    response = render_template(
        "operator_login.html",
        csrf_token=session["operator_csrf_token"],
        error=error,
        credentials_configured=_operator_credentials_configured(),
    )
    status = (
        503
        if request.method == "POST" and not _operator_credentials_configured()
        else 200
    )
    return response, status


@chat_blueprint.post("/operator/logout")
@_operator_required
def operator_logout():
    csrf_token = session.get("operator_csrf_token", "")
    if not csrf_token or not hmac.compare_digest(
        csrf_token, request.form.get("csrf_token", "")
    ):
        return "Sesi formulir tidak valid. Muat ulang halaman lalu coba lagi.", 400
    auth_token = session["operator_auth_token"]
    with operator_state_lock:
        operator_auth_tokens.discard(auth_token)
        sockets = operator_sockets.pop(auth_token, set())
    session.clear()
    for socket_id in sockets:
        socketio.server.disconnect(socket_id, namespace="/")
    return redirect(url_for("chat.operator_login"))


@chat_blueprint.get("/operator")
@_operator_required
def operator_dashboard():
    return render_template("operator_chat.html")


@chat_blueprint.get("/operator/conversations")
@_operator_required
def operator_conversations():
    with _database() as connection:
        conversations = connection.execute(
            """
            SELECT c.id, c.created_at, c.updated_at,
                   m.body AS last_message, m.sender AS last_sender
            FROM conversations AS c
            LEFT JOIN messages AS m
              ON m.id = (
                  SELECT id FROM messages
                  WHERE conversation_id = c.id
                  ORDER BY id DESC LIMIT 1
              )
            ORDER BY c.updated_at DESC
            """
        ).fetchall()
    return {
        "conversations": [dict(conversation) for conversation in conversations]
    }


@chat_blueprint.get("/chat/history")
def visitor_chat_history():
    conversation_id = get_visitor_id()
    _ensure_conversation(conversation_id)
    with _database() as connection:
        messages = connection.execute(
            """
            SELECT sender, body, sent_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id DESC
            LIMIT 100
            """,
            (conversation_id,),
        ).fetchall()
    return {"messages": [dict(message) for message in reversed(messages)]}


@socketio.on("connect")
def connect():
    if session.get("operator_auth_token"):
        if not _operator_is_authenticated():
            return False
        join_room(OPERATOR_ROOM)
        with operator_state_lock:
            operator_sockets.setdefault(session["operator_auth_token"], set()).add(
                request.sid
            )
    else:
        conversation_id = session.get("chat_visitor_id")
        if not conversation_id:
            return False
        _ensure_conversation(conversation_id)
        join_room(_conversation_room(conversation_id))


@socketio.on("disconnect")
def disconnect_operator():
    auth_token = session.get("operator_auth_token")
    if not isinstance(auth_token, str):
        return
    with operator_state_lock:
        sockets = operator_sockets.get(auth_token)
        if sockets:
            sockets.discard(request.sid)
            if not sockets:
                operator_sockets.pop(auth_token, None)


@socketio.on("chat:select")
def select_conversation(payload):
    if not _operator_is_authenticated():
        emit("chat:error", {"message": "Login operator diperlukan."})
        return

    conversation_id = payload.get("conversation_id") if isinstance(payload, dict) else None
    if not isinstance(conversation_id, str) or not conversation_id:
        emit("chat:error", {"message": "Percakapan tidak valid."})
        return

    with _database() as connection:
        exists = connection.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
    if not exists:
        emit("chat:error", {"message": "Percakapan tidak ditemukan."})
        return

    join_room(_conversation_room(conversation_id))
    emit("chat:history", {"conversation_id": conversation_id, "messages": _read_messages(conversation_id)})


def _read_messages(conversation_id):
    with _database() as connection:
        messages = connection.execute(
            """
            SELECT sender, body, sent_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id DESC
            LIMIT 100
            """,
            (conversation_id,),
        ).fetchall()
    return [dict(message) for message in reversed(messages)]


@socketio.on("chat:send")
def send_message(payload):
    if not isinstance(payload, dict):
        emit("chat:error", {"message": "Format pesan tidak valid."})
        return

    body = payload.get("body")
    if not isinstance(body, str):
        emit("chat:error", {"message": "Pesan harus berupa teks."})
        return
    body = body.strip()
    if not body or len(body) > MAX_MESSAGE_LENGTH:
        emit(
            "chat:error",
            {"message": f"Pesan harus berisi 1 sampai {MAX_MESSAGE_LENGTH} karakter."},
        )
        return

    if session.get("operator_auth_token"):
        if not _operator_is_authenticated():
            emit("chat:error", {"message": "Sesi operator sudah berakhir."})
            return
        conversation_id = payload.get("conversation_id")
        if not isinstance(conversation_id, str) or not conversation_id:
            emit("chat:error", {"message": "Pilih percakapan sebelum membalas."})
            return
        sender = "operator"
        with _database() as connection:
            exists = connection.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        if not exists:
            emit("chat:error", {"message": "Percakapan tidak ditemukan."})
            return
    else:
        conversation_id = session.get("chat_visitor_id")
        if not conversation_id:
            emit("chat:error", {"message": "Sesi chat tidak valid. Muat ulang halaman."})
            return
        sender = "visitor"
        _ensure_conversation(conversation_id)

    sent_at = _timestamp()
    try:
        with _database() as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages (conversation_id, sender, body, sent_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, sender, body, sent_at),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (sent_at, conversation_id),
            )
            message_id = cursor.lastrowid
    except sqlite3.Error:
        logger.exception("Unable to save live chat message")
        emit("chat:error", {"message": "Pesan gagal disimpan. Silakan coba lagi."})
        return

    message = {
        "id": message_id,
        "conversation_id": conversation_id,
        "sender": sender,
        "body": body,
        "sent_at": sent_at,
    }
    socketio.emit("chat:message", message, to=_conversation_room(conversation_id))
    socketio.emit("chat:conversation", message, to=OPERATOR_ROOM)
