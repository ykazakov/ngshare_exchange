#!/usr/bin/python
import os
import glob
from pathlib import Path

from nbgrader.exchange.abc import (
    ExchangeFetchFeedback as ABCExchangeFetchFeedback,
)
from .exchange import Exchange


class ExchangeFetchFeedback(Exchange, ABCExchangeFetchFeedback):
    def init_src(self):
        if self.coursedir.course_id == '':
            self.fail('No course id specified. Re-run with --course flag.')

        self.cache_path = os.path.join(self.cache, self.coursedir.course_id)
        assignment_id = (
            self.coursedir.assignment_id
            if self.coursedir.assignment_id
            else '*'
        )
        pattern = os.path.join(self.cache_path, '*+{}+*'.format(assignment_id))
        self.log.debug(
            'Looking for submissions with pattern: {}'.format(pattern)
        )

        self.src_path = '/feedback/{}/{}/{}'.format(
            self.coursedir.course_id, assignment_id, self.username
        )

        self.timestamps = []
        submissions = [os.path.split(x)[-1] for x in glob.glob(pattern)]
        for submission in submissions:
            (_, assignment_id, timestamp) = submission.split('/')[-1].split('+')
            self.timestamps.append(timestamp)

    def init_dest(self):
        if self.path_includes_course:
            root = os.path.join(
                self.coursedir.course_id, self.coursedir.assignment_id
            )
        else:
            root = self.coursedir.assignment_id
        self.dest_path = os.path.abspath(
            os.path.join(self.assignment_dir, root, 'feedback')
        )

        # check if feedback folder exists
        if not os.path.exists(self.dest_path):
            Path(self.dest_path).mkdir(parents=True)

    def copy_files(self):
        self.log.info('Fetching feedback from server')
        if len(self.timestamps) == 0:
            self.log.warning(
                'No feedback available to fetch for your submissions'
            )

        for timestamp in self.timestamps:
            params = {'timestamp': timestamp, 'list_only': 'false'}
            response = self.ngshare_api_get(self.src_path, params=params)
            if response is None:
                self.log.warning(
                    'An error occurred while trying to fetch feedback for {}'.format(
                        self.coursedir.assignment_id
                    )
                )
                return
            try:
                dest_with_timestamp = os.path.join(
                    self.dest_path, str(timestamp)
                )
                self.decode_dir(response['files'], dest_with_timestamp)
                self.log.info(
                    'Successfully decoded feedback for {} saved to {}'.format(
                        self.coursedir.assignment_id, dest_with_timestamp
                    )
                )
            except:
                self.log.warning(
                    'Could not decode feedback for timestamp {}'.format(
                        str(timestamp)
                    )
                )
