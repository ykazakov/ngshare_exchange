import base64
import hashlib
import logging
import os
from pathlib import Path
import re
import shutil

from _pytest.logging import LogCaptureFixture
from _pytest.legacypath import TempdirFactory
import pytest
from requests import PreparedRequest
from textwrap import dedent
from unittest import TestCase

from .base import parse_body, TestExchange
from nbgrader.auth import Authenticator
from nbgrader.exchange import ExchangeError
from .. import ExchangeList


class TestExchangeList(TestExchange, TestCase):
    course_id2 = 'xyz200'
    assignment_id2 = 'ps2'
    timestamp1 = '2000-02-03 12:34:56.789012 UTC'
    timestamp2 = '2001-02-03 12:34:56.789012 UTC'

    def _delete_assignment(self, request: PreparedRequest, context):
        if not self.is_instructor:
            return {'success': False, 'message': 'Permission denied'}
        self.test_completed = True
        return {'success': True}

    def _feedback_content(self):
        reference_file = self.files_path / 'feedback.html'
        with open(reference_file, 'rb') as file:
            return file.read()

    def _fetch(self, course_dir, assignment_id=TestExchange.assignment_id):
        notebook_path = (
            course_dir / assignment_id / (self.notebook_id + '.ipynb')
        )
        notebook_path.parent.mkdir()
        shutil.copyfile(self.files_path / 'test.ipynb', notebook_path)
        pass

    def _fetch_solution(
        self, course_dir, assignment_id=TestExchange.assignment_id
    ):
        notebook_path = (
            course_dir
            / assignment_id
            / 'solution'
            / (self.notebook_id + '.ipynb')
        )
        notebook_path.parent.mkdir(parents=True)
        shutil.copyfile(self.files_path / 'test.ipynb', notebook_path)
        pass

    def _fetch_feedback(self, course_dir, course_id, assignment_id, timestamp):
        feedback_dir = course_dir / assignment_id / 'feedback' / timestamp
        feedback_dir.mkdir(parents=True)
        html_path = feedback_dir / (self.notebook_id + '.html')
        timestamp_path = feedback_dir / 'timestamp.txt'
        shutil.copyfile(self.files_path / 'feedback.html', html_path)
        with open(timestamp_path, 'w') as timestamp_file:
            timestamp_file.write(timestamp)

    def _get_assignment(self, request: PreparedRequest, context):
        content = self._notebook_content()
        md5 = hashlib.md5()
        md5.update(content)
        checksum = md5.hexdigest()
        files = [
            {
                'path': self.notebook_id + '.ipynb',
                'content': base64.b64encode(content).decode(),
                'checksum': checksum,
            }
        ]
        return {'success': True, 'files': files}

    def _get_assignments(self, request: PreparedRequest, context):
        assignments = [self.assignment_id, self.assignment_id2]
        return {
            'success': True,
            'assignments': assignments[: self.num_assignments],
        }

    def _get_solution(self, request: PreparedRequest, context):
        content = self._notebook_content()
        md5 = hashlib.md5()
        md5.update(content)
        checksum = md5.hexdigest()
        files = [
            {
                'path': self.notebook_id + '.ipynb',
                'content': base64.b64encode(content).decode(),
                'checksum': checksum,
            }
        ]
        return {'success': True, 'files': files}

    def _get_solutions(self, request: PreparedRequest, context):
        solutions = [self.assignment_id, self.assignment_id2]
        return {
            'success': True,
            'solutions': solutions[: self.num_solutions],
        }

    def _get_courses(self, request: PreparedRequest, context):
        courses = [self.course_id, self.course_id2]
        return {'success': True, 'courses': courses[: self.num_courses]}

    def _get_feedback(self, request: PreparedRequest, context):
        pattern = re.compile(r'\?[^#]*')
        matches = pattern.findall(request.url)
        if len(matches) == 0 or 'timestamp' not in parse_body(matches[0]):
            print(request)
            return {'success': False, 'message': 'Please supply timestamp'}
        timestamp = parse_body(matches[0])['timestamp']
        if timestamp not in [self.timestamp1, self.timestamp2]:
            return {'success': False, 'message': 'Submission not found'}
        files = []
        if (timestamp == self.timestamp1 and self.num_feedback > 0) or (
            timestamp == self.timestamp2 and self.num_feedback > 1
        ):
            content = self._feedback_content()
            md5 = hashlib.md5()
            md5.update(content)
            checksum = md5.hexdigest()
            files = [
                {
                    'path': self.notebook_id + '.html',
                    'content': base64.b64encode(content).decode(),
                    'checksum': checksum,
                }
            ]
        return {'success': True, 'timestamp': timestamp, 'files': files}

    def _get_student_submissions(self, request: PreparedRequest, context):
        submissions = [
            {'student_id': self.student_id, 'timestamp': self.timestamp1},
            {'student_id': self.student_id, 'timestamp': self.timestamp2},
        ]
        return {
            'success': True,
            'submissions': submissions[: self.num_submissions],
        }

    def _get_submission(self, request: PreparedRequest, context):
        if not self.is_instructor:
            return {'success': False, 'message': 'Permission denied'}
        return self._get_assignment(request, context)

    def _get_submissions(self, request: PreparedRequest, context):
        return self._get_student_submissions(request, context)

    def _mock_error_assignment(self):
        url = '{}/assignment/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id
        )
        self.requests_mocker.get(url, status_code=404)
        url = '{}/assignment/{}/{}'.format(
            self.base_url, self.course_id2, self.assignment_id
        )
        self.requests_mocker.get(url, status_code=404)
        url = '{}/assignment/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id2
        )
        self.requests_mocker.get(url, status_code=404)
        url = '{}/assignment/{}/{}'.format(
            self.base_url, self.course_id2, self.assignment_id2
        )
        self.requests_mocker.get(url, status_code=404)

    def _mock_error_assignments(self):
        url = '{}/assignments/{}'.format(self.base_url, self.course_id)
        self.requests_mocker.get(url, status_code=404)
        url = '{}/assignments/{}'.format(self.base_url, self.course_id2)
        self.requests_mocker.get(url, status_code=404)

    def _mock_error_feedback(self):
        url = '{}/feedback/{}/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id, self.student_id
        )
        self.requests_mocker.get(url, status_code=404)
        url = '{}/feedback/{}/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id2, self.student_id
        )
        self.requests_mocker.get(url, status_code=404)

    def _mock_error_submission(self):
        url = '{}/submission/{}/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id, self.student_id
        )
        self.requests_mocker.get(url, status_code=404)

    def _mock_error_submissions(self):
        url = '{}/submissions/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id
        )
        self.requests_mocker.get(url, status_code=404)

        url = '{}/submissions/{}/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id, self.student_id
        )
        self.requests_mocker.get(url, status_code=404)

    def _mock_error_unrelease(self):
        url = '{}/assignment/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id
        )
        self.requests_mocker.delete(url, status_code=404)

    def _mock_no_notebook(self):
        url = '{}/submission/{}/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id, self.student_id
        )
        json = {'success': True, 'files': []}
        self.requests_mocker.get(url, json=json)

    def _mock_requests_list(self):
        """
        Mocks ngshare's GET courses, GET assignments, GET assignment, DELETE
        assignment, GET submissions GET student's submissions, GET submission,
        GET feedback, GET solutions, GET solution.
        """
        url = '{}/courses'.format(self.base_url)
        self.requests_mocker.get(url, json=self._get_courses)

        url = '{}/assignments/{}'.format(self.base_url, self.course_id)
        self.requests_mocker.get(url, json=self._get_assignments)
        url = '{}/assignments/{}'.format(self.base_url, self.course_id2)
        self.requests_mocker.get(url, json=self._get_assignments)

        url = '{}/assignment/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id
        )
        self.requests_mocker.get(url, json=self._get_assignment)
        url = '{}/assignment/{}/{}'.format(
            self.base_url, self.course_id2, self.assignment_id
        )
        self.requests_mocker.get(url, json=self._get_assignment)
        url = '{}/assignment/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id2
        )
        self.requests_mocker.get(url, json=self._get_assignment)
        url = '{}/assignment/{}/{}'.format(
            self.base_url, self.course_id2, self.assignment_id2
        )
        self.requests_mocker.get(url, json=self._get_assignment)

        url = '{}/assignment/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id
        )
        self.requests_mocker.delete(url, json=self._delete_assignment)

        url = '{}/submissions/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id
        )
        self.requests_mocker.get(url, json=self._get_submissions)

        url = '{}/submissions/{}/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id, self.student_id
        )
        self.requests_mocker.get(url, json=self._get_student_submissions)

        url = '{}/submission/{}/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id, self.student_id
        )
        self.requests_mocker.get(url, json=self._get_submission)

        url = '{}/feedback/{}/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id, self.student_id
        )
        self.requests_mocker.get(url, json=self._get_feedback)
        url = '{}/feedback/{}/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id2, self.student_id
        )
        self.requests_mocker.get(url, json=self._get_feedback)
        url = '{}/solutions/{}'.format(self.base_url, self.course_id)
        self.requests_mocker.get(url, json=self._get_solutions)
        url = '{}/solutions/{}'.format(self.base_url, self.course_id2)
        self.requests_mocker.get(url, json=self._get_solutions)
        url = '{}/solution/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id
        )
        self.requests_mocker.get(url, json=self._get_solution)
        url = '{}/solution/{}/{}'.format(
            self.base_url, self.course_id2, self.assignment_id
        )
        self.requests_mocker.get(url, json=self._get_solution)
        url = '{}/solution/{}/{}'.format(
            self.base_url, self.course_id, self.assignment_id2
        )
        self.requests_mocker.get(url, json=self._get_solution)
        url = '{}/solution/{}/{}'.format(
            self.base_url, self.course_id2, self.assignment_id2
        )
        self.requests_mocker.get(url, json=self._get_solution)

    def _new_list(
        self,
        course_id=TestExchange.course_id,
        assignment_id=TestExchange.assignment_id,
        student_id=TestExchange.student_id,
    ):
        retvalue = self._new_exchange_object(
            ExchangeList, course_id, assignment_id, student_id
        )

        class DummyAuthenticator(Authenticator):
            def has_access(self, student_id, course_id):
                return True

        retvalue.authenticator = DummyAuthenticator()
        retvalue.assignment_dir = str(self.course_dir.absolute())
        return retvalue

    def _notebook_content(self):
        reference_file = self.files_path / 'test.ipynb'
        with open(reference_file, 'rb') as file:
            return file.read()

    def _read_log(self):
        log_records = [
            '[{}] {}\n'.format(x.levelname, x.getMessage())
            for x in self.caplog.records
        ]
        self.caplog.clear()
        return ''.join(log_records)

    def _submit(
        self,
        course_id=TestExchange.course_id,
        assignment_id=TestExchange.assignment_id,
        timestamp=timestamp1,
    ):
        assignment_filename = '{}+{}+{}'.format(
            self.student_id, assignment_id, timestamp
        )
        notebook_path = (
            self.cache_dir
            / course_id
            / assignment_filename
            / (self.notebook_id + '.ipynb')
        )
        timestamp_path = notebook_path.parent / 'timestamp.txt'
        notebook_path.parent.mkdir(parents=True)
        shutil.copyfile(self.files_path / 'test.ipynb', notebook_path)
        with open(timestamp_path, 'w') as timestamp_file:
            timestamp_file.write(timestamp)

    @pytest.fixture(autouse=True)
    def init_submit(
        self, caplog: LogCaptureFixture, tmpdir_factory: TempdirFactory
    ):
        self.caplog = caplog
        self.course_dir2 = Path(
            tmpdir_factory.mktemp(self.course_id2)
        ).absolute()
        self._mock_requests_list()
        self.list = self._new_list()
        os.chdir(self.course_dir)
        self.caplog.set_level(logging.INFO)
        self.list.coursedir.course_id = '*'
        self.list.coursedir.assignment_id = '*'
        self.num_courses = 1
        self.num_assignments = 0
        self.num_submissions = 0
        self.num_feedback = 0
        self.num_solutions = 0
        self.is_instructor = True

    def test_404(self):
        self.mock_404()
        try:
            self.list.start()
        except Exception as e:
            assert issubclass(type(e), ExchangeError)

    def test_unsuccessful(self):
        self.mock_unsuccessful()
        try:
            self.list.start()
        except Exception as e:
            assert issubclass(type(e), ExchangeError)

    def test_list_by_student_id_1(self):
        self.num_courses = 2
        self.num_assignments = 1
        self.list.coursedir.course_id = self.course_id
        self.list.coursedir.student_id = self.student_id
        self.list.inbound = True
        self.list.start()

    def test_list_by_student_id_2(self):
        self.num_courses = 2
        self.num_assignments = 1
        self.list.coursedir.course_id = self.course_id
        self.list.coursedir.student_id = ''
        self.list.inbound = True
        self.list.start()

    def test_list_released_2x1_course1(self):
        self.num_courses = 2
        self.num_assignments = 1
        self.list.coursedir.course_id = self.course_id
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "assignment_id": self.assignment_id,
                    "status": "released",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                },
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released assignments:
            [INFO] {} {}
            """
            )
            .lstrip()
            .format(self.course_id, self.assignment_id)
        )

    def test_list_released_2x1_course2(self):
        self.num_courses = 2
        self.num_assignments = 1
        self.list.coursedir.course_id = self.course_id2
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id2,
                    "assignment_id": self.assignment_id,
                    "status": "released",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                },
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released assignments:
            [INFO] {} {}
            """
            )
            .lstrip()
            .format(self.course_id2, self.assignment_id)
        )

    def test_list_released_2x1(self):
        self.num_courses = 2
        self.num_assignments = 1
        self.list.coursedir.course_id = '*'
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": course_id,
                    "assignment_id": self.assignment_id,
                    "status": "released",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                }
                for course_id in (self.course_id, self.course_id2)
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released assignments:
            [INFO] {} {}
            [INFO] {} {}
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.assignment_id,
                self.course_id2,
                self.assignment_id,
            )
        )

    def test_list_released_2x2_assignment1(self):
        self.num_courses = 2
        self.num_assignments = 2
        self.list.coursedir.assignment_id = self.assignment_id
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": course_id,
                    "assignment_id": self.assignment_id,
                    "status": "released",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                }
                for course_id in (self.course_id, self.course_id2)
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released assignments:
            [INFO] {} {}
            [INFO] {} {}
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.assignment_id,
                self.course_id2,
                self.assignment_id,
            )
        )

    def test_list_released_2x2_assignment2(self):
        self.num_courses = 2
        self.num_assignments = 2
        self.list.coursedir.assignment_id = self.assignment_id2
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": course_id,
                    "assignment_id": self.assignment_id2,
                    "status": "released",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                }
                for course_id in (self.course_id, self.course_id2)
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released assignments:
            [INFO] {} {}
            [INFO] {} {}
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.assignment_id2,
                self.course_id2,
                self.assignment_id2,
            )
        )

    def test_list_released_2x2(self):
        self.num_courses = 2
        self.num_assignments = 2
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "status": "released",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                }
                for course_id in (self.course_id, self.course_id2)
                for assignment_id in (self.assignment_id, self.assignment_id2)
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released assignments:
            [INFO] {} {}
            [INFO] {} {}
            [INFO] {} {}
            [INFO] {} {}
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.assignment_id,
                self.course_id,
                self.assignment_id2,
                self.course_id2,
                self.assignment_id,
                self.course_id2,
                self.assignment_id2,
            )
        )

    def test_list_fetched(self):
        self.num_assignments = 2
        self._fetch(self.course_dir)
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "assignment_id": self.assignment_id,
                    "status": "fetched",
                    "path": (self.course_dir / self.assignment_id).as_posix(),
                    "notebooks": [
                        {
                            "notebook_id": self.notebook_id,
                            "path": (
                                self.course_dir
                                / self.assignment_id
                                / (self.notebook_id + '.ipynb')
                            ).as_posix(),
                        }
                    ],
                },
                {
                    "course_id": self.course_id,
                    "assignment_id": self.assignment_id2,
                    "status": "released",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                },
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released assignments:
            [INFO] {} {} (already downloaded)
            [INFO] {} {}
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.assignment_id,
                self.course_id,
                self.assignment_id2,
            )
        )

    def test_list_solution_2x1_course1(self):
        self.num_courses = 2
        self.num_solutions = 1
        self.list.coursedir.course_id = self.course_id
        self.list.solution = True
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "assignment_id": self.assignment_id,
                    "status": "fetch_assignment",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                },
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released solutions:
            [INFO] {} {} (download assignment!)
            """
            )
            .lstrip()
            .format(self.course_id, self.assignment_id)
        )

    def test_list_solution_2x1_course2(self):
        self.num_courses = 2
        self.num_solutions = 1
        self.list.coursedir.course_id = self.course_id2
        self.list.solution = True
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id2,
                    "assignment_id": self.assignment_id,
                    "status": "fetch_assignment",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                },
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released solutions:
            [INFO] {} {} (download assignment!)
            """
            )
            .lstrip()
            .format(self.course_id2, self.assignment_id)
        )

    def test_list_solution_2x1(self):
        self.num_courses = 2
        self.num_solutions = 1
        self.list.coursedir.course_id = '*'
        self.list.solution = True
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": course_id,
                    "assignment_id": self.assignment_id,
                    "status": "fetch_assignment",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                }
                for course_id in (self.course_id, self.course_id2)
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released solutions:
            [INFO] {} {} (download assignment!)
            [INFO] {} {} (download assignment!)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.assignment_id,
                self.course_id2,
                self.assignment_id,
            )
        )

    def test_list_solution_2x2_assignment1(self):
        self.num_courses = 2
        self.num_solutions = 2
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.solution = True
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": course_id,
                    "assignment_id": self.assignment_id,
                    "status": "fetch_assignment",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                }
                for course_id in (self.course_id, self.course_id2)
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released solutions:
            [INFO] {} {} (download assignment!)
            [INFO] {} {} (download assignment!)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.assignment_id,
                self.course_id2,
                self.assignment_id,
            )
        )

    def test_list_solution_2x2_assignment2(self):
        self.num_courses = 2
        self.num_solutions = 2
        self.list.coursedir.assignment_id = self.assignment_id2
        self.list.solution = True
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": course_id,
                    "assignment_id": self.assignment_id2,
                    "status": "fetch_assignment",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                }
                for course_id in (self.course_id, self.course_id2)
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released solutions:
            [INFO] {} {} (download assignment!)
            [INFO] {} {} (download assignment!)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.assignment_id2,
                self.course_id2,
                self.assignment_id2,
            )
        )

    def test_list_solution_2x2(self):
        self.num_courses = 2
        self.num_solutions = 2
        self.list.solution = True
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "status": "fetch_assignment",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                }
                for course_id in (self.course_id, self.course_id2)
                for assignment_id in (self.assignment_id, self.assignment_id2)
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released solutions:
            [INFO] {} {} (download assignment!)
            [INFO] {} {} (download assignment!)
            [INFO] {} {} (download assignment!)
            [INFO] {} {} (download assignment!)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.assignment_id,
                self.course_id,
                self.assignment_id2,
                self.course_id2,
                self.assignment_id,
                self.course_id2,
                self.assignment_id2,
            )
        )

    def test_list_solution_fetched_assignment_1(self):
        self.num_assignments = 2
        self._fetch(self.course_dir)
        self.num_solutions = 2
        self.list.solution = True
        data = self.list.start()
        solution_path = self.course_dir / self.assignment_id / "solution"
        notebook_solution_path = solution_path / (self.notebook_id + '.ipynb')
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "assignment_id": self.assignment_id,
                    "status": "released_solution",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                },
                {
                    "course_id": self.course_id,
                    "assignment_id": self.assignment_id2,
                    "status": "fetch_assignment",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                },
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released solutions:
            [INFO] {} {}
            [INFO] {} {} (download assignment!)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.assignment_id,
                self.course_id,
                self.assignment_id2,
            )
        )

    def test_list_solution_fetched_assignment_2(self):
        self.num_assignments = 2
        self._fetch(self.course_dir)
        self._fetch(self.course_dir, assignment_id=self.assignment_id2)
        self.num_solutions = 2
        self.list.solution = True
        data = self.list.start()
        solution_path = self.course_dir / self.assignment_id / "solution"
        notebook_solution_path = solution_path / (self.notebook_id + '.ipynb')
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "assignment_id": assignment_id,
                    "status": "released_solution",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                }
                for assignment_id in (self.assignment_id, self.assignment_id2)
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released solutions:
            [INFO] {} {}
            [INFO] {} {}
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.assignment_id,
                self.course_id,
                self.assignment_id2,
            )
        )

    def test_list_fetched_solution(self):
        self.num_assignments = 2
        self._fetch(self.course_dir)
        self.num_solutions = 2
        self._fetch_solution(self.course_dir)
        self.list.solution = True
        data = self.list.start()
        solution_path = self.course_dir / self.assignment_id / "solution"
        notebook_solution_path = solution_path / (self.notebook_id + '.ipynb')
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "assignment_id": self.assignment_id,
                    "status": "fetched_solution",
                    "path": solution_path.as_posix(),
                    "notebooks": [
                        {
                            "notebook_id": self.notebook_id,
                            "path": notebook_solution_path.as_posix(),
                        }
                    ],
                },
                {
                    "course_id": self.course_id,
                    "assignment_id": self.assignment_id2,
                    "status": "fetch_assignment",
                    "notebooks": [{"notebook_id": self.notebook_id}],
                },
            ],
        )
        output = self._read_log()
        assert (
            output
            == dedent(
                """
            [INFO] Released solutions:
            [INFO] {} {} (already downloaded)
            [INFO] {} {} (download assignment!)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.assignment_id,
                self.course_id,
                self.assignment_id2,
            )
        )

    def test_list_remove_inbound(self):
        self.num_assignments = 2
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.inbound = True
        self.list.remove = True
        self.list.start()
        assert not self.test_failed
        assert not self.test_completed

    def test_list_remove_outbound(self):
        self.num_assignments = 2
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.remove = True
        self.list.start()
        assert not self.test_failed
        assert self.test_completed

    def test_list_remove_solution(self):
        self.num_assignments = 2
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.solution = True
        self.list.remove = True
        self.list.start()
        assert not self.test_failed
        assert not self.test_completed

    def test_list_inbound_0(self):
        self.num_assignments = 1
        self.num_submissions = 0
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.inbound = True
        data = self.list.start()
        assert data == []
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            """
            ).lstrip()
        )

    def test_list_inbound_1(self):
        self.num_assignments = 1
        self.num_submissions = 1
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.inbound = True
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": self.timestamp1,
                            "status": "submitted",
                            "notebooks": [
                                {
                                    "notebook_id": "p1",
                                    "has_local_feedback": False,
                                    "has_exchange_feedback": False,
                                    "local_feedback_path": None,
                                    "feedback_updated": False,
                                }
                            ],
                            "has_local_feedback": False,
                            "has_exchange_feedback": False,
                            "feedback_updated": False,
                            "local_feedback_path": None,
                        }
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (no feedback available)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
            )
        )

    def test_list_inbound_2(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.inbound = True
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": timestamp,
                            "status": "submitted",
                            "notebooks": [
                                {
                                    "notebook_id": "p1",
                                    "has_local_feedback": False,
                                    "has_exchange_feedback": False,
                                    "local_feedback_path": None,
                                    "feedback_updated": False,
                                }
                            ],
                            "has_local_feedback": False,
                            "has_exchange_feedback": False,
                            "feedback_updated": False,
                            "local_feedback_path": None,
                        }
                        for timestamp in (self.timestamp1, self.timestamp2)
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (no feedback available)
            [INFO] {} {} {} {} (no feedback available)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp2,
            )
        )

    def test_list_inbound_no_notebooks(self):
        self._mock_no_notebook()
        self.num_assignments = 1
        self.num_submissions = 1
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.inbound = True
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": self.timestamp1,
                            "status": "submitted",
                            "notebooks": [],
                            "has_local_feedback": False,
                            "has_exchange_feedback": False,
                            "feedback_updated": False,
                            "local_feedback_path": None,
                        },
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [WARNING] No notebooks found for assignment "{}" in course "{}"
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (no feedback available)
            """
            )
            .lstrip()
            .format(
                self.assignment_id,
                self.course_id,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
            )
        )

    def test_list_cached_0(self):
        self.num_assignments = 1
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        data = self.list.start()
        assert data == []
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            """
            ).lstrip()
        )

    def test_list_cached_1(self):
        self.num_assignments = 1
        self._submit()
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        data = self.list.start()
        submission_path = (
            self.cache_dir
            / self.course_id
            / '{}+{}+{}'.format(
                self.student_id,
                self.assignment_id,
                self.timestamp1,
            )
        )
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": self.timestamp1,
                            "status": "submitted",
                            "path": submission_path.as_posix(),
                            "notebooks": [
                                {
                                    "notebook_id": self.notebook_id,
                                    "path": (
                                        submission_path
                                        / (self.notebook_id + '.ipynb')
                                    ).as_posix(),
                                    "has_local_feedback": False,
                                    "has_exchange_feedback": False,
                                    "feedback_updated": False,
                                    "local_feedback_path": None,
                                }
                            ],
                            "has_local_feedback": False,
                            "has_exchange_feedback": False,
                            "feedback_updated": False,
                            "local_feedback_path": None,
                        }
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (no feedback available)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
            )
        )

    def test_list_cached_2(self):
        self.num_assignments = 1
        self._submit()
        self._submit(timestamp=self.timestamp2)
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        data = self.list.start()
        submission_path1, submission_path2 = (
            self.cache_dir
            / self.course_id
            / '{}+{}+{}'.format(
                self.student_id,
                self.assignment_id,
                timestamp,
            )
            for timestamp in (self.timestamp1, self.timestamp2)
        )
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": timestamp,
                            "status": "submitted",
                            "path": submission_path.as_posix(),
                            "notebooks": [
                                {
                                    "notebook_id": self.notebook_id,
                                    "path": (
                                        submission_path
                                        / (self.notebook_id + '.ipynb')
                                    ).as_posix(),
                                    "has_local_feedback": False,
                                    "has_exchange_feedback": False,
                                    "feedback_updated": False,
                                    "local_feedback_path": None,
                                }
                            ],
                            "has_local_feedback": False,
                            "has_exchange_feedback": False,
                            "feedback_updated": False,
                            "local_feedback_path": None,
                        }
                        for timestamp, submission_path in (
                            (self.timestamp1, submission_path1),
                            (self.timestamp2, submission_path2),
                        )
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (no feedback available)
            [INFO] {} {} {} {} (no feedback available)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp2,
            )
        )

    def test_list_not_in_course(self):
        tester = self

        class DummyAuthenticator(Authenticator):
            def get_student_courses(self, student_id):
                return [tester.course_id2]

        self.num_courses = 2
        self.num_assignments = 1
        self.list.coursedir.course_id = self.course_id
        self.list.authenticator = DummyAuthenticator()
        assert self.list.start() == []

    def test_list_remove_cached(self):
        self._submit()
        self._submit(
            assignment_id=self.assignment_id2, timestamp=self.timestamp2
        )
        self.is_instructor = False
        self.list.cached = True
        self.list.remove = True
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.start()
        self._read_log()
        self.list.remove = False
        self.list.coursedir.assignment_id = '*'
        data = self.list.start()
        submission_path2 = (
            self.cache_dir
            / self.course_id
            / '{}+{}+{}'.format(
                self.student_id,
                self.assignment_id2,
                self.timestamp2,
            )
        )
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id2,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id2,
                            "timestamp": self.timestamp2,
                            "status": "submitted",
                            "path": submission_path2.as_posix(),
                            "notebooks": [
                                {
                                    "notebook_id": self.notebook_id,
                                    "path": (
                                        submission_path2
                                        / (self.notebook_id + '.ipynb')
                                    ).as_posix(),
                                    "has_local_feedback": False,
                                    "has_exchange_feedback": False,
                                    "feedback_updated": False,
                                    "local_feedback_path": None,
                                }
                            ],
                            "has_local_feedback": False,
                            "has_exchange_feedback": False,
                            "feedback_updated": False,
                            "local_feedback_path": None,
                        }
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (no feedback available)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id2,
                self.timestamp2,
            )
        )

    def test_list_cached_and_inbound(self):
        self.is_instructor = False
        self.list.cached = True
        self.list.inbound = True
        with pytest.raises(ExchangeError):
            self.list.start()

    def test_list_feedback_inbound_ready1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self.list.inbound = True
        self.list.coursedir.assignment_id = self.assignment_id
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": timestamp,
                            "status": "submitted",
                            "notebooks": [
                                {
                                    "notebook_id": "p1",
                                    "has_local_feedback": False,
                                    "has_exchange_feedback": has_exchange_feedback,
                                    "local_feedback_path": None,
                                    "feedback_updated": False,
                                }
                            ],
                            "has_local_feedback": False,
                            "has_exchange_feedback": has_exchange_feedback,
                            "feedback_updated": False,
                            "local_feedback_path": None,
                        }
                        for (timestamp, has_exchange_feedback) in (
                            (self.timestamp1, True),
                            (self.timestamp2, False),
                        )
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback ready to be fetched)
            [INFO] {} {} {} {} (no feedback available)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp2,
            )
        )

    def test_list_feedback_inbound_fetched1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self.list.inbound = True
        self.list.coursedir.assignment_id = self.assignment_id
        self._fetch_feedback(
            self.course_dir, self.course_id, self.assignment_id, self.timestamp1
        )
        data = self.list.start()
        feedback_path = (
            self.course_dir / self.assignment_id / 'feedback' / self.timestamp1
        )
        notebook_feedback_path = feedback_path / (self.notebook_id + '.html')
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": timestamp,
                            "status": "submitted",
                            "notebooks": [
                                {
                                    "notebook_id": "p1",
                                    "has_local_feedback": has_local_feedback,
                                    "has_exchange_feedback": has_exchange_feedback,
                                    "local_feedback_path": notebook_local_feedback_path,
                                    "feedback_updated": False,
                                }
                            ],
                            "has_local_feedback": has_local_feedback,
                            "has_exchange_feedback": has_exchange_feedback,
                            "feedback_updated": False,
                            "local_feedback_path": local_feedback_path,
                        }
                        for (
                            timestamp,
                            has_local_feedback,
                            has_exchange_feedback,
                            local_feedback_path,
                            notebook_local_feedback_path,
                        ) in (
                            (
                                self.timestamp1,
                                True,
                                True,
                                feedback_path.as_posix(),
                                notebook_feedback_path.as_posix(),
                            ),
                            (self.timestamp2, False, False, None, None),
                        )
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback already fetched)
            [INFO] {} {} {} {} (no feedback available)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp2,
            )
        )

    def test_list_feedback_inbound_modified1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self.list.inbound = True
        self.list.coursedir.assignment_id = self.assignment_id
        self._fetch_feedback(
            self.course_dir, self.course_id, self.assignment_id, self.timestamp1
        )
        # This part is different from the original test because the fetched
        # feedback is modified instead of the outbound one, but the results
        # should be the same.
        feedback_path = (
            self.course_dir / self.assignment_id / 'feedback' / self.timestamp1
        )
        notebook_feedback_path = feedback_path / (self.notebook_id + '.html')
        with open(notebook_feedback_path, 'a') as fetched_file:
            fetched_file.write('blahblahblah')
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": timestamp,
                            "status": "submitted",
                            "notebooks": [
                                {
                                    "notebook_id": "p1",
                                    "has_local_feedback": has_local_feedback,
                                    "has_exchange_feedback": has_exchange_feedback,
                                    "local_feedback_path": notebook_local_feedback_path,
                                    "feedback_updated": feedback_updated,
                                }
                            ],
                            "has_local_feedback": has_local_feedback,
                            "has_exchange_feedback": has_exchange_feedback,
                            "feedback_updated": feedback_updated,
                            "local_feedback_path": local_feedback_path,
                        }
                        for (
                            timestamp,
                            has_local_feedback,
                            has_exchange_feedback,
                            feedback_updated,
                            local_feedback_path,
                            notebook_local_feedback_path,
                        ) in (
                            (
                                self.timestamp1,
                                True,
                                True,
                                True,
                                feedback_path.as_posix(),
                                notebook_feedback_path.as_posix(),
                            ),
                            (self.timestamp2, False, False, False, None, None),
                        )
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback ready to be fetched)
            [INFO] {} {} {} {} (no feedback available)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp2,
            )
        )

    def test_list_feedback_inbound_modified1_ready1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self.list.inbound = True
        self.list.coursedir.assignment_id = self.assignment_id
        self._fetch_feedback(
            self.course_dir, self.course_id, self.assignment_id, self.timestamp1
        )
        feedback_path = (
            self.course_dir / self.assignment_id / 'feedback' / self.timestamp1
        )
        notebook_feedback_path = feedback_path / (self.notebook_id + '.html')
        with open(notebook_feedback_path, 'a') as fetched_file:
            fetched_file.write('blahblahblah')
        self.num_feedback = 2
        data = self.list.start()
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": timestamp,
                            "status": "submitted",
                            "notebooks": [
                                {
                                    "notebook_id": "p1",
                                    "has_local_feedback": has_local_feedback,
                                    "has_exchange_feedback": has_exchange_feedback,
                                    "local_feedback_path": notebook_local_feedback_path,
                                    "feedback_updated": feedback_updated,
                                }
                            ],
                            "has_local_feedback": has_local_feedback,
                            "has_exchange_feedback": has_exchange_feedback,
                            "feedback_updated": feedback_updated,
                            "local_feedback_path": local_feedback_path,
                        }
                        for (
                            timestamp,
                            has_local_feedback,
                            has_exchange_feedback,
                            feedback_updated,
                            local_feedback_path,
                            notebook_local_feedback_path,
                        ) in (
                            (
                                self.timestamp1,
                                True,
                                True,
                                True,
                                feedback_path.as_posix(),
                                notebook_feedback_path.as_posix(),
                            ),
                            (self.timestamp2, False, True, False, None, None),
                        )
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback ready to be fetched)
            [INFO] {} {} {} {} (feedback ready to be fetched)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp2,
            )
        )

    def test_list_feedback_inbound_fetched2(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self.list.inbound = True
        self.list.coursedir.assignment_id = self.assignment_id
        self._fetch_feedback(
            self.course_dir, self.course_id, self.assignment_id, self.timestamp1
        )
        self._fetch_feedback(
            self.course_dir, self.course_id, self.assignment_id, self.timestamp2
        )
        self.num_feedback = 2
        data = self.list.start()
        feedback_path1, feedback_path2 = (
            self.course_dir / self.assignment_id / 'feedback' / timestamp
            for timestamp in (self.timestamp1, self.timestamp2)
        )
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": timestamp,
                            "status": "submitted",
                            "notebooks": [
                                {
                                    "notebook_id": "p1",
                                    "has_local_feedback": has_local_feedback,
                                    "has_exchange_feedback": has_exchange_feedback,
                                    "local_feedback_path": (
                                        local_feedback_path
                                        / (self.notebook_id + '.html')
                                    ).as_posix(),
                                    "feedback_updated": False,
                                }
                            ],
                            "has_local_feedback": has_local_feedback,
                            "has_exchange_feedback": has_exchange_feedback,
                            "feedback_updated": False,
                            "local_feedback_path": local_feedback_path.as_posix(),
                        }
                        for (
                            timestamp,
                            has_local_feedback,
                            has_exchange_feedback,
                            local_feedback_path,
                        ) in (
                            (
                                self.timestamp1,
                                True,
                                True,
                                feedback_path1,
                            ),
                            (
                                self.timestamp2,
                                True,
                                True,
                                feedback_path2,
                            ),
                        )
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback already fetched)
            [INFO] {} {} {} {} (feedback already fetched)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp2,
            )
        )

    def test_list_feedback_cached_ready1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self._submit()
        self._submit(timestamp=self.timestamp2)
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        data = self.list.start()
        submission_path1, submission_path2 = (
            self.cache_dir
            / self.course_id
            / '{}+{}+{}'.format(
                self.student_id,
                self.assignment_id,
                timestamp,
            )
            for timestamp in (self.timestamp1, self.timestamp2)
        )
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": timestamp,
                            "status": "submitted",
                            "path": submission_path.as_posix(),
                            "notebooks": [
                                {
                                    "notebook_id": "p1",
                                    "path": (
                                        submission_path
                                        / (self.notebook_id + '.ipynb')
                                    ).as_posix(),
                                    "has_local_feedback": has_local_feedback,
                                    "has_exchange_feedback": has_exchange_feedback,
                                    "local_feedback_path": None,
                                    "feedback_updated": False,
                                }
                            ],
                            "has_local_feedback": has_local_feedback,
                            "has_exchange_feedback": has_exchange_feedback,
                            "feedback_updated": False,
                            "local_feedback_path": None,
                        }
                        for (
                            timestamp,
                            submission_path,
                            has_local_feedback,
                            has_exchange_feedback,
                        ) in (
                            (
                                self.timestamp1,
                                submission_path1,
                                False,
                                True,
                            ),
                            (
                                self.timestamp2,
                                submission_path2,
                                False,
                                False,
                            ),
                        )
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback ready to be fetched)
            [INFO] {} {} {} {} (no feedback available)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp2,
            )
        )

    def test_list_feedback_cached_fetched1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self._submit()
        self._submit(timestamp=self.timestamp2)
        self._fetch_feedback(
            self.course_dir, self.course_id, self.assignment_id, self.timestamp1
        )
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        data = self.list.start()
        submission_path1, submission_path2 = (
            self.cache_dir
            / self.course_id
            / '{}+{}+{}'.format(
                self.student_id,
                self.assignment_id,
                timestamp,
            )
            for timestamp in (self.timestamp1, self.timestamp2)
        )
        feedback_path = (
            self.course_dir / self.assignment_id / 'feedback' / self.timestamp1
        )
        notebook_feedback_path = feedback_path / (self.notebook_id + '.html')
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": timestamp,
                            "status": "submitted",
                            "path": submission_path.as_posix(),
                            "notebooks": [
                                {
                                    "notebook_id": "p1",
                                    "path": (
                                        submission_path
                                        / (self.notebook_id + '.ipynb')
                                    ).as_posix(),
                                    "has_local_feedback": has_local_feedback,
                                    "has_exchange_feedback": has_exchange_feedback,
                                    "local_feedback_path": notebook_local_feedback_path,
                                    "feedback_updated": False,
                                }
                            ],
                            "has_local_feedback": has_local_feedback,
                            "has_exchange_feedback": has_exchange_feedback,
                            "feedback_updated": False,
                            "local_feedback_path": local_feedback_path,
                        }
                        for (
                            timestamp,
                            submission_path,
                            has_local_feedback,
                            has_exchange_feedback,
                            local_feedback_path,
                            notebook_local_feedback_path,
                        ) in (
                            (
                                self.timestamp1,
                                submission_path1,
                                True,
                                True,
                                feedback_path.as_posix(),
                                notebook_feedback_path.as_posix(),
                            ),
                            (
                                self.timestamp2,
                                submission_path2,
                                False,
                                False,
                                None,
                                None,
                            ),
                        )
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback already fetched)
            [INFO] {} {} {} {} (no feedback available)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp2,
            )
        )

    def test_list_feedback_cached_modified1(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self._submit()
        self._submit(timestamp=self.timestamp2)
        self._fetch_feedback(
            self.course_dir, self.course_id, self.assignment_id, self.timestamp1
        )
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        # This part is different from the original test because the fetched
        # feedback is modified instead of the outbound one, but the results
        # should be the same.
        feedback_path = (
            self.course_dir / self.assignment_id / 'feedback' / self.timestamp1
        )
        notebook_feedback_path = feedback_path / (self.notebook_id + '.html')
        with open(notebook_feedback_path, 'a') as fetched_file:
            fetched_file.write('blahblahblah')
        data = self.list.start()
        submission_path1, submission_path2 = (
            self.cache_dir
            / self.course_id
            / '{}+{}+{}'.format(
                self.student_id,
                self.assignment_id,
                timestamp,
            )
            for timestamp in (self.timestamp1, self.timestamp2)
        )
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": timestamp,
                            "status": "submitted",
                            "path": submission_path.as_posix(),
                            "notebooks": [
                                {
                                    "notebook_id": "p1",
                                    "path": (
                                        submission_path
                                        / (self.notebook_id + '.ipynb')
                                    ).as_posix(),
                                    "has_local_feedback": has_local_feedback,
                                    "has_exchange_feedback": has_exchange_feedback,
                                    "local_feedback_path": notebook_local_feedback_path,
                                    "feedback_updated": feedback_updated,
                                }
                            ],
                            "has_local_feedback": has_local_feedback,
                            "has_exchange_feedback": has_exchange_feedback,
                            "feedback_updated": feedback_updated,
                            "local_feedback_path": local_feedback_path,
                        }
                        for (
                            timestamp,
                            submission_path,
                            has_local_feedback,
                            has_exchange_feedback,
                            feedback_updated,
                            local_feedback_path,
                            notebook_local_feedback_path,
                        ) in (
                            (
                                self.timestamp1,
                                submission_path1,
                                True,
                                True,
                                True,
                                feedback_path.as_posix(),
                                notebook_feedback_path.as_posix(),
                            ),
                            (
                                self.timestamp2,
                                submission_path2,
                                False,
                                False,
                                False,
                                None,
                                None,
                            ),
                        )
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback ready to be fetched)
            [INFO] {} {} {} {} (no feedback available)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp2,
            )
        )

    def test_list_feedback_cached_ready2(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self._submit()
        self._submit(timestamp=self.timestamp2)
        self._fetch_feedback(
            self.course_dir, self.course_id, self.assignment_id, self.timestamp1
        )
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        feedback_path = (
            self.course_dir / self.assignment_id / 'feedback' / self.timestamp1
        )
        notebook_feedback_path = feedback_path / (self.notebook_id + '.html')
        with open(notebook_feedback_path, 'a') as fetched_file:
            fetched_file.write('blahblahblah')
        self.num_feedback = 2
        data = self.list.start()
        submission_path1, submission_path2 = (
            self.cache_dir
            / self.course_id
            / '{}+{}+{}'.format(
                self.student_id,
                self.assignment_id,
                timestamp,
            )
            for timestamp in (self.timestamp1, self.timestamp2)
        )
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": timestamp,
                            "status": "submitted",
                            "path": submission_path.as_posix(),
                            "notebooks": [
                                {
                                    "notebook_id": "p1",
                                    "path": (
                                        submission_path
                                        / (self.notebook_id + '.ipynb')
                                    ).as_posix(),
                                    "has_local_feedback": has_local_feedback,
                                    "has_exchange_feedback": has_exchange_feedback,
                                    "local_feedback_path": notebook_local_feedback_path,
                                    "feedback_updated": feedback_updated,
                                }
                            ],
                            "has_local_feedback": has_local_feedback,
                            "has_exchange_feedback": has_exchange_feedback,
                            "feedback_updated": feedback_updated,
                            "local_feedback_path": local_feedback_path,
                        }
                        for (
                            timestamp,
                            submission_path,
                            has_local_feedback,
                            has_exchange_feedback,
                            feedback_updated,
                            local_feedback_path,
                            notebook_local_feedback_path,
                        ) in (
                            (
                                self.timestamp1,
                                submission_path1,
                                True,
                                True,
                                True,
                                feedback_path.as_posix(),
                                notebook_feedback_path.as_posix(),
                            ),
                            (
                                self.timestamp2,
                                submission_path2,
                                False,
                                True,
                                False,
                                None,
                                None,
                            ),
                        )
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback ready to be fetched)
            [INFO] {} {} {} {} (feedback ready to be fetched)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp2,
            )
        )

    def test_list_feedback_cached_fetched2(self):
        self.num_assignments = 1
        self.num_submissions = 2
        self.num_feedback = 1
        self._submit()
        self._submit(timestamp=self.timestamp2)
        self._fetch_feedback(
            self.course_dir, self.course_id, self.assignment_id, self.timestamp1
        )
        self._fetch_feedback(
            self.course_dir, self.course_id, self.assignment_id, self.timestamp2
        )
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        self.num_feedback = 2
        data = self.list.start()
        submission_path1, submission_path2 = (
            self.cache_dir
            / self.course_id
            / '{}+{}+{}'.format(
                self.student_id,
                self.assignment_id,
                timestamp,
            )
            for timestamp in (self.timestamp1, self.timestamp2)
        )
        feedback_path1, feedback_path2 = (
            self.course_dir / self.assignment_id / 'feedback' / timestamp
            for timestamp in (self.timestamp1, self.timestamp2)
        )
        self.assertEqual(
            data,
            [
                {
                    "course_id": self.course_id,
                    "student_id": self.student_id,
                    "assignment_id": self.assignment_id,
                    "status": "submitted",
                    "submissions": [
                        {
                            "course_id": self.course_id,
                            "student_id": self.student_id,
                            "assignment_id": self.assignment_id,
                            "timestamp": timestamp,
                            "status": "submitted",
                            "path": submission_path.as_posix(),
                            "notebooks": [
                                {
                                    "notebook_id": "p1",
                                    "path": (
                                        submission_path
                                        / (self.notebook_id + '.ipynb')
                                    ).as_posix(),
                                    "has_local_feedback": has_local_feedback,
                                    "has_exchange_feedback": has_exchange_feedback,
                                    "local_feedback_path": (
                                        local_feedback_path
                                        / (self.notebook_id + '.html')
                                    ).as_posix(),
                                    "feedback_updated": False,
                                }
                            ],
                            "has_local_feedback": has_local_feedback,
                            "has_exchange_feedback": has_exchange_feedback,
                            "feedback_updated": False,
                            "local_feedback_path": local_feedback_path.as_posix(),
                        }
                        for (
                            timestamp,
                            submission_path,
                            has_local_feedback,
                            has_exchange_feedback,
                            local_feedback_path,
                        ) in (
                            (
                                self.timestamp1,
                                submission_path1,
                                True,
                                True,
                                feedback_path1,
                            ),
                            (
                                self.timestamp2,
                                submission_path2,
                                True,
                                True,
                                feedback_path2,
                            ),
                        )
                    ],
                },
            ],
        )
        assert (
            self._read_log()
            == dedent(
                """
            [INFO] Submitted assignments:
            [INFO] {} {} {} {} (feedback already fetched)
            [INFO] {} {} {} {} (feedback already fetched)
            """
            )
            .lstrip()
            .format(
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp1,
                self.course_id,
                self.student_id,
                self.assignment_id,
                self.timestamp2,
            )
        )

    def test_list_path_includes_course(self):
        self.num_courses = 2
        self.num_assignments = 1
        self.list.coursedir.course_id = self.course_id
        self.list.path_includes_course = True
        self.list.start()

    def test_list_ngshare_error_assignment(self):
        self._mock_error_assignment()
        self.num_courses = 1
        self.num_assignments = 1
        self.list.coursedir.course_id = self.course_id
        self.list.start()

    def test_list_ngshare_error_assignments(self):
        self._mock_error_assignments()
        self.num_courses = 1
        self.num_assignments = 1
        self.list.coursedir.course_id = self.course_id
        self.list.start()

    def test_list_ngshare_error_feedback_1(self):
        self._mock_error_feedback()
        self.num_assignments = 1
        self.num_submissions = 1
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.inbound = True
        self.list.start()

    def test_list_ngshare_error_feedback_2(self):
        self._mock_error_feedback()
        self.num_assignments = 1
        self._submit()
        self.is_instructor = False
        self.list.cached = True
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.start()

    def test_list_ngshare_error_submission(self):
        self._mock_error_submission()
        self.num_assignments = 1
        self.num_submissions = 1
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.inbound = True
        self.list.start()

    def test_list_ngshare_error_submissions(self):
        self._mock_error_submissions()
        self.num_courses = 2
        self.num_assignments = 1
        self.list.coursedir.course_id = self.course_id
        self.list.coursedir.student_id = self.student_id
        self.list.inbound = True
        self.list.start()

    def test_list_ngshare_error_unrelease(self):
        self._mock_error_unrelease()
        self.num_assignments = 2
        self.list.coursedir.assignment_id = self.assignment_id
        self.list.remove = True
        self.list.start()
