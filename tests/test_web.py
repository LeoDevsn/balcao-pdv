import tempfile
import unittest
from balcao.web import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.app=create_app(temp.name)
        self.app.testing=True
        self.client=self.app.test_client()
        self.csrf=self.client.get('/api/session').json['csrf']

    def post(self,path,data):
        return self.client.post('/api/'+path,json=data,headers={'X-CSRF-Token':self.csrf})

    def setup_owner(self):
        self.assertEqual(self.post('setup',dict(name='Mercado de teste',password='senha-exemplo-123')).status_code,200)
        self.csrf=self.client.get('/api/session').json['csrf']

    def test_access_csrf_setup_logout_and_login(self):
        self.assertEqual(self.client.get('/api/data').status_code,401)
        self.assertEqual(self.client.post('/api/setup',json={}).status_code,403)
        self.setup_owner()
        self.assertNotIn('password',self.client.get('/api/session').json)
        self.assertEqual(self.client.get('/api/data').status_code,200)
        self.assertEqual(self.post('setup',dict(name='Outro',password='outra-senha-123')).status_code,409)
        self.post('logout',{})
        self.assertEqual(self.client.get('/api/backup').status_code,401)
        self.csrf=self.client.get('/api/session').json['csrf']
        self.assertEqual(self.post('login',dict(password='incorreta')).status_code,401)
        self.assertEqual(self.post('login',dict(password='senha-exemplo-123')).status_code,200)

    def test_host_local_only_and_security_headers(self):
        self.assertEqual(self.client.get('/health',headers={'Host':'attacker.example'}).status_code,400)
        self.assertEqual(self.client.get('/',environ_overrides={'REMOTE_ADDR':'192.168.1.10'}).status_code,403)
        response=self.client.get('/')
        self.assertIn("frame-ancestors 'none'",response.headers['Content-Security-Policy'])
        self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')

    def test_bad_login_throttled(self):
        self.setup_owner()
        self.post('logout',{})
        self.csrf=self.client.get('/api/session').json['csrf']
        for _ in range(5):
            self.assertEqual(self.post('login',dict(password='erro')).status_code,401)
        self.assertEqual(self.post('login',dict(password='erro')).status_code,429)

    def test_validation_and_api_sale(self):
        self.setup_owner()
        self.assertEqual(self.post('products',dict(name='Sem preço',code='1')).status_code,400)
        product=self.post('products',dict(name='Café',code='789',unit='un',price='9,50')).json
        self.assertEqual(self.post(f"products/{product['id']}/stock",dict(quantity='10',reason='Entrada')).status_code,200)
        shift=self.post('shifts/open',dict(operator='Teste',opening='10')).json['id']
        sale=self.post('sales',dict(shift_id=shift,nonce='nonce-teste-000001',method='cash',received='10',items=[dict(id=product['id'],price=950,quantity='1')]))
        self.assertEqual(sale.status_code,200)
        self.assertEqual(sale.json['change'],50)
        self.assertEqual(self.client.get('/api/backup').data[:16],b'SQLite format 3\x00')
        self.assertEqual(self.post('sales/1/cancel',dict(reason='Teste',confirmed=True)).status_code,200)


if __name__ == '__main__':
    unittest.main()
