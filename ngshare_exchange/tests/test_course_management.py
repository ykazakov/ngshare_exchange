import os
from pathlib import Path
from shutil import copyfile

from nbgrader.api import Gradebook
import pytest
import re
from logging import getLogger
import requests
from requests import PreparedRequest
import requests_mock as rq_mock
from requests_mock import Mocker
import urllib
import tempfile
from .. import course_management as cm


def remove_color(s):
    # https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    result = ansi_escape.sub('', s)
    return result


def get_out_array(out):
    out = remove_color(out)
    out = out.split('\n')
    out.remove('')
    return out


def parse_body(body: str):
    # https://stackoverflow.com/questions/48018622/how-can-see-the-request-data#51052385
    return dict(urllib.parse.parse_qsl(body))


NGSHARE_URL = 'http://127.0.0.1:12121/api'
global _ngshare_url
cm._ngshare_url = NGSHARE_URL


class TestCourseManagement:
    course_id = 'math101'
    instructor = (
        os.environ['JUPYTERHUB_USER']
        if 'JUPYTERHUB_USER' in os.environ
        else os.environ['USER']
    )
    instructors = ['mi1', 'mi2']
    student_id = 'ms'
    instructor_id = 'mi1'

    course_created = False
    bad_user_warning_message = 'The following usernames have upper-case letters. Normally JupyterHub forces usernames to be lowercase. If the user has trouble accessing the course, you should add their lowercase username to ngshare instead.'

    @pytest.fixture(autouse=True)
    def init(self, requests_mock: Mocker):
        self.requests_mocker = requests_mock
        requests_mock.register_uri(
            rq_mock.ANY, rq_mock.ANY, text=self._mock_all
        )
        cm._ngshare_url = NGSHARE_URL

    def _add_gradebook(self, path):
        gb_path = Path(__file__).parent / 'files' / 'gradebook.db'
        copyfile(gb_path, Path(path) / 'gradebook.db')

    def _add_empty_gradebook(self, path):
        gb_path = Path(__file__).parent / 'files' / 'empty_gradebook.db'
        copyfile(gb_path, Path(path) / 'gradebook.db')

    def _mock_all(self, request: PreparedRequest, content):
        getLogger().fatal(
            'The request \'%s\' has not been mocked yet.', request.url
        )
        content.status_code = 404
        return ''

    def _get_user_info(self, request: PreparedRequest, context):
        request = parse_body(request.body)
        print(request)
        if 'first_name' not in request:
            return {'success': False, 'message': 'Please supply first name'}
        elif 'last_name' not in request:
            return {'success': False, 'message': 'Please supply last name'}
        elif 'email' not in request:
            return {'success': False, 'message': 'Please supply email'}
        elif request['user'] != self.instructor:
            return {'success': False, 'message': 'Permission denied'}
        else:
            return {'success': True}

    def _get_user_info_unsuccessful(self, request: PreparedRequest, context):
        request = parse_body(request.body)
        if 'first_name' not in request:
            return {'success': False, 'message': 'Please supply first name'}
        elif 'last_name' not in request:
            return {'success': False, 'message': 'Please supply last name'}
        elif 'email' not in request:
            return {'success': False, 'message': 'Please supply email'}
        elif request['user'] != self.instructor:
            return {'success': False, 'message': 'Permission denied'}
        else:
            return {'success': False, 'message': '¯\\_O_/¯'}

    def _get_students_info(self, request: PreparedRequest, context):
        request = parse_body(request.body)
        students = eval(request['students'])

        if (
            'sid1' == students[0]['username']
            and 'sid2' == students[1]['username']
        ):
            return {
                'success': True,
                'status': [
                    {'username': 'sid1', 'success': True},
                    {'username': 'sid2', 'success': True},
                ],
            }
        else:
            return {'success': False, 'message': 'wrong students passed in'}

    def _get_bad_students_info(self, request: PreparedRequest, context):
        request = parse_body(request.body)
        students = eval(request['students'])

        if (
            'Not_good' == students[0]['username']
            and 'Bad' == students[1]['username']
            and '123' == students[2]['username']
        ):
            return {
                'success': True,
                'status': [
                    {'username': 'Not_good', 'success': True},
                    {'username': 'Bad', 'success': True},
                    {'username': '123', 'success': True},
                ],
            }
        else:
            return {'success': False, 'message': 'wrong students passed in'}

    def _get_students_info_unsuccessful(
        self, request: PreparedRequest, context
    ):
        request = parse_body(request.body)
        students = eval(request['students'])

        if (
            'sid1' == students[0]['username']
            and 'sid2' == students[1]['username']
        ):
            return {
                'success': True,
                'status': [
                    {
                        'username': 'sid1',
                        'success': False,
                        'message': '¯\\_O_/¯',
                    },
                    {'username': 'sid2', 'success': True},
                ],
            }
        else:
            return {'success': False, 'message': 'wrong students passed in'}

    def _get_user(self, request: PreparedRequest, context):
        request = parse_body(request.body)
        response = {'success': False, 'message': 'Permission denied'}
        if self.instructor in request['user']:
            response = {'success': True}
        return response

    def _get_instructors_info(self, request: PreparedRequest, context):
        request = parse_body(request.body)
        response = {'success': False, 'message': 'Some error occurred'}
        if not self.course_created:
            if 'instructors' in request:
                instructors = eval(request['instructors'])
                if (
                    self.instructors[0] == instructors[0]
                    and self.instructors[1] == instructors[1]
                ):
                    response = {'success': True}
                    self.course_created = True
        else:
            response = {'success': False, 'message': 'Course already exists'}

        return response

    def _mock_create_course(self):
        url = '{}/course/{}'.format(NGSHARE_URL, self.course_id)
        self.requests_mocker.post(url, json=self._get_instructors_info)

    def _mock_add_student(self):
        url = '{}/student/{}/{}'.format(
            NGSHARE_URL, self.course_id, self.student_id
        )
        self.requests_mocker.post(url, json=self._get_user_info)

    def _mock_add_student_unsuccessful(self):
        url = '{}/student/{}/{}'.format(
            NGSHARE_URL, self.course_id, self.student_id
        )
        self.requests_mocker.post(url, json=self._get_user_info_unsuccessful)

    def _mock_add_students(self):
        url = '{}/students/{}'.format(NGSHARE_URL, self.course_id)
        self.requests_mocker.post(url, json=self._get_students_info)

    def _mock_add_students_unsuccessful(self):
        url = '{}/students/{}'.format(NGSHARE_URL, self.course_id)
        self.requests_mocker.post(
            url, json=self._get_students_info_unsuccessful
        )

    def _mock_add_bad_students(self):
        url = '{}/students/{}'.format(NGSHARE_URL, self.course_id)
        self.requests_mocker.post(url, json=self._get_bad_students_info)

    def _mock_add_instructor(self):
        url = '{}/instructor/{}/{}'.format(
            NGSHARE_URL, self.course_id, self.instructor_id
        )
        self.requests_mocker.post(url, json=self._get_user_info)

    def _mock_remove_student(self):
        url = '{}/student/{}/{}'.format(
            NGSHARE_URL, self.course_id, self.student_id
        )
        self.requests_mocker.delete(url, json=self._get_user)

    def _mock_remove_instructor(self):
        url = '{}/instructor/{}/{}'.format(
            NGSHARE_URL, self.course_id, self.instructor_id
        )
        self.requests_mocker.delete(url, json=self._get_user)

    def test_create_course(self, capsys):
        self._mock_create_course()
        cm.main(['create_course', self.course_id] + self.instructors)
        out, err = capsys.readouterr()
        out = remove_color(out)
        assert ' Successfully created {}\n'.format(self.course_id) in out

        # test missing course id
        with pytest.raises(SystemExit) as se:
            cm.main(['create_course'])
        assert se.type == SystemExit
        assert se.value.code == 2

        # try to create course again
        self._mock_create_course()
        with pytest.raises(SystemExit) as se:
            cm.main(['create_course', self.course_id])
        out, err = capsys.readouterr()
        assert ' Course already exists' in out
        assert se.type == SystemExit
        assert se.value.code == -1

    def test_create_course_instructor_warning(self, capsys, tmpdir_factory):
        # test passing in a list with one bad username
        self._mock_create_course()
        self.instructors = ['BadUsername', 'goodusername']
        cm.main(['create_course', self.course_id] + self.instructors)

        out, err = capsys.readouterr()
        out = get_out_array(out)

        assert self.bad_user_warning_message in out[0]
        assert 'BadUsername' in out[1]
        assert 'Successfully created math101' in out[-1]

    def test_add_student_warning(self, capsys, tmpdir_factory):
        # test trying to add a student with bad username
        self.student_id = 'BAD_username'
        self._mock_add_student()
        cm.main(
            [
                'add_student',
                self.course_id,
                self.student_id,
                '-f',
                'jane',
                '-l',
                'doe',
                '-e' 'jd@mail.com',
                '--no-gb',
            ]
        )

        out, err = capsys.readouterr()
        out = get_out_array(out)

        assert self.bad_user_warning_message in out[0]
        assert 'BAD_username' in out[1]
        assert 'Successfully added/updated BAD_username on math101' in out[-1]

    def test_add_instructor_warning(self, capsys, tmpdir_factory):
        # test adding an instructor with a bad username
        self.instructor_id = 'Bad_Inst'
        self._mock_add_instructor()
        cm.main(
            [
                'add_instructor',
                self.course_id,
                self.instructor_id,
                '-f',
                'john',
                '-l',
                'doe',
                '-e',
                'jd@mail.com',
            ]
        )

        out, err = capsys.readouterr()
        out = get_out_array(out)

        assert self.bad_user_warning_message in out[0]
        assert 'Bad_Inst' in out[1]
        assert 'Successfully added Bad_Inst as an instructor to math' in out[-1]

    def test_add_students_warning(self, capsys, tmpdir_factory):
        # check add students with bad usernames
        tmp_dir = tmpdir_factory.mktemp(self.course_id)
        os.chdir(tmp_dir)
        self._add_empty_gradebook(tmp_dir)
        self._mock_add_bad_students()
        with tempfile.NamedTemporaryFile() as f:
            f.writelines(
                [
                    b'student_id,first_name,last_name,email\n',
                    b'Not_good,jane,doe,jd@mail.com\n',
                    b'Bad,john,perez,jp@mail.com\n',
                    b'123,john,perez,jp@mail.com\n',
                ]
            )
            f.flush()
            cm.main(['add_students', self.course_id, f.name])

        out, err = capsys.readouterr()
        out = get_out_array(out)
        assert self.bad_user_warning_message in out[0]
        assert 'Not_good' in out[1]
        assert 'Bad' in out[2]
        assert 'Not_good was successfully added to math101' in out[-3]
        assert 'Bad was successfully added to math101' in out[-2]
        assert '123 was successfully added to math101' in out[-1]

    def test_add_student(self, capsys):
        # test missing course id
        with pytest.raises(SystemExit) as se:
            cm.main(['add_student'])
        assert se.type == SystemExit
        assert se.value.code == 2

        # test missing student id
        with pytest.raises(SystemExit) as se:
            cm.main(['add_student', self.course_id])
        assert se.type == SystemExit
        assert se.value.code == 2

        self._mock_add_student()
        cm.main(
            [
                'add_student',
                self.course_id,
                self.student_id,
                '-f',
                'jane',
                '-l',
                'doe',
                '-e' 'jd@mail.com',
                '--no-gb',
            ]
        )
        out, err = capsys.readouterr()
        assert 'Successfully added/updated {}'.format(self.student_id) in out

    def test_add_student_db(self, capsys, tmpdir_factory):
        tmp_dir = tmpdir_factory.mktemp(self.course_id)
        os.chdir(tmp_dir)
        self._add_empty_gradebook(tmp_dir)
        self._mock_add_student()
        cm.main(
            [
                'add_student',
                self.course_id,
                self.student_id,
                '-f',
                'jane',
                '-l',
                'doe',
                '-e' 'jd@mail.com',
            ]
        )
        gb = Gradebook('sqlite:///gradebook.db', course_id=self.course_id)
        students = gb.students
        assert len(students) == 1
        student = students[0]
        assert student.first_name == 'jane'
        assert student.last_name == 'doe'
        assert student.email == 'jd@mail.com'

    def test_add_student_unsuccessful(self, capsys):
        self._mock_add_student_unsuccessful()
        with pytest.raises(SystemExit) as se:
            cm.main(
                [
                    'add_student',
                    self.course_id,
                    self.student_id,
                    '-f',
                    'jane',
                    '-l',
                    'doe',
                    '-e' 'jd@mail.com',
                    '--no-gb',
                ]
            )
        assert se.type == SystemExit
        assert se.value.code == -1

    def test_add_students_db(self, capsys, tmpdir_factory):
        tmp_dir = tmpdir_factory.mktemp(self.course_id)
        os.chdir(tmp_dir)
        self._add_empty_gradebook(tmp_dir)
        self._mock_add_students()
        with tempfile.NamedTemporaryFile() as f:
            f.writelines(
                [
                    b'student_id,first_name,last_name,email\n',
                    b'sid1,jane,doe,jd@mail.com\n',
                    b'sid2,john,perez,jp@mail.com\n',
                ]
            )
            f.flush()
            cm.main(['add_students', self.course_id, f.name])
        out, err = capsys.readouterr()
        assert 'sid1 was successfully added to math101' in out
        assert 'sid2 was successfully added to math101' in out

        gb = Gradebook('sqlite:///gradebook.db', course_id=self.course_id)
        students = gb.students
        assert len(students) == 2
        student_dict = {
            'sid1': {'f_name': 'jane', 'l_name': 'doe', 'email': 'jd@mail.com'},
            'sid2': {
                'f_name': 'john',
                'l_name': 'perez',
                'email': 'jp@mail.com',
            },
        }
        for student in students:
            assert student.first_name == student_dict[student.id]['f_name']
            assert student.last_name == student_dict[student.id]['l_name']
            assert student.email == student_dict[student.id]['email']

    def test_add_students(self, capsys, tmp_path):
        self._mock_add_students()
        # test no course id
        with pytest.raises(SystemExit) as se:
            cm.main(['add_students'])
        assert se.type == SystemExit
        assert se.value.code == 2

        # test no file
        with pytest.raises(SystemExit) as se:
            cm.main(['add_students', self.course_id])
        assert se.type == SystemExit
        assert se.value.code == 2

        # test no non existing file
        with pytest.raises(SystemExit) as se:
            cm.main(['add_students', self.course_id, 'dne'])

        assert se.type == SystemExit
        assert se.value.code == -1
        out, err = capsys.readouterr()
        assert 'The csv file you entered does not exist' in out

        with tempfile.NamedTemporaryFile() as f:
            f.writelines(
                [
                    b"student_id,first_name,last_name,email\n",
                    b"sid1,jane,doe,jd@mail.com\n",
                    b"sid2,john,perez,jp@mail.com\n",
                ]
            )
            f.flush()
            cm.main(['add_students', self.course_id, f.name, '--no-gb'])
        out, err = capsys.readouterr()
        assert 'sid1 was successfully added to math101' in out
        assert 'sid2 was successfully added to math101' in out

    def test_add_students_unsuccessful(self, capsys, tmp_path):
        self._mock_add_students_unsuccessful()
        with tempfile.NamedTemporaryFile() as f:
            f.writelines(
                [
                    b'student_id,first_name,last_name,email\n',
                    b'sid1,jane,doe,jd@mail.com\n',
                    b'sid2,john,perez,jp@mail.com\n',
                ]
            )
            f.flush()
            cm.main(['add_students', self.course_id, f.name, '--no-gb'])
        out, err = capsys.readouterr()
        assert 'There was an error adding sid1 to math101: ' in out
        assert 'sid2 was successfully added to math101' in out

    def test_add_instructor(self, capsys):
        self._mock_add_instructor()

        # test no course id
        with pytest.raises(SystemExit) as se:
            cm.main(['add_instructor'])
        assert se.type == SystemExit
        assert se.value.code == 2

        # test no instructor id
        with pytest.raises(SystemExit) as se:
            cm.main(['add_instructor', self.course_id])
        assert se.type == SystemExit
        assert se.value.code == 2

        # test valid
        cm.main(
            [
                'add_instructor',
                self.course_id,
                self.instructor_id,
                '-f',
                'john',
                '-l',
                'doe',
                '-e',
                'jd@mail.com',
            ]
        )
        out, err = capsys.readouterr()
        assert (
            'Successfully added {} as an instructor to {}'.format(
                self.instructor_id, self.course_id
            )
            in out
        )

    def test_remove_student(self, capsys):
        self._mock_remove_student()

        # test missing course id
        with pytest.raises(SystemExit) as se:
            cm.main(['remove_students'])
        assert se.type == SystemExit
        assert se.value.code == 2

        # test missing student id
        with pytest.raises(SystemExit) as se:
            cm.main(['remove_students', self.course_id])
        assert se.type == SystemExit
        assert se.value.code == 2

        # test valid
        cm.main(['remove_students', self.course_id, self.student_id, '--no-gb'])
        out, err = capsys.readouterr()
        assert (
            'Successfully deleted {} from {}'.format(
                self.student_id, self.course_id
            )
            in out
        )

    def test_remove_student_db(self, tmpdir_factory):
        self._mock_remove_student()
        tmp_dir = tmpdir_factory.mktemp(self.course_id)
        os.chdir(tmp_dir)
        self._add_empty_gradebook(tmp_dir)
        gb = Gradebook('sqlite:///gradebook.db', course_id=self.course_id)
        gb.add_student(self.student_id)

        # test valid
        cm.main(['remove_students', self.course_id, self.student_id])
        assert len(gb.students) == 0

    def test_remove_student_db_force(self, tmpdir_factory):
        self._mock_remove_student()
        tmp_dir = tmpdir_factory.mktemp(self.course_id)
        os.chdir(tmp_dir)
        self._add_gradebook(tmp_dir)
        gb = Gradebook('sqlite:///gradebook.db', course_id=self.course_id)

        # test valid
        cm.main(['remove_students', self.course_id, self.student_id])
        assert len(gb.students) == 1
        cm.main(['remove_students', self.course_id, self.student_id, '--force'])
        assert len(gb.students) == 0

    def test_remove_instructor(self, capsys):
        self._mock_remove_instructor()

        # test missing course id
        with pytest.raises(SystemExit) as se:
            cm.main(['remove_instructor'])
        assert se.type == SystemExit
        assert se.value.code == 2

        # test missing student id
        with pytest.raises(SystemExit) as se:
            cm.main(['remove_instructor', self.course_id])
        assert se.type == SystemExit
        assert se.value.code == 2

        # test valid
        cm.main(['remove_instructor', self.course_id, self.instructor_id])
        out, err = capsys.readouterr()
        assert (
            'Successfully deleted instructor {} from {}'.format(
                self.instructor_id, self.course_id
            )
            in out
        )

    def test_add_students_parsing(self, capsys):
        # test empty file
        with tempfile.NamedTemporaryFile() as f:
            with pytest.raises(SystemExit) as se:
                cm.main(['add_students', self.course_id, f.name, '--no-gb'])
            assert se.type == SystemExit
            assert se.value.code == -1
            out, err = capsys.readouterr()
            assert 'The csv file you entered is empty' in out

        # test missing a column
        with tempfile.NamedTemporaryFile() as f:
            f.write(b'first_name,last_name,email')
            f.flush()

            with pytest.raises(SystemExit) as se:
                cm.main(['add_students', self.course_id, f.name, '--no-gb'])
            assert se.type == SystemExit
            assert se.value.code == -1
            out, err = capsys.readouterr()
            assert (
                'Missing column {} in {}.'.format('student_id', f.name) in out
            )

        self._mock_add_students()
        with tempfile.NamedTemporaryFile() as f:
            f.write(b'student_id,first_name,last_name,email\n')
            f.write(b'sid1,jane,doe,jd@mail.com\n')
            f.write(b',jane,doe,jd@mail.com\n')
            f.write(b'sid2,john,perez,jp@mail.com\n')
            f.flush()

            cm.main(['add_students', self.course_id, f.name, '--no-gb'])
            out, err = capsys.readouterr()
            assert 'sid1 was successfully added to math101' in out
            assert 'Student ID cannot be empty (row 2)' in out
            assert 'sid2 was successfully added to math101' in out

    def test_get_username(self):
        jhu = 'JUPYTERHUB_USER'
        if jhu in os.environ:
            del os.environ[jhu]
        assert os.environ['USER'] == cm.get_username()
        os.environ[jhu] = 'jh_username'
        username1 = cm.get_username()
        username2 = os.environ[jhu]
        del os.environ[jhu]
        assert username1 == username2

    def test_no_ngshare_url(self, tmpdir_factory):
        url = 'http://ngshare.url'
        tmp_dir = tmpdir_factory.mktemp(self.course_id)
        os.chdir(tmp_dir)
        config_file = Path(tmp_dir) / 'nbgrader_config.py'
        config = '\n'.join(
            [
                'from ngshare_exchange import configureExchange',
                'c=get_config()',
                'configureExchange(c)',
                'c.ExchangeFactory.exchange._ngshare_url = "{}"',
            ]
        ).format(url)
        config_file.write_text(config)
        del cm._ngshare_url
        assert url == cm.ngshare_url()

    def test_no_ngshare_url_no_config(self, tmpdir_factory):
        tmp_dir = tmpdir_factory.mktemp(self.course_id)
        os.chdir(tmp_dir)
        del cm._ngshare_url
        with pytest.raises(SystemExit):
            cm.ngshare_url()

    def test_headers_delete(self):
        token = 'unique_token'
        os.environ['JUPYTERHUB_API_TOKEN'] = token
        self.called = False

        def json(request: PreparedRequest, context):
            self.called = True
            assert 'Authorization' in request.headers
            assert request.headers['Authorization'] == 'token ' + token
            return self._get_user(request, context)

        url = '{}/student/{}/{}'.format(
            NGSHARE_URL, self.course_id, self.student_id
        )
        self.requests_mocker.delete(url, json=json)
        cm.main(['remove_students', self.course_id, self.student_id, '--no-gb'])
        assert self.called
        del self.called

    def test_headers_post(self):
        token = 'unique_token'
        os.environ['JUPYTERHUB_API_TOKEN'] = token
        self.called = False

        def json(request: PreparedRequest, context):
            self.called = True
            assert 'Authorization' in request.headers
            assert request.headers['Authorization'] == 'token ' + token
            return self._get_instructors_info(request, context)

        url = '{}/course/{}'.format(NGSHARE_URL, self.course_id)
        self.requests_mocker.post(url, json=json)
        cm.main(['create_course', self.course_id] + self.instructors)
        assert self.called
        del self.called

    def test_connection_error_delete(self):
        url = '{}/student/{}/{}'.format(
            NGSHARE_URL, self.course_id, self.student_id
        )
        self.requests_mocker.delete(
            url, exc=requests.exceptions.ConnectionError
        )
        with pytest.raises(SystemExit):
            cm.main(
                ['remove_students', self.course_id, self.student_id, '--no-gb']
            )

    def test_connection_error_post(self):
        url = '{}/course/{}'.format(NGSHARE_URL, self.course_id)
        self.requests_mocker.post(url, exc=requests.exceptions.ConnectionError)
        with pytest.raises(SystemExit):
            cm.main(['create_course', self.course_id] + self.instructors)

    def test_ngshare_bad_status_404_delete(self):
        json = {'success': False, 'message': 'Something happened :('}
        url = '{}/student/{}/{}'.format(
            NGSHARE_URL, self.course_id, self.student_id
        )
        self.requests_mocker.delete(url, status_code=404, json=json)
        with pytest.raises(SystemExit):
            cm.main(
                ['remove_students', self.course_id, self.student_id, '--no-gb']
            )

    def test_ngshare_bad_status_404_post(self):
        json = {'success': False, 'message': 'Something happened :('}
        url = '{}/course/{}'.format(NGSHARE_URL, self.course_id)
        self.requests_mocker.post(url, status_code=404, json=json)
        with pytest.raises(SystemExit):
            cm.main(['create_course', self.course_id] + self.instructors)

    def test_ngshare_bad_status_500_delete(self):
        url = '{}/student/{}/{}'.format(
            NGSHARE_URL, self.course_id, self.student_id
        )
        self.requests_mocker.delete(url, status_code=500)
        with pytest.raises(SystemExit):
            cm.main(
                ['remove_students', self.course_id, self.student_id, '--no-gb']
            )

    def test_ngshare_bad_status_500_post(self):
        url = '{}/course/{}'.format(NGSHARE_URL, self.course_id)
        self.requests_mocker.post(url, status_code=500)
        with pytest.raises(SystemExit):
            cm.main(['create_course', self.course_id] + self.instructors)
