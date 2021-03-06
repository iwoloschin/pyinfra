from __future__ import unicode_literals

import re

import six

from pyinfra.api import FactBase

from .util.packaging import parse_packages


class DebPackages(FactBase):
    '''
    Returns a dict of installed dpkg packages:

    .. code:: python

        'package_name': ['version'],
        ...
    '''

    command = 'which dpkg > /dev/null && dpkg -l || true'
    regex = r'^ii\s+([a-zA-Z0-9\+\-\.]+):?[a-zA-Z0-9]*\s+([a-zA-Z0-9:~\.\-\+]+).+$'
    default = dict

    def process(self, output):
        return parse_packages(self.regex, output)


class DebPackage(FactBase):
    '''
    Returns information on a .deb archive or installed package.
    '''

    _regexes = {
        'name': r'^Package: ([a-zA-Z0-9\-]+)$',
        'version': r'^Version: ([0-9\:\.\-]+)$',
    }

    def command(self, name):
        return (
            'which dpkg > /dev/null && (dpkg -I {0} 2> /dev/null || dpkg -s {0}) || true'
        ).format(name)

    def process(self, output):
        data = {}

        for line in output:
            line = line.strip()
            for key, regex in six.iteritems(self._regexes):
                matches = re.match(regex, line)
                if matches:
                    value = matches.group(1)
                    data[key] = value
                    break

        return data
