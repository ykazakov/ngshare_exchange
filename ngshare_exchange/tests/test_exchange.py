import json
import logging
from pathlib import Path
import os
from shutil import copyfile

from jupyter_core.paths import jupyter_data_dir
from nbgrader.exchange import ExchangeError
import requests
from requests import PreparedRequest
from _pytest.logging import LogCaptureFixture
import pytest

from .. import Exchange
from .base import TestExchange


default_cache = None


@pytest.fixture(scope='module', autouse=True)
def get_default_cache():
    global default_cache
    default_cache = Exchange.cache.get(Exchange())


class TestExchangeClass(TestExchange):
    def _get_encoded_tree(self):
        return [
            {'path': 'problem1.ipynb', 'content': 'abcdefgh'},
            {'path': 'ignore_me.ipynb', 'content': 'ijklmnop'},
        ]

    def _get_encoded_subdir_tree(self):
        return [
            {'path': 'path/problem1.ipynb', 'content': 'abcdefgh'},
            {'path': 'path/to/notebook/problem1.ipynb', 'content': 'ijklmnop'},
            {'path': 'path/ignore_me.ipynb', 'content': 'qrstuvwx'},
        ]

    def _get_response(self, status_code, json):
        url = 'http://_get_response'
        self.requests_mocker.get(url, status_code=status_code, json=json)
        response = requests.get(url)
        return response

    def _new_exchange(
        self,
        course_id=TestExchange.course_id,
        assignment_id=TestExchange.assignment_id,
        student_id=TestExchange.student_id,
    ):
        return self._new_exchange_object(
            Exchange, course_id, assignment_id, student_id
        )

    @pytest.fixture(autouse=True)
    def init_exchange(self):
        env_proxy = 'PROXY_PUBLIC_SERVICE_HOST'
        if env_proxy in os.environ:
            del os.environ[env_proxy]
        if not hasattr(self, 'default_cache'):
            self.default_cache = Exchange.cache
        self.exchange = self._new_exchange()
        os.chdir(self.course_dir)

    def test_ngshare_url(self):
        url = 'http://some.random.url'
        self.exchange._ngshare_url = url
        assert self.exchange.ngshare_url == url

    def test_proxy_public_url(self):
        os.environ['PROXY_PUBLIC_SERVICE_HOST'] = 'http://proxy-public'
        self.exchange._ngshare_url = ''
        url = self.exchange.ngshare_url
        assert url == 'http://proxy-public/services/ngshare'

    def test_no_ngshare_url(self):
        self.exchange._ngshare_url = ''
        with pytest.raises(Exception):
            self.exchange.ngshare_url

    def test_check_response_good(self):
        url = self.exchange.ngshare_url
        response = self._get_response(200, {'success': True})
        assert response.json() == self.exchange._ngshare_api_check_error(
            response, url
        )

    def test_check_response_bad_status(self):
        url = self.exchange.ngshare_url
        response = self._get_response(400, {'success': True})
        assert response.json() == self.exchange._ngshare_api_check_error(
            response, url
        )

    def test_check_response_unsuccessful(self):
        url = self.exchange.ngshare_url
        response = self._get_response(200, {'success': False})
        assert None is self.exchange._ngshare_api_check_error(response, url)

    def test_check_response_bad_status_unsuccessful(self):
        url = self.exchange.ngshare_url
        response = self._get_response(400, {'success': False})
        assert None is self.exchange._ngshare_api_check_error(response, url)

    def test_ngshare_headers(self):
        token = 'unique_token'
        os.environ['JUPYTERHUB_API_TOKEN'] = token

        def request_handler(request: PreparedRequest, context):
            assert 'Authorization' in request.headers
            assert request.headers['Authorization'] == 'token ' + token
            return {'success': True, 'passed': True}

        url = self.exchange.ngshare_url
        self.requests_mocker.get(url, json=request_handler)
        response = self.exchange.ngshare_api_get('')
        assert 'passed' in response

    def test_ngshare_exception(self):
        url = self.exchange.ngshare_url
        self.requests_mocker.get(url, exc=requests.exceptions.ConnectionError)
        response = self.exchange.ngshare_api_get('')
        assert response is None

    def test_default_cache_dir(self):
        dir = default_cache
        assert Path(dir) == Path(jupyter_data_dir()) / 'nbgrader_cache'

    def test_decode_clobber(self):
        src = self._get_encoded_tree()
        existing = self.course_dir / 'problem1.ipynb'
        existing.write_bytes(b'Not clobbered')
        self.exchange.decode_dir(src, self.course_dir, noclobber=False)
        assert existing.read_bytes() != b'Not clobbered'

    def test_decode_no_clobber(self):
        src = self._get_encoded_tree()
        existing = self.course_dir / 'problem1.ipynb'
        existing.write_bytes(b'Not clobbered')
        self.exchange.decode_dir(src, self.course_dir, noclobber=True)
        assert existing.read_bytes() == b'Not clobbered'

    def test_decode_ignore(self):
        src = self._get_encoded_tree()
        ignore_patterns = self.exchange.ignore_patterns()
        self.exchange.coursedir.ignore.append('ignore_me*')
        self.exchange.decode_dir(src, self.course_dir, ignore=ignore_patterns)
        assert (self.course_dir / 'problem1.ipynb').exists()
        assert not (self.course_dir / 'ignore_me.ipynb').exists()

    def test_decode_no_ignore(self):
        src = self._get_encoded_tree()
        self.exchange.coursedir.ignore.append('ignore_me*')
        self.exchange.decode_dir(src, self.course_dir, ignore=None)
        assert (self.course_dir / 'problem1.ipynb').exists()
        assert (self.course_dir / 'ignore_me.ipynb').exists()

    def test_decode_subdir(self):
        src = self._get_encoded_subdir_tree()
        self.exchange.decode_dir(src, self.course_dir)
        for file in src:
            assert (self.course_dir / file['path']).exists()

    def test_decode_subdir_ignore(self):
        src = self._get_encoded_subdir_tree()
        ignore_patterns = self.exchange.ignore_patterns()
        self.exchange.coursedir.ignore.append('ignore_me*')
        self.exchange.decode_dir(src, self.course_dir, ignore=ignore_patterns)
        assert (self.course_dir / 'path' / 'problem1.ipynb').exists()
        assert (
            self.course_dir / 'path' / 'to' / 'notebook' / 'problem1.ipynb'
        ).exists()
        assert not (self.course_dir / 'path' / 'ignore_me.ipynb').exists()

    def test_decode_subdir_no_ignore(self):
        src = self._get_encoded_subdir_tree()
        self.exchange.coursedir.ignore.append('ignore_me*')
        self.exchange.decode_dir(src, self.course_dir, ignore=None)
        assert (self.course_dir / 'path' / 'problem1.ipynb').exists()
        assert (
            self.course_dir / 'path' / 'to' / 'notebook' / 'problem1.ipynb'
        ).exists()
        assert (self.course_dir / 'path' / 'ignore_me.ipynb').exists()

    def test_decode_subdir_clobber(self):
        src = self._get_encoded_subdir_tree()
        existing = self.course_dir / 'path' / 'problem1.ipynb'
        existing.parent.mkdir()
        existing.write_bytes(b'Not clobbered')
        self.exchange.decode_dir(src, self.course_dir, noclobber=False)
        assert existing.read_bytes() != b'Not clobbered'

    def test_decode_subdir_no_clobber(self):
        src = self._get_encoded_subdir_tree()
        existing = self.course_dir / 'path' / 'problem1.ipynb'
        existing.parent.mkdir()
        existing.write_bytes(b'Not clobbered')
        self.exchange.decode_dir(src, self.course_dir, noclobber=True)
        assert existing.read_bytes() == b'Not clobbered'

    def test_encode_subdir(self):
        assignment_dir = self.course_dir / self.assignment_id
        nb_path = assignment_dir / 'path' / 'to' / 'notebook' / 'nb.ipynb'
        nb_path.parent.mkdir(parents=True)
        test_path = Path(__file__).parent / 'files' / 'test.ipynb'
        copyfile(test_path, nb_path)
        encoded = json.loads(self.exchange.encode_dir(assignment_dir)['files'])
        assert encoded[0]['path'] == 'path/to/notebook/nb.ipynb'

    def test_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self.exchange.copy_files()
        with pytest.raises(NotImplementedError):
            self.exchange.init_dest()
        with pytest.raises(NotImplementedError):
            self.exchange.init_src()

    def test_assignment_not_found(self, caplog: LogCaptureFixture):
        def read_log(caplog):
            log_records = [
                '[{}] {}\n'.format(x.levelname, x.getMessage())
                for x in caplog.get_records('call')
            ]
            caplog.clear()
            return ''.join(log_records)

        dummy_path = self.course_dir / 'dummy'
        real_path = self.course_dir / self.assignment_id
        dummy_path.mkdir()
        real_path.mkdir()
        caplog.set_level(logging.ERROR)
        self.exchange.src_path = str(dummy_path)

        try:
            self.exchange._assignment_not_found(str(dummy_path), str(real_path))
        except ExchangeError:
            pass
        assert 0 <= read_log(caplog).find('Did you mean: {}'.format(real_path))
