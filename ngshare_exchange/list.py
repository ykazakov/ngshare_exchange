import os
import glob
import shutil
import re
import hashlib

from nbgrader.exchange.abc import ExchangeList as ABCExchangeList
from .exchange import Exchange


def _checksum(path):
    m = hashlib.md5()
    m.update(open(path, 'rb').read())
    return m.hexdigest()


def _merge_notebooks_feedback(notebook_ids, checksums):
    """
    Returns a list of dictionaries with 'notebook_id' and 'feedback_checksum'.

    ``notebook_ids`` - A list of notebook IDs.
    ``checksum`` - A dictionary mapping notebook IDs to checksums.
    """
    merged = []
    for nb_id in notebook_ids:
        if nb_id not in checksums.keys():
            checksum = None
        else:
            checksum = checksums[nb_id]
        merged.append({'notebook_id': nb_id, 'feedback_checksum': checksum})
    return merged


def _parse_notebook_id(path, extension='.ipynb'):
    """
    Returns the notebook_id from the path. If the path is not a file with the
    extension, returns None.
    """
    split_name = os.path.splitext(os.path.split(path)[1])
    if split_name[1] == extension:
        return split_name[0]
    return None


class ExchangeList(Exchange, ABCExchangeList):
    def _get_assignments(self, course_ids):
        """
        Returns a list of assignments. Each assignment is a dictionary
        containing the course_id and assignment_id.

        ``course_ids`` - A list of course IDs.
        """
        assignments = []
        for course_id in course_ids:
            response = self.ngshare_api_get('/assignments/{}'.format(course_id))
            if response is None:
                self.log.error(
                    'Failed to get assignments from course {}.'.format(
                        course_id
                    )
                )
                continue

            assignments += [
                {'course_id': course_id, 'assignment_id': x}
                for x in response['assignments']
            ]

        return assignments

    def _get_courses(self):
        """
        Returns a list of course_ids.
        """

        response = self.ngshare_api_get('/courses')
        if response is None:
            return None
        return response['courses']

    def _get_solutions(self, course_ids):
        """
        Returns a list of released solutions. Each solution is a dictionary
        containing the course_id and assignment_id.

        ``course_ids`` - A list of course IDs.
        """
        solutions = []
        for course_id in course_ids:
            response = self.ngshare_api_get('/solutions/{}'.format(course_id))
            if response is None:
                self.log.error(
                    'Failed to get solutions from course {}.'.format(course_id)
                )
                continue

            solutions += [
                {'course_id': course_id, 'assignment_id': x}
                for x in response['solutions']
            ]

        return solutions

    def _get_feedback_checksums(
        self, course_id, assignment_id, student_id, timestamp
    ):
        """
        Returns the checksums of all feedback files for a specific submission.
        This is a dictionary mapping all notebook_ids to the feedback file's
        checksum.
        """
        url = '/feedback/{}/{}/{}'.format(course_id, assignment_id, student_id)
        params = {'list_only': 'true', 'timestamp': timestamp}

        response = self.ngshare_api_get(url, params)
        if response is None:
            return None

        checksums = {}
        for file_entry in response['files']:
            notebook_id = _parse_notebook_id(file_entry['path'], '.html')
            if notebook_id is not None:
                checksums[notebook_id] = file_entry['checksum']

        return checksums

    def _get_notebooks(self, course_id, assignment_id):
        """
        Returns a list of notebook_ids from the assignment.
        """
        url = '/assignment/{}/{}'.format(course_id, assignment_id)
        params = {'list_only': 'true'}

        response = self.ngshare_api_get(url, params)
        if response is None:
            return None

        return [
            os.path.splitext(os.path.split(x['path'])[1])[0]
            for x in response['files']
        ]

    def _get_solution_notebooks(self, course_id, assignment_id):
        """
        Returns a list of notebook_ids from the solution.
        """
        url = '/solution/{}/{}'.format(course_id, assignment_id)
        params = {'list_only': 'true'}

        response = self.ngshare_api_get(url, params)
        if response is None:
            return None

        return [
            os.path.splitext(os.path.split(x['path'])[1])[0]
            for x in response['files']
        ]

    def _get_submissions(self, assignments, student_id=None):
        """
        Returns a list of submissions. Each submission is a dictionary
        containing the 'course_id', 'assignment_id', 'student_id', 'timestamp'
        and a list of 'notebooks'. Each notebook is a dictionary containing a
        'notebook_id' and 'feedback_checksum'.

        ``assignments`` - A list of dictionaries containing 'course_id' and
        'assignment_id'.
        ``student_id`` - Used to specify a specific student's submissions to
        get. If None, submissions from all students are fetched if permitted.
        """
        submissions = []
        for assignment in assignments:
            course_id = assignment['course_id']
            assignment_id = assignment['assignment_id']
            url = '/submissions/{}/{}'.format(course_id, assignment_id)

            if student_id is not None:
                url += '/' + student_id

            response = self.ngshare_api_get(url)
            if response is None:
                self.log.error('Failed to get submisions for assignment {}.')
                continue

            for submission in response['submissions']:
                notebook_ids = self._get_submission_notebooks(
                    course_id,
                    assignment_id,
                    submission['student_id'],
                    submission['timestamp'],
                )
                if notebook_ids is None:
                    self.log.error(
                        'Failed to list notebooks in submission '
                        '{}/{} from student {} (timestamp {})'.format(
                            course_id,
                            assignment_id,
                            submission['student_id'],
                            submission['timestamp'],
                        )
                    )
                    continue
                feedback_checksums = self._get_feedback_checksums(
                    course_id,
                    assignment_id,
                    submission['student_id'],
                    submission['timestamp'],
                )
                if feedback_checksums is None:
                    self.log.error('Failed to check for feedback.')
                    feedback_checksums = {}
                notebooks = _merge_notebooks_feedback(
                    notebook_ids, feedback_checksums
                )
                submissions.append(
                    {
                        'course_id': course_id,
                        'assignment_id': assignment_id,
                        'student_id': submission['student_id'],
                        'timestamp': submission['timestamp'],
                        'notebooks': notebooks,
                    }
                )

        return submissions

    def _get_submission_notebooks(
        self, course_id, assignment_id, student_id, timestamp
    ):
        """
        Returns a list of notebook_ids from a submission.
        """
        url = '/submission/{}/{}/{}'.format(
            course_id, assignment_id, student_id
        )
        params = {'list_only': 'true', 'timestamp': timestamp}

        response = self.ngshare_api_get(url, params)
        if response is None:
            return None

        notebooks = []
        for file_entry in response['files']:
            notebook_id = _parse_notebook_id(file_entry['path'], '.ipynb')
            if notebook_id is not None:
                notebooks.append(notebook_id)

        return notebooks

    def _unrelease_assignment(self, course_id, assignment_id):
        """
        Unrelease a released assignment.
        """
        url = '/assignment/{}/{}'.format(course_id, assignment_id)

        return self.ngshare_api_delete(url)

    def _unrelease_solution(self, course_id, assignment_id):
        """
        Unrelease a released solution.
        """
        url = '/solution/{}/{}'.format(course_id, assignment_id)

        return self.ngshare_api_delete(url)

    def init_src(self):
        pass

    def init_dest(self):
        course_id = (
            self.coursedir.course_id if self.coursedir.course_id else '*'
        )
        assignment_id = (
            self.coursedir.assignment_id
            if self.coursedir.assignment_id
            else '*'
        )
        student_id = (
            self.coursedir.student_id if self.coursedir.student_id else '*'
        )

        if course_id == '*':
            courses = self._get_courses()
            if courses is None:
                self.fail('Failed to get courses.')
        else:
            courses = [course_id]
        if assignment_id == '*':
            if self.solution:
                assignments = self._get_solutions(courses)
            else:
                assignments = self._get_assignments(courses)
        else:
            assignments = [
                {'course_id': course, 'assignment_id': assignment_id}
                for course in courses
            ]

        if self.inbound:
            if student_id == '*':
                student_id = None
            self.assignments = self._get_submissions(assignments, student_id)
        elif self.cached:
            pattern = os.path.join(
                self.cache,
                course_id,
                '{}+{}+*'.format(student_id, assignment_id),
            )
            self.assignments = sorted(glob.glob(pattern))
            if student_id == '*':
                student_id = None
        else:
            self.assignments = assignments

    def parse_assignment(self, assignment):
        if self.inbound:
            return {
                'course_id': assignment['course_id'],
                'student_id': assignment['student_id'],
                'assignment_id': assignment['assignment_id'],
                'timestamp': assignment['timestamp'],
            }
        elif self.cached:
            regexp = r'.*/(?P<course_id>.*)/(?P<student_id>.*)\+(?P<assignment_id>.*)\+(?P<timestamp>.*)'
        else:
            return assignment

        m = re.match(regexp, assignment)
        if m is None:
            raise RuntimeError(
                'Could not match "%s" with regexp "%s"', assignment, regexp
            )
        return m.groupdict()

    def format_inbound_assignment(self, info):
        msg = '{course_id} {student_id} {assignment_id} {timestamp}'.format(
            **info
        )
        if info['status'] == 'submitted':
            if info['has_local_feedback'] and not info['feedback_updated']:
                msg += ' (feedback already fetched)'
            elif info['has_exchange_feedback']:
                msg += ' (feedback ready to be fetched)'
            else:
                msg += ' (no feedback available)'
        return msg

    def format_outbound_assignment(self, info):
        msg = '{course_id} {assignment_id}'.format(**info)
        if os.path.exists(info['assignment_id']):
            msg += ' (already downloaded)'
        return msg

    def format_solution(self, info):
        msg = "{course_id} {assignment_id}".format(**info)
        if os.path.exists(os.path.join(info['assignment_id'], 'solution')):
            msg += " (already downloaded)"
        return msg

    def copy_files(self):
        pass

    def parse_assignments(self):
        if self.coursedir.student_id:
            courses = self.authenticator.get_student_courses(
                self.coursedir.student_id
            )
        else:
            courses = None

        assignments = []
        for assignment in self.assignments:
            info = self.parse_assignment(assignment)
            if courses is not None and info['course_id'] not in courses:
                continue

            if self.path_includes_course:
                assignment_dir = os.path.join(
                    self.assignment_dir,
                    info['course_id'],
                    info['assignment_id'],
                )
            else:
                assignment_dir = os.path.join(
                    self.assignment_dir, info['assignment_id']
                )

            if self.inbound or self.cached:
                info['status'] = 'submitted'
                if self.cached:
                    info['path'] = assignment
            elif self.solution:
                solution_dir = os.path.join(assignment_dir, 'solution')
                if os.path.exists(solution_dir):
                    info['status'] = 'fetched_solution'
                    info['path'] = os.path.abspath(solution_dir)
                else:
                    info['status'] = 'released_solution'
            elif os.path.exists(assignment_dir):
                info['status'] = 'fetched'
                info['path'] = os.path.abspath(assignment_dir)
            else:
                info['status'] = 'released'

            if self.remove:
                info['status'] = 'removed'

            if (
                self.cached
                or info['status'] == 'fetched'
                or info['status'] == 'fetched_solution'
            ):
                notebooks = sorted(
                    glob.glob(os.path.join(info['path'], '*.ipynb'))
                )
            elif self.inbound:

                def nb_key(nb):
                    return nb['notebook_id']

                notebooks = sorted(assignment['notebooks'], key=nb_key)
            elif self.solution:
                notebooks = self._get_solution_notebooks(
                    info['course_id'], info['assignment_id']
                )
                if notebooks is None:
                    self.log.error(
                        'Failed to get list of solution ' 'notebooks.'
                    )
                    notebooks = []
                notebooks = sorted(notebooks)
            else:
                notebooks = self._get_notebooks(
                    info['course_id'], info['assignment_id']
                )
                if notebooks is None:
                    self.log.error(
                        'Failed to get list of assignment ' 'notebooks.'
                    )
                    notebooks = []
                notebooks = sorted(notebooks)

            if not notebooks:
                self.log.warning(
                    'No notebooks found for assignment "{}" in '
                    'course "{}"'.format(
                        info['assignment_id'], info['course_id']
                    )
                )

            if self.cached:
                feedback_checksums = self._get_feedback_checksums(
                    info['course_id'],
                    info['assignment_id'],
                    info['student_id'],
                    info['timestamp'],
                )
                if feedback_checksums is None:
                    feedback_checksums = {}

            info['notebooks'] = []
            for notebook in notebooks:
                if (
                    self.cached
                    or info['status'] == 'fetched'
                    or info['status'] == 'fetched_solution'
                ):
                    nb_info = {
                        'notebook_id': os.path.splitext(
                            os.path.split(notebook)[1]
                        )[0],
                        'path': os.path.abspath(notebook),
                    }
                elif self.inbound:
                    nb_info = {'notebook_id': notebook['notebook_id']}
                elif (
                    info['status'] == 'fetched'
                    or info['status'] == 'fetched_solution'
                ):
                    nb_info = {
                        'notebook_id': notebook,
                        'path': os.path.abspath(notebook),
                    }
                else:
                    nb_info = {'notebook_id': notebook}
                if info['status'] != 'submitted':
                    info['notebooks'].append(nb_info)
                    continue

                nb_info['has_local_feedback'] = False
                nb_info['has_exchange_feedback'] = False
                nb_info['local_feedback_path'] = None
                nb_info['feedback_updated'] = False

                # Check whether feedback has been fetched already.
                local_feedback_dir = os.path.join(
                    assignment_dir, 'feedback', info['timestamp']
                )
                local_feedback_path = os.path.join(
                    local_feedback_dir,
                    '{0}.html'.format(nb_info['notebook_id']),
                )
                has_local_feedback = os.path.isfile(local_feedback_path)
                if has_local_feedback:
                    local_feedback_checksum = _checksum(local_feedback_path)
                else:
                    local_feedback_checksum = None

                # Also look to see if there is feedback available to fetch.
                if self.cached:
                    has_exchange_feedback = False
                    exchange_feedback_checksum = None
                    notebook_id = nb_info['notebook_id']
                    if notebook_id in feedback_checksums.keys():
                        has_exchange_feedback = True
                        exchange_feedback_checksum = feedback_checksums[
                            notebook_id
                        ]
                else:  # self.inbound
                    has_exchange_feedback = (
                        notebook['feedback_checksum'] is not None
                        and notebook['feedback_checksum'] != ''
                    )
                    if has_exchange_feedback:
                        exchange_feedback_checksum = notebook[
                            'feedback_checksum'
                        ]
                    else:
                        exchange_feedback_checksum = None

                nb_info['has_local_feedback'] = has_local_feedback
                nb_info['has_exchange_feedback'] = has_exchange_feedback
                if has_local_feedback:
                    nb_info['local_feedback_path'] = local_feedback_path
                if has_local_feedback and has_exchange_feedback:
                    nb_info['feedback_updated'] = (
                        exchange_feedback_checksum != local_feedback_checksum
                    )
                info['notebooks'].append(nb_info)

            if info['status'] == 'submitted':
                if info['notebooks']:
                    has_local_feedback = all(
                        [nb['has_local_feedback'] for nb in info['notebooks']]
                    )
                    has_exchange_feedback = all(
                        [
                            nb['has_exchange_feedback']
                            for nb in info['notebooks']
                        ]
                    )
                    feedback_updated = any(
                        [nb['feedback_updated'] for nb in info['notebooks']]
                    )
                else:
                    has_local_feedback = False
                    has_exchange_feedback = False
                    feedback_updated = False

                info['has_local_feedback'] = has_local_feedback
                info['has_exchange_feedback'] = has_exchange_feedback
                info['feedback_updated'] = feedback_updated
                if has_local_feedback:
                    info['local_feedback_path'] = os.path.join(
                        assignment_dir, 'feedback', info['timestamp']
                    )
                else:
                    info['local_feedback_path'] = None

            assignments.append(info)

        # partition the assignments into groups for course/student/assignment
        if self.inbound or self.cached:
            _get_key = lambda info: (
                info['course_id'],
                info['student_id'],
                info['assignment_id'],
            )
            _match_key = lambda info, key: (
                info['course_id'] == key[0]
                and info['student_id'] == key[1]
                and info['assignment_id'] == key[2]
            )
            assignment_keys = sorted(
                list(set([_get_key(info) for info in assignments]))
            )
            assignment_submissions = []
            for key in assignment_keys:
                submissions = [x for x in assignments if _match_key(x, key)]
                submissions = sorted(submissions, key=lambda x: x['timestamp'])
                info = {
                    'course_id': key[0],
                    'student_id': key[1],
                    'assignment_id': key[2],
                    'status': submissions[0]['status'],
                    'submissions': submissions,
                }
                assignment_submissions.append(info)
            assignments = assignment_submissions

        return assignments

    def list_files(self):
        '''List files.'''
        assignments = self.parse_assignments()

        if self.inbound or self.cached:
            self.log.info('Submitted assignments:')
            for assignment in assignments:
                for info in assignment['submissions']:
                    self.log.info(self.format_inbound_assignment(info))
        elif self.solution:
            self.log.info("Released solutions:")
            for info in assignments:
                self.log.info(self.format_solution(info))
        else:
            self.log.info('Released assignments:')
            for info in assignments:
                self.log.info(self.format_outbound_assignment(info))

        return assignments

    def remove_files(self):
        '''List and remove files.'''
        assignments = self.parse_assignments()

        if self.inbound or self.cached:
            self.log.info('Removing submitted assignments:')
            for assignment in assignments:
                for info in assignment['submissions']:
                    self.log.info(self.format_inbound_assignment(info))
        elif self.solution:
            self.log.info("Removing released solutions:")
            for info in assignments:
                self.log.info(self.format_solution(info))
        else:
            self.log.info('Removing released assignments:')
            for info in assignments:
                self.log.info(self.format_outbound_assignment(info))

        if self.cached:
            for assignment in self.assignments:
                shutil.rmtree(assignment)
        elif self.inbound:
            self.log.warning(
                'ngshare does not support removing submissions.'
            )  # TODO
        elif self.solution:
            for assignment in self.assignments:
                retvalue = self._unrelease_solution(
                    assignment['course_id'], assignment['assignment_id']
                )
                if retvalue is None:
                    self.log.error(
                        'Failed to remove solution {}/{}.'.format(
                            assignment['course_id'], assignment['assignment_id']
                        )
                    )
        else:
            for assignment in self.assignments:
                retvalue = self._unrelease_assignment(
                    assignment['course_id'], assignment['assignment_id']
                )
                if retvalue is None:
                    self.log.error(
                        'Failed to remove assignment {}/{}.'.format(
                            assignment['course_id'], assignment['assignment_id']
                        )
                    )

        return assignments
