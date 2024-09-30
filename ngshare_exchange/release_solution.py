#!/usr/bin/python
import os

from traitlets import Bool

from nbgrader.exchange.abc import (
    ExchangeReleaseSolution as ABCExchangeReleaseSolution,
)
from .exchange import Exchange


class ExchangeReleaseSolution(Exchange, ABCExchangeReleaseSolution):
    def init_src(self):
        self.src_path = self.coursedir.format_path(
            self.coursedir.solution_directory, '.', self.coursedir.assignment_id
        )

        if not os.path.isdir(self.src_path):
            source = self.coursedir.format_path(
                self.coursedir.source_directory,
                '.',
                self.coursedir.assignment_id,
            )
            if os.path.isdir(source):
                self.fail(
                    'Assignment "{}" has no solution "{}", run `nbgrader generate_solution` first.'.format(
                        source, self.src_path
                    )
                )
            else:
                self._assignment_not_found(
                    self.src_path,
                    self.coursedir.format_path(
                        self.coursedir.solution_directory, '.', '*'
                    ),
                )

    def init_dest(self):
        if self.coursedir.course_id == '':
            self.fail('No course id specified. Re-run with --course flag.')
        self.dest_path = '/solution/{}/{}'.format(
            self.coursedir.course_id, self.coursedir.assignment_id
        )

    def solution_exists(self):
        url = '/solutions/{}'.format(self.coursedir.course_id)
        response = self.ngshare_api_get(url)

        if response is None:
            self.log.error(
                'An error occurred while trying to check if the solution exists {}.'.format(
                    self.coursedir.course_id
                )
            )
            return True

        if self.coursedir.assignment_id in response['solutions']:
            if self.force:
                self.log.info(
                    'Overwriting solution: {} {}'.format(
                        self.coursedir.course_id, self.coursedir.assignment_id
                    )
                )
                delete_url = '/solution/{}/{}'.format(
                    self.coursedir.course_id, self.coursedir.assignment_id
                )
                response = self.ngshare_api_delete(delete_url)
                if response is None:
                    self.fail(
                        'An error occurred while trying to delete solution {}'.format(
                            self.coursedir.assignment_id
                        )
                    )
            else:
                self.fail(
                    'Solution already exists, add --force to overwrite: {} {}'.format(
                        self.coursedir.course_id, self.coursedir.assignment_id
                    )
                )

        return False

    def copy_files(self):
        if not self.solution_exists():
            self.log.info('Encoding files')
            data = self.encode_dir(self.src_path)
            response = self.ngshare_api_post(self.dest_path, data)
            if response is None:
                self.log.warning(
                    'An error occurred while trying to release solution {}'.format(
                        self.coursedir.assignment_id
                    )
                )
            else:
                self.log.info(
                    'Successfully released solution {}'.format(
                        self.coursedir.assignment_id
                    )
                )
