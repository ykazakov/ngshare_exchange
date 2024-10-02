import os
import sys
import requests
import csv
import subprocess
import json
import argparse
from urllib.parse import quote


# https://www.geeksforgeeks.org/print-colors-python-terminal/
def prRed(skk, exit=True):
    print('\033[91m {}\033[00m'.format(skk))

    if exit:
        sys.exit(-1)


def prGreen(skk):
    print('\033[92m {}\033[00m'.format(skk))


def prYellow(skk):
    print("\033[93m {}\033[00m".format(skk))


class User:
    def __init__(self, id, first_name, last_name, email):
        self.id = id
        self.first_name = '' if first_name is None else first_name
        self.last_name = '' if last_name is None else last_name
        self.email = '' if email is None else email


def get_username():
    if 'JUPYTERHUB_USER' in os.environ:
        return os.environ['JUPYTERHUB_USER']
    else:
        return os.environ['USER']


def ngshare_url():
    global _ngshare_url
    try:
        return _ngshare_url
    except NameError:
        try:
            from nbgrader.apps import NbGrader

            nbgrader = NbGrader()
            nbgrader.load_config_file()
            exchange = nbgrader.config.ExchangeFactory.exchange()
            _ngshare_url = exchange.ngshare_url
            return _ngshare_url
        except Exception as e:
            prRed(
                'Cannot determine ngshare URL. Please check your nbgrader_config.py!',
                False,
            )
            prRed(e)


def get_header():
    if 'JUPYTERHUB_API_TOKEN' in os.environ:
        return {'Authorization': 'token ' + os.environ['JUPYTERHUB_API_TOKEN']}
    else:
        return None


def check_status_code(response):
    if response.status_code != requests.codes.ok:
        prRed(
            'ngshare returned an invalid status code {}'.format(
                response.status_code
            ),
            False,
        )
        if response.status_code >= 500:
            prRed(
                'ngshare encountered an error. Please contact the maintainers'
            )

        check_message(response)


def check_message(response):
    response = response.json()
    if not response['success']:
        prRed(response['message'])

    return response


def encode_url(url):
    return quote(url, safe='/', encoding=None, errors=None)


def post(url, data):
    header = get_header()
    encoded_url = encode_url(url)

    try:
        response = requests.post(
            ngshare_url() + encoded_url, data=data, headers=header
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        prRed('Could not establish connection to ngshare server')
    except Exception:
        check_status_code(response)

    return check_message(response)


def delete(url, data):
    header = get_header()
    encoded_url = encode_url(url)
    try:
        response = requests.delete(
            ngshare_url() + encoded_url, data=data, headers=header
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        prRed('Could not establish connection to ngshare server')
    except Exception:
        check_status_code(response)

    return check_message(response)


def check_username_warning(users):
    invalid_usernames = [n for n in users if n != n.lower()]
    if invalid_usernames:
        prYellow(
            'The following usernames have upper-case letters. Normally JupyterHub forces usernames to be lowercase. If the user has trouble accessing the course, you should add their lowercase username to ngshare instead.',
        )
        for user in invalid_usernames:
            prYellow(user)


def create_course(args):
    instructors = args.instructors or []
    check_username_warning(instructors)

    url = '/course/{}'.format(args.course_id)
    data = {'user': get_username(), 'instructors': json.dumps(instructors)}

    response = post(url, data)
    prGreen('Successfully created {}'.format(args.course_id))


def add_student(args):
    # add student to ngshare
    check_username_warning([args.student_id])
    student = User(args.student_id, args.first_name, args.last_name, args.email)
    url = '/student/{}/{}'.format(args.course_id, student.id)
    data = {
        'user': get_username(),
        'first_name': student.first_name,
        'last_name': student.last_name,
        'email': student.email,
    }

    response = post(url, data)
    prGreen(
        'Successfully added/updated {} on {}'.format(student.id, args.course_id)
    )

    if not args.no_gb:
        add_jh_student(student)


def add_jh_student(student: User):
    # add student to nbgrader gradebook
    command = ['nbgrader', 'db', 'student', 'add']

    if len(student.first_name) > 0:
        command.append('--first-name')
        command.append(student.first_name)
    if len(student.last_name) > 0:
        command.append('--last-name')
        command.append(student.last_name)
    if len(student.email) > 0:
        command.append('--email')
        command.append(student.email)

    command.append(student.id)
    subprocess.run(command)


def add_students(args):
    students = []
    if not os.path.exists(args.csv_file):
        prRed(
            'The csv file you entered does not exist. Please enter a valid path!'
        )
    with open(args.csv_file, 'r') as f:
        csv_reader = csv.reader(f, delimiter=',')
        rows = list(csv_reader)
        if len(rows) == 0:
            prRed('The csv file you entered is empty')

        header = rows[0]

        required_cols = ['student_id', 'first_name', 'last_name', 'email']

        cols_dict = dict()
        for i, col in enumerate(header):
            cols_dict[col] = i

        for col in required_cols:
            if col not in cols_dict:
                prRed('Missing column {} in {}.'.format(col, args.csv_file))

        for i, row in enumerate(rows[1:]):
            student_dict = {}
            student_id = row[cols_dict['student_id']]
            if len(student_id.replace(' ', '')) == 0:
                prRed(
                    'Student ID cannot be empty (row {})'.format(i + 1), False
                )
                continue
            first_name = row[cols_dict['first_name']]
            last_name = row[cols_dict['last_name']]
            email = row[cols_dict['email']]

            student_dict['username'] = student_id
            student_dict['first_name'] = first_name
            student_dict['last_name'] = last_name
            student_dict['email'] = email
            students.append(student_dict)

    check_username_warning([student['username'] for student in students])
    url = '/students/{}'.format(args.course_id)
    data = {'user': get_username(), 'students': json.dumps(students)}

    response = post(url, data)

    if response['success']:
        for i, s in enumerate(response['status']):
            user = s['username']
            if s['success']:
                prGreen(
                    '{} was successfully added to {}'.format(
                        user, args.course_id
                    )
                )
                student = User(
                    user,
                    students[i]['first_name'],
                    students[i]['last_name'],
                    students[i]['email'],
                )
                if not args.no_gb:
                    add_jh_student(student)
            else:
                prRed(
                    'There was an error adding {} to {}: {}'.format(
                        user, args.course_id, s['message']
                    ),
                    False,
                )


def remove_jh_student(student_id, force):
    # remove a student from nbgrader gradebook
    command = 'nbgrader db student remove {} '.format(student_id)
    if force:
        command += '--force'
    os.system(command)


def remove_students(args):
    for student in args.students:
        if not args.no_gb:
            remove_jh_student(student, args.force)

        url = '/student/{}/{}'.format(args.course_id, student)
        data = {'user': get_username()}
        response = delete(url, data)
        prGreen(
            'Successfully deleted {} from {}'.format(student, args.course_id)
        )


def add_instructor(args):
    check_username_warning([args.instructor_id])
    url = '/instructor/{}/{}'.format(args.course_id, args.instructor_id)
    data = {
        'user': get_username(),
        'first_name': args.first_name,
        'last_name': args.last_name,
        'email': args.email,
    }
    print(data)
    response = post(url, data)
    prGreen(
        'Successfully added {} as an instructor to {}'.format(
            args.instructor_id, args.course_id
        )
    )


def remove_instructor(args):
    url = '/instructor/{}/{}'.format(args.course_id, args.instructor_id)
    data = {'user': get_username()}
    response = delete(url, data)
    prGreen(
        'Successfully deleted instructor {} from {}'.format(
            args.instructor_id, args.course_id
        )
    )


def parse_args(argv):
    parser = argparse.ArgumentParser(description='ngshare Course Management')
    subparsers = parser.add_subparsers()

    create_course_parser = subparsers.add_parser(
        'create_course', help='Create a course'
    )
    create_course_parser.add_argument(
        'course_id', metavar='COURSE_ID', help='ID of the course'
    )
    create_course_parser.add_argument(
        'instructors',
        metavar='INSTRUCTOR',
        nargs='*',
        default=None,
        help='List of instructors assigned to the course',
    )
    create_course_parser.set_defaults(func=create_course)

    add_instructor_parser = subparsers.add_parser(
        'add_instructor', help='Add/update one instructor for a course'
    )
    add_instructor_parser.add_argument(
        'course_id', metavar='COURSE_ID', help='ID of the course'
    )
    add_instructor_parser.add_argument(
        'instructor_id',
        metavar='INSTRUCTOR_ID',
        help='Username of the added/modified instructor',
    )
    add_instructor_parser.add_argument(
        '-f',
        '--first_name',
        default=None,
        help='First name of the instructor',
    )
    add_instructor_parser.add_argument(
        '-l',
        '--last_name',
        default=None,
        help='Last name of the instructor',
    )
    add_instructor_parser.add_argument(
        '-e',
        '--email',
        default=None,
        help='Email of the instructor',
    )
    add_instructor_parser.set_defaults(func=add_instructor)

    remove_instructor_parser = subparsers.add_parser(
        'remove_instructor', help='Remove one instructor from a course'
    )
    remove_instructor_parser.add_argument(
        'course_id', metavar='COURSE_ID', help='ID of the course'
    )
    remove_instructor_parser.add_argument(
        'instructor_id',
        metavar='INSTRUCTOR_ID',
        help='Username of the instructor to remove',
    )
    remove_instructor_parser.set_defaults(func=remove_instructor)

    add_student_parser = subparsers.add_parser(
        'add_student', help='Add/update one student for a course'
    )
    add_student_parser.add_argument(
        'course_id', metavar='COURSE_ID', help='ID of the course'
    )
    add_student_parser.add_argument(
        'student_id',
        metavar='STUDENT_ID',
        help='Username of the added/modified student',
    )
    add_student_parser.add_argument(
        '-f',
        '--first_name',
        default=None,
        help='First name of the student',
    )
    add_student_parser.add_argument(
        '-l',
        '--last_name',
        default=None,
        help='Last name of the student',
    )
    add_student_parser.add_argument(
        '-e',
        '--email',
        default=None,
        help='Email of the student',
    )
    add_student_parser.add_argument(
        '--no-gb',
        action='store_true',
        help='Do not add student to local nbgrader gradebook',
    )
    add_student_parser.set_defaults(func=add_student)

    add_students_parser = subparsers.add_parser(
        'add_students',
        help='Add/update multiple students in a course using a CSV file',
    )
    add_students_parser.add_argument(
        'course_id', metavar='COURSE_ID', help='ID of the course'
    )
    add_students_parser.add_argument(
        'csv_file',
        metavar='CSV_FILE',
        help='A CSV file with four fields: student_id,first_name,last_name,email',
    )
    add_students_parser.add_argument(
        '--no-gb',
        action='store_true',
        help='Do not add students to local nbgrader gradebook',
    )
    add_students_parser.set_defaults(func=add_students)

    remove_students_parser = subparsers.add_parser(
        'remove_students', help='Remove one or more students from a course'
    )
    remove_students_parser.add_argument(
        'course_id', metavar='COURSE_ID', help='ID of the course'
    )
    remove_students_parser.add_argument(
        'students',
        metavar='STUDENT',
        nargs='+',
        help='List of student IDs to remove',
    )
    remove_students_parser.add_argument(
        '--no-gb',
        action='store_true',
        help='Do not remove student from local nbgrader gradebook',
    )
    remove_students_parser.add_argument(
        '--force',
        action='store_true',
        help='Force student removal from local nbgrader gradebook, even if this deletes their grades',
    )
    remove_students_parser.set_defaults(func=remove_students)

    parser.set_defaults(func=lambda x: parser.print_help())
    args = parser.parse_args(argv)
    return args


def main(argv=None):
    argv = argv or sys.argv[1:]
    args = parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    sys.exit(main())
