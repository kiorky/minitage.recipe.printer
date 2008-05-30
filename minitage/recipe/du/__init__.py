#!/usr/bin/env python

# Copyright (C) 2008, Mathieu PASQUET <kiorky@cryptelium.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

__docformat__ = 'restructuredtext en'

import datetime
import imp
import logging
import os
import setuptools.archive_util
import sha
import shutil
import sys
import tempfile
import urllib2
import urlparse

from minitage.recipe import common
from minitage.core import core

class Recipe(common.MinitageCommonRecipe):
    """
    Downloads and installs a distutils Python distribution.
    """
    def __init__(self, buildout, name, options):
        common.MinitageCommonRecipe.__init__(self,
                                    buildout, name, options)


    def install(self):
        """installs a python package using distutils.

        - You can play with pre-setup-hook and post-setup-hook to make as in
            hexagonit.cmmi
        - You can apply patches, and more over specificly to your os with
            those 4 options in buildout:

                - freebsd-patches
                - linux-patches
                - patches
                - darwin-patches
        """
        # initialise working directories
        for path in [self.prefix, self.tmp_directory]:
            if not os.path.exists(path):
                os.makedirs(path)
        try:
            self.logger.info('Installing python package.')
            # downloading
            fname = self._download()

            # unpack
            self._unpack(fname)

            # get default compilation directory
            self.compil_dir = self._get_compil_dir(self.tmp_directory)
            self.options['compile-directory'] = self.compil_dir

            # build-dir behaviour is significantly different that in cmmi,
            # build-dir is where we have the setup.py if it is not at
            # the top root of the archive.
            if self.build_dir:
                self.compil_dir = os.path.join(
                    self.compil_dir,
                    self.build_dir
                )

            # set path
            self._set_path()

            # set pkgconfigpath
            self._set_pkgconfigpath()

            # set python path
            self._set_py_path()

            # applying patches
            self._patch(self.compil_dir)

            # executing pre-hook.
            self._call_hook('pre_setup_hook')

            # compile time
            self._build_python_package(self.compil_dir)

            # executing pre-hook.
            self._call_hook('pre_install_hook')

            # install time
            self._install_python_package(self.compil_dir)

            # executing pre-hook.
            self._call_hook('post_setup_hook')
            self.logger.info('Installation completed.')

        except Exception, e:
            self.logger.error('Compilation error. The package is left as is at %s where '
                      'you can inspect what went wrong' % self.tmp_directory)
            self.logger.error('Message was:\n\t%s' % e)
            raise core.MinimergeError('Recipe failed, cant install.')

        shutil.rmtree(self.tmp_directory)

        os.chdir(self.buildout['buildout']['directory'])

        return []

    def update(self):
        pass

    def _build_python_package(self, directory):
        """Compile a python package."""
        cwd = os.getcwd()
        os.chdir(directory)
        cmds = []
        self._set_py_path()
        self._set_compilation_flags()
        # compilation phase if we have an extension module.
        # accepting ''
        if 'build-ext' in self.options\
           or self.options.get('rpath',None) \
           or self.options.get('libraries',None) \
           or self.options.get('includes',None):
            cmds.append(
                '"%s" setup.py build_ext %s' % (
                    self.executable,
                    self.build_ext.replace('\n', '')
                )
            )

        # build package
        cmds.append('"%s" setup.py build' % (self.executable))

        for cmd in cmds:
            self._system(cmd)

        os.chdir(cwd)

    def _install_python_package(self, directory):
        """Install a python package."""
        self._set_py_path()
        cmd = '"%s" setup.py install %s  %s %s' % (
            self.executable,
            '--install-purelib="%s"' % self.site_packages_path,
            '--install-platlib="%s"' % self.site_packages_path,
            '--prefix=%s' % self.buildout['buildout']['directory']
        )
        # moving and restoring if problem :)
        cwd = os.getcwd()
        os.chdir(directory)
        tmp = '%s.old' % self.site_packages_path
        if os.path.exists(self.site_packages_path):
            shutil.move(self.site_packages_path, tmp)

        if not self.options.get('noinstall', None):
            try:
                os.makedirs(self.site_packages_path)
                self._system(cmd)
            except Exception, e:
                shutil.rmtree(self.site_packages_path)
                shutil.move(tmp, self.site_packages_path)
                raise core.MinimergeError('PythonPackage Install failed:\n\t%s' % e)
        if os.path.exists(tmp):
            shutil.rmtree(tmp)
        os.chdir(cwd)

    
