"""Regras do caixa. Valores em centavos; quantidades em milésimos."""
import hashlib
import json
import re
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def text(value, label, limit=150):
    value = str(value or "").strip()
    if not value or len(value) > limit:
        raise ValueError(f"Informe {label} com até {limit} caracteres.")
    return value


def number(value, scale=100, *, negative=False):
    raw = str(value).strip()
    if not re.fullmatch(r"-?\d+(?:[,.]\d+)?", raw):
        raise ValueError("Use um número sem separador de milhar. Ex.: 12,50.")
    try:
        amount = Decimal(raw.replace(",", ".")) * scale
        if amount != amount.to_integral_value() or abs(amount) > 1_000_000_000 or (amount < 0 and not negative):
            raise ValueError("Valor fora do limite ou com casas decimais demais.")
        return int(amount)
    except InvalidOperation:
        raise ValueError("Confira o valor informado.") from None


def money(cents):
    return f"R$ {cents / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "balcao.sqlite3"
        with self.db() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS products(
              id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE COLLATE NOCASE,
              name TEXT NOT NULL, unit TEXT NOT NULL CHECK(unit IN ('un','kg')),
              price INTEGER NOT NULL CHECK(price>=0), stock INTEGER NOT NULL DEFAULT 0 CHECK(stock>=0),
              minimum INTEGER NOT NULL DEFAULT 0, updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS shifts(
              id INTEGER PRIMARY KEY, operator TEXT NOT NULL, opened TEXT NOT NULL,
              closed TEXT, opening INTEGER NOT NULL, counted INTEGER, expected INTEGER, difference INTEGER);
            CREATE UNIQUE INDEX IF NOT EXISTS one_open_shift ON shifts((1)) WHERE closed IS NULL;
            CREATE TABLE IF NOT EXISTS sales(
              id INTEGER PRIMARY KEY, shift_id INTEGER NOT NULL REFERENCES shifts(id),
              created TEXT NOT NULL, total INTEGER NOT NULL, method TEXT NOT NULL,
              received INTEGER NOT NULL, change INTEGER NOT NULL, nonce TEXT NOT NULL UNIQUE,
              signature TEXT NOT NULL, cancelled TEXT, cancel_reason TEXT);
            CREATE TABLE IF NOT EXISTS sale_items(
              id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id),
              product_id INTEGER NOT NULL REFERENCES products(id), code TEXT NOT NULL,
              name TEXT NOT NULL, unit TEXT NOT NULL, quantity INTEGER NOT NULL,
              price INTEGER NOT NULL, total INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS stock_moves(
              id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id),
              delta INTEGER NOT NULL, reason TEXT NOT NULL, sale_id INTEGER REFERENCES sales(id), created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cash_moves(
              id INTEGER PRIMARY KEY, shift_id INTEGER NOT NULL REFERENCES shifts(id),
              amount INTEGER NOT NULL, kind TEXT NOT NULL, reason TEXT NOT NULL,
              sale_id INTEGER REFERENCES sales(id), created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS profile(id INTEGER PRIMARY KEY CHECK(id=1),name TEXT NOT NULL,password TEXT NOT NULL);
            PRAGMA user_version=1;
            """)

    @contextmanager
    def db(self, transaction=False):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if transaction:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def product(self, data, product_id=None):
        name = text(data.get("name"), "o nome do produto")
        code = text(data.get("code"), "o código", 32)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", code):
            raise ValueError("Use apenas letras, números, traço ou sublinhado no código.")
        unit = data.get("unit", "un")
        if unit not in ("un", "kg"):
            raise ValueError("Escolha unidade ou quilograma.")
        price = number(data.get("price", ""))
        minimum = number(data.get("minimum", "0"), 1000)
        if unit == "un" and minimum % 1000:
            raise ValueError("Produtos por unidade precisam de quantidade inteira.")
        try:
            with self.db(True) as db:
                old = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone() if product_id else None
                if product_id and not old:
                    raise ValueError("Produto não encontrado. Atualize a lista.")
                if old and unit != old["unit"]:
                    raise ValueError("A unidade de um produto cadastrado não pode mudar. Crie outro código.")
                if old:
                    db.execute("UPDATE products SET code=?,name=?,unit=?,price=?,minimum=?,updated=? WHERE id=?",
                               (code,name,unit,price,minimum,now(),product_id))
                else:
                    product_id = db.execute("INSERT INTO products(code,name,unit,price,minimum,updated) VALUES(?,?,?,?,?,?)",
                                            (code,name,unit,price,minimum,now())).lastrowid
                return dict(db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone())
        except sqlite3.IntegrityError:
            raise ValueError("Esse código já está cadastrado. Use outro ou edite o produto existente.") from None

    def adjust(self, product_id, quantity, reason):
        delta = number(quantity, 1000, negative=True)
        reason = text(reason, "o motivo da movimentação", 300)
        if not delta:
            raise ValueError("Informe uma quantidade diferente de zero.")
        with self.db(True) as db:
            product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
            if not product:
                raise ValueError("Produto não encontrado.")
            if product["unit"] == "un" and delta % 1000:
                raise ValueError("Este produto é vendido por unidade. Informe um número inteiro.")
            if product["stock"] + delta < 0:
                raise ValueError("A saída é maior que o estoque disponível.")
            db.execute("UPDATE products SET stock=stock+?,updated=? WHERE id=?", (delta,now(),product_id))
            db.execute("INSERT INTO stock_moves(product_id,delta,reason,created) VALUES(?,?,?,?)", (product_id,delta,reason,now()))

    @staticmethod
    def open_shift(db):
        shift = db.execute("SELECT * FROM shifts WHERE closed IS NULL").fetchone()
        if not shift:
            raise ValueError("Abra o caixa antes de registrar esta operação.")
        return shift

    def open(self, operator, opening):
        operator = text(operator, "o nome do operador", 100)
        amount = number(opening)
        with self.db(True) as db:
            if db.execute("SELECT 1 FROM shifts WHERE closed IS NULL").fetchone():
                raise ValueError("Já existe um caixa aberto.")
            shift_id = db.execute("INSERT INTO shifts(operator,opened,opening) VALUES(?,?,?)", (operator,now(),amount)).lastrowid
            db.execute("INSERT INTO cash_moves(shift_id,amount,kind,reason,created) VALUES(?,?,'opening','Fundo de troco',?)", (shift_id,amount,now()))
            return shift_id

    def movement(self, amount, kind, reason, shift_id):
        amount = number(amount)
        reason = text(reason, "o motivo", 300)
        if amount <= 0 or kind not in ("deposit", "withdrawal"):
            raise ValueError("Escolha entrada ou retirada e informe um valor maior que zero.")
        with self.db(True) as db:
            shift = self.open_shift(db)
            if shift["id"] != shift_id:
                raise ValueError("O caixa aberto mudou. Atualize a página antes de continuar.")
            expected = db.execute("SELECT COALESCE(SUM(amount),0) FROM cash_moves WHERE shift_id=?", (shift["id"],)).fetchone()[0]
            if kind == "withdrawal" and amount > expected:
                raise ValueError("A retirada ultrapassa o dinheiro esperado no caixa.")
            db.execute("INSERT INTO cash_moves(shift_id,amount,kind,reason,created) VALUES(?,?,?,?,?)",
                       (shift["id"],amount if kind == "deposit" else -amount,kind,reason,now()))

    def close(self, counted, shift_id):
        amount = number(counted)
        with self.db(True) as db:
            shift = self.open_shift(db)
            if shift["id"] != shift_id:
                raise ValueError("O caixa aberto mudou. Atualize a página antes de fechar.")
            expected = db.execute("SELECT COALESCE(SUM(amount),0) FROM cash_moves WHERE shift_id=?", (shift["id"],)).fetchone()[0]
            db.execute("UPDATE shifts SET closed=?,counted=?,expected=?,difference=? WHERE id=?", (now(),amount,expected,amount-expected,shift["id"]))
            return {"expected":expected,"counted":amount,"difference":amount-expected}

    def sell(self, data):
        nonce = text(data.get("nonce"), "o identificador da venda", 80)
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", nonce):
            raise ValueError("Identificador de venda inválido. Atualize a tela.")
        signature = hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=True).encode()).hexdigest()
        with self.db(True) as db:
            prior = db.execute("SELECT * FROM sales WHERE nonce=?", (nonce,)).fetchone()
            if prior:
                if prior["signature"] != signature:
                    raise ValueError("Esta venda já foi registrada com outros dados. Confira o histórico.")
                return self._sale(db, prior["id"])
            shift = self.open_shift(db)
            if shift["id"] != data.get("shift_id"):
                raise ValueError("O caixa aberto mudou. Atualize a página e confira a venda.")
            items = data.get("items")
            if not isinstance(items,list) or not 1 <= len(items) <= 200:
                raise ValueError("Adicione entre 1 e 200 produtos à venda.")
            quantities = {}
            for item in items:
                if not isinstance(item,dict):
                    raise ValueError("Confira os itens da venda.")
                try:
                    product_id = int(item.get("id",0))
                except (TypeError, ValueError):
                    raise ValueError("Produto inválido.") from None
                quantity = number(item.get("quantity",""),1000)
                if quantity <= 0:
                    raise ValueError("A quantidade deve ser maior que zero.")
                quantities[product_id] = quantities.get(product_id,0)+quantity
            lines = []
            for product_id,quantity in quantities.items():
                product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
                if not product:
                    raise ValueError("Um produto não está mais disponível. Atualize a venda.")
                if product["unit"] == "un" and quantity % 1000:
                    raise ValueError(f"{product['name']} precisa de quantidade inteira.")
                if quantity > product["stock"]:
                    raise ValueError(f"Estoque insuficiente de {product['name']}. Confira o estoque ou a quantidade.")
                if any(i.get("price") != product["price"] for i in items if int(i.get("id",0)) == product_id):
                    raise ValueError("Um preço mudou. Remova o item da venda, atualize a lista e adicione novamente para conferir.")
                total = int((Decimal(product["price"])*quantity/1000).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
                lines.append((product,quantity,total))
            total = sum(line[2] for line in lines)
            if not 0 < total <= 100_000_000:
                raise ValueError("O total da venda deve ser maior que zero e até R$ 1.000.000,00.")
            method = data.get("method")
            if method not in ("cash","pix","card"):
                raise ValueError("Escolha a forma de pagamento.")
            if method != "cash" and data.get("confirmed") is not True:
                raise ValueError("Confirme o recebimento no banco ou na maquininha antes de registrar.")
            received = number(data.get("received","")) if method == "cash" else total
            if received < total:
                raise ValueError("O valor recebido é menor que o total da venda.")
            change = received-total
            sale_id = db.execute("INSERT INTO sales(shift_id,created,total,method,received,change,nonce,signature) VALUES(?,?,?,?,?,?,?,?)",
                                 (shift["id"],now(),total,method,received,change,nonce,signature)).lastrowid
            for product,quantity,line_total in lines:
                db.execute("INSERT INTO sale_items(sale_id,product_id,code,name,unit,quantity,price,total) VALUES(?,?,?,?,?,?,?,?)",
                           (sale_id,product["id"],product["code"],product["name"],product["unit"],quantity,product["price"],line_total))
                db.execute("UPDATE products SET stock=stock-?,updated=? WHERE id=?", (quantity,now(),product["id"]))
                db.execute("INSERT INTO stock_moves(product_id,delta,reason,sale_id,created) VALUES(?,?,'Venda',?,?)", (product["id"],-quantity,sale_id,now()))
            if method == "cash":
                db.execute("INSERT INTO cash_moves(shift_id,amount,kind,reason,sale_id,created) VALUES(?,?,'sale','Venda em dinheiro',?,?)", (shift["id"],total,sale_id,now()))
            return self._sale(db,sale_id)

    @staticmethod
    def _sale(db,sale_id):
        sale = db.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
        if not sale:
            raise ValueError("Venda não encontrada.")
        result = dict(sale)
        for key in ("signature","nonce"):
            result.pop(key,None)
        result["items"] = [dict(i) for i in db.execute("SELECT * FROM sale_items WHERE sale_id=? ORDER BY id", (sale_id,))]
        return result

    def sale(self,sale_id):
        with self.db() as db:
            return self._sale(db,sale_id)

    def cancel(self,sale_id,reason,refund_confirmed=False):
        reason = text(reason,"o motivo do cancelamento",300)
        if not refund_confirmed:
            raise ValueError("Confirme que o valor foi devolvido ao cliente.")
        with self.db(True) as db:
            shift = self.open_shift(db)
            sale = self._sale(db,sale_id)
            if sale["cancelled"]:
                return sale
            if sale["shift_id"] != shift["id"]:
                raise ValueError("Só é possível cancelar vendas do caixa atualmente aberto.")
            if sale["method"] == "cash":
                balance = db.execute("SELECT COALESCE(SUM(amount),0) FROM cash_moves WHERE shift_id=?", (shift["id"],)).fetchone()[0]
                if balance < sale["total"]:
                    raise ValueError("O caixa não tem saldo para essa devolução. Registre a entrada do dinheiro devolvido ao caixa antes de cancelar.")
            for item in sale["items"]:
                db.execute("UPDATE products SET stock=stock+?,updated=? WHERE id=?", (item["quantity"],now(),item["product_id"]))
                db.execute("INSERT INTO stock_moves(product_id,delta,reason,sale_id,created) VALUES(?,?,?, ?,?)", (item["product_id"],item["quantity"],reason,sale_id,now()))
            if sale["method"] == "cash":
                db.execute("INSERT INTO cash_moves(shift_id,amount,kind,reason,sale_id,created) VALUES(?,?,'cancel',?,?,?)", (shift["id"],-sale["total"],reason,sale_id,now()))
            db.execute("UPDATE sales SET cancelled=?,cancel_reason=? WHERE id=?", (now(),reason,sale_id))
            return self._sale(db,sale_id)

    def data(self):
        with self.db(True) as db:
            shift = db.execute("SELECT * FROM shifts WHERE closed IS NULL").fetchone()
            shift = dict(shift) if shift else None
            moves = [dict(m) for m in db.execute("SELECT * FROM cash_moves WHERE shift_id=? ORDER BY id DESC", (shift["id"] if shift else 0,))]
            if shift:
                shift["expected"] = sum(m["amount"] for m in moves)
            return {"products":[dict(p) for p in db.execute("SELECT * FROM products ORDER BY name COLLATE NOCASE")],
                    "shift":shift,"moves":moves,
                    "sales":[dict(s) for s in db.execute("SELECT id,shift_id,created,total,method,received,change,cancelled,cancel_reason FROM sales ORDER BY id DESC LIMIT 300")],
                    "shifts":[dict(s) for s in db.execute("SELECT * FROM shifts ORDER BY id DESC LIMIT 100")],
                    "stock_moves":[dict(m) for m in db.execute("SELECT m.*,p.name,p.unit FROM stock_moves m JOIN products p ON p.id=m.product_id ORDER BY m.id DESC LIMIT 100")]}

    def backup(self,target):
        with self.db() as source, closing(sqlite3.connect(target)) as destination:
            source.backup(destination)
