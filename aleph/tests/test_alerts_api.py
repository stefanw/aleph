import json

from aleph.core import db
from aleph.model import Alert
from aleph.tests.util import TestCase


class AlertsApiTestCase(TestCase):

    def setUp(self):
        super(AlertsApiTestCase, self).setUp()

    def test_index(self):
        res = self.client.get('/api/1/alerts')
        assert res.status_code == 403, res
        self.login()
        res = self.client.get('/api/1/alerts')
        assert res.status_code == 200, res
        assert res.json['total'] == 0, res.json

    def test_create(self):
        data = {'query': {}}
        jdata = json.dumps(data)
        res = self.client.post('/api/1/alerts', data=jdata,
                               content_type='application/json')
        assert res.status_code == 403, res
        self.login()
        res = self.client.post('/api/1/alerts', data=jdata,
                               content_type='application/json')
        assert res.status_code == 200, res.json
        assert 'Everything' in res.json['label'], res.json

    def test_create_with_label(self):
        data = {'query': {}, 'custom_label': 'banana'}
        jdata = json.dumps(data)
        self.login()
        res = self.client.post('/api/1/alerts', data=jdata,
                               content_type='application/json')
        assert res.status_code == 200, res.json
        assert 'banana' in res.json['label'], res.json

    def test_create_with_query(self):
        data = {'query': {'q': 'putin'}}
        jdata = json.dumps(data)
        self.login()
        res = self.client.post('/api/1/alerts', data=jdata,
                               content_type='application/json')
        assert res.status_code == 200, res.json
        assert 'Results matching' in res.json['label'], res.json
        assert res.json['query']['q'] == ['putin'], res.json

    def test_view(self):
        data = {'query': {'q': 'putin'}}
        jdata = json.dumps(data)
        self.login()
        res = self.client.post('/api/1/alerts', data=jdata,
                               content_type='application/json')
        url = '/api/1/alerts/%s' % res.json['id']
        res2 = self.client.get(url)
        assert res2.json['id'] == res.json['id'], res2.json

        res3 = self.client.get('/api/1/alerts/100000')
        assert res3.status_code == 404, res3

    def test_delete(self):
        data = {'query': {'q': 'putin'}}
        jdata = json.dumps(data)
        self.login()
        res = self.client.post('/api/1/alerts', data=jdata,
                               content_type='application/json')
        assert res.status_code == 200, res.json

        count = Alert.all().count()
        url = '/api/1/alerts/%s' % res.json['id']
        res = self.client.delete(url)
        assert res.status_code == 200, res.json
        new_count = Alert.all().count()
        real_count = db.session.query(Alert).count()
        assert count == real_count, (count, real_count)
        assert new_count == real_count - 1
