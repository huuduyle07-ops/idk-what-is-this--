import pytest
from web.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

def test_help_route_returns_200(client):
    resp = client.get('/help')
    assert resp.status_code == 200

def test_help_route_returns_html_fragment(client):
    resp = client.get('/help')
    data = resp.get_data(as_text=True)
    assert '<h' in data

def test_help_route_content_type(client):
    resp = client.get('/help')
    assert 'text/plain' in resp.content_type
    assert resp.headers['X-Content-Type-Options'] == 'nosniff'
