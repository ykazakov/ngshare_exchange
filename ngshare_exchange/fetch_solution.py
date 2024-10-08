#!/usr/bin/python
import os
from pathlib import Path

from nbgrader.exchange.abc import (
    ExchangeFetchSolution as ABCExchangeFetchSolution,
)
from .exchange import Exchange


class ExchangeFetchSolution(Exchange, ABCExchangeFetchSolution):
    def init_src(self):
        if self.coursedir.course_id == '':
            self.fail('No course id specified. Re-run with --course flag.')
        if not self.authenticator.has_access(
            self.coursedir.student_id, self.coursedir.course_id
        ):
            self.fail('You do not have access to this course.')

        self.src_path = '/solution/{}/{}'.format(
            self.coursedir.course_id, self.coursedir.assignment_id
        )

    def init_dest(self):
        if self.path_includes_course:
            root = os.path.join(
                self.coursedir.course_id, self.coursedir.assignment_id
            )
        else:
            root = self.coursedir.assignment_id
        assignment_root = os.path.join(self.assignment_dir, root)
        if not os.path.isdir(assignment_root):
            self.fail(
                'Assignment "{}" was not downloaded, run `nbgrader fetch_assignment` first.'.format(
                    self.coursedir.assignment_id
                )
            )
        self.dest_path = os.path.abspath(
            os.path.join(assignment_root, 'solution')
        )

        # check if solution folder exists
        if not os.path.exists(self.dest_path):
            Path(self.dest_path).mkdir()

    def do_copy(self, files):
        '''Copy the src dir to the dest dir omitting the self.coursedir.ignore globs.'''
        if os.path.isdir(self.dest_path):
            self.decode_dir(
                files,
                self.dest_path,
                ignore=self.ignore_patterns(),
                noclobber=True,
            )
        else:
            self.decode_dir(files, self.dest_path)

        self.log.info(
            'Successfully decoded {}.'.format(self.coursedir.assignment_id)
        )

    def copy_files(self):
        response = self.ngshare_api_get(self.src_path)
        if response is None:
            self.log.warning('Failed to fetch solution.')
        else:
            self.log.info(
                'Successfully fetched {}. Will try to decode'.format(
                    self.coursedir.assignment_id
                )
            )
            try:
                self.do_copy(response['files'])
            except:
                self.fail('Could not decode the solution')
