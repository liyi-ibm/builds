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

import datetime
import logging
import os

from lib import config
from lib import exception
from lib.mock_package_builder import MockPackageBuilder
from lib.packages_manager import PackagesManager
from lib.rpm_package import RPM_Package
import lib.centos
import lib.scheduler

CONF = config.get_config().CONF
LOG = logging.getLogger(__name__)


class BuildManager(object):
    def __init__(self, packages_names, distro):
        self.packages_manager = PackagesManager(packages_names)
        self.distro = distro
        self.repositories = None
        self.timestamp = datetime.datetime.now().isoformat()

    def _build_packages(self, distro, packages):
        """
        Build packages

        Args:
            distro (Distribution): Linux distribution
            packages ([Package]): packages
        """

        # create package builder based on distro
        if distro.name in distro.names:
            mock_config_file_name = "%s-%s-%s.cfg" % (
                distro.name, distro.version, distro.architecture)
            mock_config_file_path = os.path.join(
                "config/mock", distro.name, distro.version,
                mock_config_file_name)
            if not os.path.isfile(mock_config_file_path):
                raise exception.BaseException(
                    "Mock config file not found at %s" % mock_config_file_path)
            package_builder = MockPackageBuilder(mock_config_file_path, self.timestamp)
        else:
            raise exception.DistributionError()
        # create packages
        package_builder.initialize()
        for package in packages:
            if package.force_rebuild:
                LOG.info("%s: Forcing rebuild." % package.name)
                build_package = True
            elif package.needs_rebuild():
                build_package = True
            else:
                LOG.info("%s: Skipping rebuild." % package.name)
                build_package = False

            if build_package:
                package.lock()
                package.download_files(recurse=False)
                package_builder.prepare_sources(package)
                package.unlock()
                package_builder.build(package)
            package_builder.copy_results(package)

        package_builder.create_repository()
        package_builder.create_latest_symlink_result_dir()
        package_builder.clean()

    def build(self):
        """
        Schedule package build order and build
        """

        force_rebuild = CONF.get('force_rebuild')
        try:
            # TODO: should not restrict building to RPM packages
            self.packages_manager.prepare_packages(
                packages_class=RPM_Package, distro=self.distro,
                download_source_code=False, force_rebuild=force_rebuild)
        # distro related issues
        except (exception.DistributionNotSupportedError,
                exception.DistributionVersionNotSupportedError,
                exception.DistributionDetectionError):
            LOG.error("Error during distribution detection. "
                      "See the logs for more information")
            raise

        scheduler = lib.scheduler.Scheduler()
        ordered_packages = scheduler.schedule(self.packages_manager.packages)
        self._build_packages(self.distro, ordered_packages)
