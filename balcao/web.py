import io
import secrets
import sqlite3
import tempfile
import time
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, request, send_file, session
from werkzeug.security import check_password_hash, generate_password_hash

from . import __version__
from .core import Store, text


def create_app(directory):
    store = Store(directory)
    key = store.directory / ".session-key"
    try:
        with key.open("x",encoding="ascii") as file:
            file.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    app = Flask(__name__, static_folder="frontend",static_url_path="/static")
    app.secret_key = key.read_text(encoding="ascii")
    app.config.update(MAX_CONTENT_LENGTH=256_000,TRUSTED_HOSTS=["localhost","127.0.0.1","[::1]"],
                      SESSION_COOKIE_NAME="balcao_session",SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Strict",PERMANENT_SESSION_LIFETIME=12*60*60)
    app.extensions["store"] = store
    failures = []
    auth_lock = Lock()

    def profile():
        with store.db() as db:
            row = db.execute("SELECT * FROM profile WHERE id=1").fetchone()
            return dict(row) if row else None

    @app.before_request
    def guard():
        if request.remote_addr not in ("127.0.0.1","::1"):
            return jsonify(error="Esta versão funciona somente no computador do caixa."),403
        if not request.path.startswith("/api/"):
            return None
        if request.method != "GET" and not secrets.compare_digest(str(session.get("csrf","missing")),str(request.headers.get("X-CSRF-Token",""))):
            return jsonify(error="A sessão mudou. Atualize a página e tente novamente."),403
        if request.path not in ("/api/session","/api/setup","/api/login") and not session.get("authenticated"):
            return jsonify(error="Entre para continuar."),401

    @app.after_request
    def headers(response):
        response.headers.update({"X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer",
            "Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)),400

    @app.errorhandler(sqlite3.OperationalError)
    def database_error(error):
        app.logger.error("Falha no banco do caixa: %s",type(error).__name__)
        return jsonify(error="Não foi possível acessar os dados. Confira o espaço no disco e tente novamente."),503

    def body():
        data = request.get_json(silent=True)
        if not isinstance(data,dict):
            raise ValueError("Envie os campos do formulário e tente novamente.")
        return data

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/health")
    def health():
        return jsonify(app="balcao",version=__version__)

    @app.get("/api/session")
    def session_info():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        owner = profile()
        return jsonify(configured=owner is not None,authenticated=bool(session.get("authenticated")),
                       name=owner["name"] if owner and session.get("authenticated") else "",
                       csrf=session["csrf"],version=__version__)

    @app.post("/api/setup")
    def setup():
        data = body()
        name = text(data.get("name"),"o nome do negócio",100)
        password = data.get("password","")
        if not isinstance(password,str) or not 10 <= len(password) <= 200:
            raise ValueError("Crie uma senha com 10 a 200 caracteres.")
        with auth_lock,store.db(True) as db:
            if db.execute("SELECT 1 FROM profile").fetchone():
                return jsonify(error="O acesso já foi configurado. Entre com a senha."),409
            db.execute("INSERT INTO profile(id,name,password) VALUES(1,?,?)",(name,generate_password_hash(password)))
        session.clear()
        session.update(authenticated=True,csrf=secrets.token_urlsafe(32))
        session.permanent = True
        return jsonify(ok=True)

    @app.post("/api/login")
    def login():
        data = body()
        password = data.get("password","")
        if not isinstance(password,str) or len(password)>200:
            raise ValueError("Confira a senha.")
        with auth_lock:
            failures[:] = [stamp for stamp in failures if time.monotonic()-stamp<60]
            if len(failures)>=5:
                return jsonify(error="Aguarde um minuto antes de tentar outra senha."),429
            owner = profile()
            if not owner or not check_password_hash(owner["password"],password):
                failures.append(time.monotonic())
                return jsonify(error="Senha incorreta. Confira e tente novamente."),401
            failures.clear()
        session.clear()
        session.update(authenticated=True,csrf=secrets.token_urlsafe(32))
        session.permanent = True
        return jsonify(ok=True)

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/data")
    def data():
        return jsonify(store.data())

    @app.post("/api/products")
    def product_new():
        return jsonify(store.product(body()))

    @app.post("/api/products/<int:product_id>")
    def product_edit(product_id):
        return jsonify(store.product(body(),product_id))

    @app.post("/api/products/<int:product_id>/stock")
    def stock(product_id):
        data = body()
        store.adjust(product_id,data.get("quantity",""),data.get("reason"))
        return jsonify(ok=True)

    @app.post("/api/shifts/open")
    def shift_open():
        data = body()
        return jsonify(id=store.open(data.get("operator"),data.get("opening","")))

    @app.post("/api/shifts/close")
    def shift_close():
        data = body()
        return jsonify(store.close(data.get("counted",""),data.get("shift_id")))

    @app.post("/api/shifts/movement")
    def shift_move():
        data = body()
        store.movement(data.get("amount",""),data.get("kind"),data.get("reason"),data.get("shift_id"))
        return jsonify(ok=True)

    @app.post("/api/sales")
    def sale_new():
        return jsonify(store.sell(body()))

    @app.get("/api/sales/<int:sale_id>")
    def sale_detail(sale_id):
        return jsonify(store.sale(sale_id))

    @app.post("/api/sales/<int:sale_id>/cancel")
    def cancel(sale_id):
        data = body()
        return jsonify(store.cancel(sale_id,data.get("reason"),data.get("confirmed") is True))

    @app.get("/api/backup")
    def backup():
        with tempfile.TemporaryDirectory(prefix="Balcao-backup-") as folder:
            target = Path(folder)/"backup.sqlite3"
            store.backup(target)
            content = target.read_bytes()
        return send_file(io.BytesIO(content),download_name="Balcao-backup.sqlite3",as_attachment=True,mimetype="application/octet-stream")

    return app
