import secrets
import sqlite3
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from balcao.core import Store, number


class SalesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.unit = self.store.product(dict(name="Arroz 1 kg",code="7891001",unit="un",price="6,49",minimum="2"))
        self.weight = self.store.product(dict(name="Banana",code="42",unit="kg",price="12,00",minimum="1"))
        self.store.adjust(self.unit["id"],"10","Estoque inicial")
        self.store.adjust(self.weight["id"],"5","Estoque inicial")
        self.shift = self.store.open("Operador", "100,00")

    def order(self,product=None,quantity="1",**extra):
        p = product or self.unit
        return {"shift_id":self.shift,"items":[{"id":p["id"],"price":p["price"],"quantity":quantity}],
                "method":"cash","received":"50,00","nonce":secrets.token_hex(16),**extra}

    def stock(self,product):
        return next(p["stock"] for p in self.store.data()["products"] if p["id"] == product["id"])

    def test_numbers_reject_ambiguous_and_fractional_cents(self):
        for value in ("1.250,00","NaN","Infinity","1e3","1.001","-1",None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                number(value)
        self.assertEqual(number("1,25"),125)
        self.assertEqual(number("0.750",1000),750)

    def test_weight_calculation_and_change(self):
        sale = self.store.sell(self.order(self.weight,"0,750",received="10"))
        self.assertEqual((sale["total"],sale["change"]),(900,100))
        self.assertEqual(self.stock(self.weight),4250)
        self.assertEqual(self.store.data()["shift"]["expected"],10900)

    def test_half_cent_rounds_up_per_product(self):
        p=self.store.product(dict(name="Produto a peso",code="43",unit="kg",price="0,05"))
        self.store.adjust(p["id"],"1","Entrada")
        sale=self.store.sell(self.order(p,"0,1"))
        self.assertEqual(sale["total"],1)

    def test_repeated_sale_returns_same_after_shift_closed(self):
        order=self.order()
        first=self.store.sell(order)
        self.store.close("106,49",self.shift)
        self.assertEqual(self.store.sell(order)["id"],first["id"])
        self.assertEqual(len(self.store.data()["sales"]),1)
        self.assertEqual(self.stock(self.unit),9000)
        with self.assertRaises(ValueError):
            self.store.sell({**order,"received":"60"})

    def test_insufficient_stock_and_payment_are_atomic(self):
        for order in (self.order(quantity="11"),self.order(received="1"),self.order(quantity="1,5"),self.order(method="pix",confirmed=False),self.order(shift_id=99)):
            with self.assertRaises(ValueError):
                self.store.sell(order)
        self.assertEqual(self.stock(self.unit),10000)
        self.assertEqual(self.store.data()["sales"],[])
        self.assertEqual(self.store.data()["shift"]["expected"],10000)

    def test_repeated_item_cannot_oversell(self):
        order=self.order(quantity="6")
        order["items"]*=2
        with self.assertRaises(ValueError):
            self.store.sell(order)
        self.assertEqual(self.stock(self.unit),10000)

    def test_price_changes_require_operator_review(self):
        old=self.order()
        self.store.product(dict(name="Arroz",code="7891001",unit="un",price="7"),self.unit["id"])
        with self.assertRaisesRegex(ValueError,"preço mudou"):
            self.store.sell(old)
        old["items"][0]["price"]=0
        with self.assertRaises(ValueError):
            self.store.sell(old)

    def test_concurrent_sales_cannot_oversell(self):
        orders=[self.order(quantity="8",received="100") for _ in range(2)]
        def sell(order):
            try:
                return self.store.sell(order)["id"]
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(sell,orders))
        self.assertEqual(sum(r is not None for r in results),1)
        self.assertEqual(self.stock(self.unit),2000)

    def test_external_payments_are_records_not_cash(self):
        for method in ("pix","card"):
            sale=self.store.sell(self.order(method=method,confirmed=True))
            self.assertEqual(sale["change"],0)
        self.assertEqual(self.store.data()["shift"]["expected"],10000)

    def test_cancel_is_audited_and_idempotent(self):
        sale=self.store.sell(self.order())
        with self.assertRaises(ValueError):
            self.store.cancel(sale["id"],"Erro",False)
        self.store.cancel(sale["id"],"Cliente desistiu",True)
        self.store.cancel(sale["id"],"Cliente desistiu",True)
        self.assertEqual(self.stock(self.unit),10000)
        self.assertEqual(self.store.data()["shift"]["expected"],10000)
        self.assertTrue(self.store.sale(sale["id"])["cancelled"])

    def test_cancel_old_shift_is_rejected(self):
        sale=self.store.sell(self.order())
        self.store.close("106,49",self.shift)
        new=self.store.open("Segundo turno","0")
        with self.assertRaises(ValueError):
            self.store.cancel(sale["id"],"Erro",True)
        with self.assertRaises(ValueError):
            self.store.close("0",self.shift)
        self.assertEqual(self.store.data()["shift"]["id"],new)

    def test_cash_balance_and_difference(self):
        self.store.movement("20","deposit","Troco adicional",self.shift)
        self.store.movement("5","withdrawal","Retirada",self.shift)
        with self.assertRaises(ValueError):
            self.store.movement("200","withdrawal","Retirada",self.shift)
        closed=self.store.close("114",self.shift)
        self.assertEqual(closed,{"expected":11500,"counted":11400,"difference":-100})

    def test_stock_validation_unique_codes_and_fixed_unit(self):
        with self.assertRaises(ValueError):
            self.store.product(dict(name="Outro",code="7891001",price="1"))
        for quantity in ("-11","0","0,5"):
            with self.assertRaises(ValueError):
                self.store.adjust(self.unit["id"],quantity,"Ajuste")
        with self.assertRaises(ValueError):
            self.store.product(dict(name="Arroz",code="7891001",unit="kg",price="1"),self.unit["id"])

    def test_backup_is_consistent_and_keeps_history(self):
        self.store.sell(self.order())
        target=Path(self.temp.name)/"backup.sqlite3"
        self.store.backup(target)
        with closing(sqlite3.connect(target)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sales").fetchone()[0],1)


if __name__ == "__main__":
    unittest.main()
