"""Package loading and HTTP boundary checks without a running database."""
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app import create_app


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_all_modules_import(self):
        root = Path(__file__).resolve().parents[1] / 'backend'
        for file in (root / 'app').rglob('*.py'):
            name = '.'.join(file.relative_to(root).with_suffix('').parts)
            importlib.import_module(name.removesuffix('.__init__'))

    def test_anonymous_requests_require_login(self):
        response = self.client.get('/api/requests')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_login_cookie_and_authenticated_user(self):
        user = {'id': 1, 'name': '테스트'}
        with patch('app.services.auth_service.login', return_value=(user, 'session-token')):
            response = self.client.post('/api/auth/login', json={'login_id': 'demo', 'password': 'demo'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('collab_session=session-token', response.headers['Set-Cookie'])
        self.assertIn('HttpOnly', response.headers['Set-Cookie'])
        with patch('app.services.auth_service.session_user', return_value=user):
            self.assertEqual(self.client.get('/api/auth/me').json, {'user': user})

    def test_invalid_request_boundaries(self):
        self.assertEqual(self.client.post('/api/auth/login', data='text').status_code, 415)
        self.assertEqual(self.client.post('/api/auth/login', json={}, headers={'Origin': 'https://other.example'}).status_code, 403)

    def test_health_route(self):
        with patch('app.services.auth_service.health', return_value={'ok': True, 'initialized': True}):
            self.assertEqual(self.client.get('/api/health').json, {'ok': True, 'initialized': True})


if __name__ == '__main__':
    unittest.main()
