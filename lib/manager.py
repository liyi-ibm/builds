# Copyright (C) IBM Corp. 2016.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging

from lib import config
from lib import exception
from lib import package
import lib.scheduler
from lib import utils

CONF = config.get_config().CONF
LOG = logging.getLogger(__name__)


class BuildManager(object):
    def __init__(self):
        self.packages_list = CONF.get('default').get('packages')
        self.packages = None
        self.distro = None
        self.repositories = None

    def __call__(self):
        try:
            self._distro = utils.detect_distribution()
            self.packages = self._prepare_packages()
        # distro related issues
        except (exception.DistributionNotSupportedError,
                exception.DistributionVersionNotSupportedError,
                exception.DistributionDetectionError) as exc:
            LOG.exception("Error during distribution detection. "
                          "See the logs for more information")
            return exc.errno
        except exception.PackageError as exc:
            LOG.exception("Failed to load the package in components. "
                          "See the logs for more information")
            return exc.errno

        return self.build()

    def build(self):
        scheduler = lib.scheduler.Scheduler()
        self._distro.build_packages(scheduler(self.packages))

    def _prepare_packages(self):
        return [package.Package(x, self._distro) for x in set(
                self.packages_list)]