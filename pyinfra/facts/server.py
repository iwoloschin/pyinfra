from __future__ import unicode_literals

import os
import re
import shutil
from datetime import datetime
from tempfile import mkdtemp

from dateutil.parser import parse as parse_date

from pyinfra.api import FactBase, ShortFactBase
from pyinfra.api.util import try_int

from .util.distro import get_distro_info


class Home(FactBase):
    '''
    Returns the home directory of the current user.
    '''

    command = 'echo $HOME'


class Hostname(FactBase):
    '''
    Returns the current hostname of the server.
    '''

    command = 'hostname'


class Os(FactBase):
    '''
    Returns the OS name according to ``uname``.
    '''

    command = 'uname -s'


class OsVersion(FactBase):
    '''
    Returns the OS version according to ``uname``.
    '''

    command = 'uname -r'


class Arch(FactBase):
    '''
    Returns the system architecture according to ``uname``.
    '''

    command = 'uname -p'


class Command(FactBase):
    '''
    Returns the raw output lines of a given command.
    '''

    @staticmethod
    def command(command):
        return command


class Which(FactBase):
    '''
    Returns the path of a given command, if available.
    '''

    @staticmethod
    def command(name):
        return 'which {0} || true'.format(name)


class Date(FactBase):
    '''
    Returns the current datetime on the server.
    '''

    command = 'LANG=C date'
    default = datetime.now

    @staticmethod
    def process(output):
        return parse_date(output[0])


class Mounts(FactBase):
    '''
    Returns a dictionary of mounted filesystems and information.

    .. code:: python

        "/": {
            "device": "/dev/mv2",
            "type": "ext4",
            "options": [
                "rw",
                "relatime"
            ]
        },
        ...
    '''

    command = 'mount'
    default = dict

    @staticmethod
    def process(output):
        devices = {}

        for line in output:
            is_map = False
            if line.startswith('map '):
                line = line[4:]
                is_map = True

            device, _, path, other_bits = line.split(' ', 3)

            if is_map:
                device = 'map {0}'.format(device)

            if other_bits.startswith('type'):
                _, type_, options = other_bits.split(' ', 2)
                options = options.strip('()').split(',')
            else:
                options = other_bits.strip('()').split(',')
                type_ = options.pop(0)

            devices[path] = {
                'device': device,
                'type': type_,
                'options': [option.strip() for option in options],
            }

        return devices


class KernelModules(FactBase):
    '''
    Returns a dictionary of kernel module name -> info.

    .. code:: python

        'module_name': {
            'size': 0,
            'instances': 0,
            'state': 'Live',
        },
        ...
    '''

    command = 'find /proc/modules > /dev/null && cat /proc/modules || true'
    default = dict

    @staticmethod
    def process(output):
        modules = {}

        for line in output:
            name, size, instances, depends, state, _ = line.split(' ', 5)
            instances = int(instances)

            module = {
                'size': size,
                'instances': instances,
                'state': state,
            }

            if depends != '-':
                module['depends'] = [
                    value
                    for value in depends.split(',')
                    if value
                ]

            modules[name] = module

        return modules


class LsbRelease(FactBase):
    '''
    Returns a dictionary of release information using ``lsb_release``.

    .. code:: python

        {
            "id": "Ubuntu",
            "description": "Ubuntu 18.04.2 LTS",
            "release": "18.04",
            "codename": "bionic",
            ...
        }
    '''

    command = 'which lsb_release > /dev/null && lsb_release -ca || true'

    @staticmethod
    def process(output):
        items = {}

        for line in output:
            if ':' not in line:
                continue

            key, value = line.split(':', 1)

            key = key.strip().lower()

            # Turn "distributor id" into "id"
            if ' ' in key:
                key = key.split(' ')[-1]

            value = value.strip()

            items[key] = value

        return items


class Sysctl(FactBase):
    '''
    Returns a dictionary of sysctl settings and values.

    .. code:: python

        {
            "fs.inotify.max_queued_events": 16384,
            "fs.inode-state": [
                44565,
                360,
            ],
            ...
        }
    '''

    command = 'sysctl -a'
    default = dict

    @staticmethod
    def process(output):
        sysctls = {}

        for line in output:
            key = values = None

            if '=' in line:
                key, values = line.split('=', 1)
            elif ':' in line:
                key, values = line.split(':', 1)
            else:
                continue  # pragma: no cover

            if key and values:
                key = key.strip()
                values = values.strip()

                if re.match(r'^[a-zA-Z0-9_\.\s]+$', values):
                    values = [
                        try_int(item.strip())
                        for item in values.split()
                    ]

                    if len(values) == 1:
                        values = values[0]

                sysctls[key] = values

        return sysctls


class Groups(FactBase):
    '''
    Returns a list of groups on the system.
    '''

    command = 'cat /etc/group'
    default = list

    @staticmethod
    def process(output):
        groups = []

        for line in output:
            if ':' in line:
                groups.append(line.split(':')[0])

        return groups


class Crontab(FactBase):
    '''
    Returns a dictionary of cron command -> execution time.

    .. code:: python

        '/path/to/command': {
            'minute': '*',
            'hour': '*',
            'month': '*',
            'day_of_month': '*',
            'day_of_week': '*',
        },
        ...
    '''

    default = dict

    @staticmethod
    def command(user=None):
        if user:
            return 'which crontab > /dev/null && crontab -l -u {0} || true'.format(user)

        return 'which crontab > /dev/null && crontab -l || true'

    @staticmethod
    def process(output):
        crons = {}
        current_comments = []

        for line in output:
            line = line.strip()
            if not line or line.startswith('#'):
                current_comments.append(line)
                continue

            minute, hour, day_of_month, month, day_of_week, command = line.split(' ', 5)
            crons[command] = {
                'minute': try_int(minute),
                'hour': try_int(hour),
                'month': try_int(month),
                'day_of_month': try_int(day_of_month),
                'day_of_week': try_int(day_of_week),
                'comments': current_comments,
            }
            current_comments = []

        return crons


class Users(FactBase):
    '''
    Returns a dictionary of users -> details.

    .. code:: python

        'user_name': {
            'home': '/home/user_name',
            'shell': '/bin/bash,
            'group': 'main_user_group',
            'groups': [
                'other',
                'groups'
            ]
        },
        ...
    '''

    command = '''
        for i in `cat /etc/passwd | cut -d: -f1`; do
            ID=`id $i`;
            META=`cat /etc/passwd | grep ^$i: | cut -d: -f6-7`;
            echo "$ID $META";
        done
    '''.strip()

    default = dict

    regex = r'^uid=[0-9]+\(([a-zA-Z0-9_\.\-]+)\) gid=[0-9]+\(([a-zA-Z0-9_\.\-]+)\) groups=([a-zA-Z0-9_\.\-,\(\)\s]+) (.*)$'  # noqa
    group_regex = r'^[0-9]+\(([a-zA-Z0-9_\.\-]+)\)$'

    def process(self, output):
        users = {}
        for line in output:
            matches = re.match(self.regex, line)

            if matches:
                # Parse out the home/shell
                home_shell = matches.group(4)
                home = shell = None

                # /blah: is just a home
                if home_shell.endswith(':'):
                    home = home_shell[:-1]

                # :/blah is just a shell
                elif home_shell.startswith(':'):
                    shell = home_shell[1:]

                # Both home & shell
                elif ':' in home_shell:
                    home, shell = home_shell.split(':')

                # Main user group
                group = matches.group(2)

                # Parse the groups
                groups = []
                for group_matches in matches.group(3).split(','):
                    name = re.match(self.group_regex, group_matches.strip())
                    if name:
                        name = name.group(1)
                    else:
                        continue  # pragma: no cover

                    # We only want secondary groups here
                    if name != group:
                        groups.append(name)

                users[matches.group(1)] = {
                    'group': group,
                    'groups': groups,
                    'home': home,
                    'shell': shell,
                }

        return users


class LinuxDistribution(FactBase):
    '''
    Returns a dict of the Linux distribution version. Ubuntu, Debian, CentOS,
    Fedora & Gentoo currently. Also contains any key/value items located in
    release files.

    .. code:: python

        {
            'name': 'Ubuntu',
            'major': 20,
            'minor': 04,
            'release_meta': {
                'CODENAME': 'focal',
                'ID_LIKE': 'debian',
                ...
            }
        }
    '''
    command = ('cd /etc/ && for file in $(ls -pdL *-release | grep -v /); '
               'do echo "/etc/${file}"; cat "/etc/${file}"; echo ---; '
               'done')

    name_to_pretty_name = {
        'alpine': 'Alpine',
        'centos': 'CentOS',
        'fedora': 'Fedora',
        'gentoo': 'Gentoo',
        'opensuse': 'openSUSE',
        'rhel': 'RedHat',
        'ubuntu': 'Ubuntu',
    }

    @staticmethod
    def default():
        return {
            'name': None,
            'major': None,
            'minor': None,
            'release_meta': {},
        }

    def process(self, output):
        parts = {}
        for part in '\n'.join(output).strip().split('---'):
            if not part.strip():
                continue
            filename, content = part.strip().split('\n', 1)
            parts[filename] = content

        release_info = self.default()
        if not parts:
            return release_info

        temp_root = mkdtemp()
        try:
            temp_etc_dir = os.path.join(temp_root, 'etc')
            os.mkdir(temp_etc_dir)

            for filename, content in parts.items():
                with open(os.path.join(temp_etc_dir, os.path.basename(filename)), 'w') as fp:
                    fp.write(content)

            parsed = get_distro_info(temp_root)

            release_meta = {key.upper(): value for key, value in parsed.os_release_info().items()}
            release_info.update({
                'name': self.name_to_pretty_name.get(parsed.id(), parsed.name()),
                'major': try_int(parsed.major_version()),
                'minor': try_int(parsed.minor_version()) or None,
                'release_meta': release_meta,
            })

        finally:
            shutil.rmtree(temp_root)

        return release_info


class LinuxName(ShortFactBase):
    '''
    Returns the name of the Linux distribution. Shortcut for
    ``host.fact.linux_distribution['name']``.
    '''

    fact = LinuxDistribution

    @staticmethod
    def process_data(data):
        return data['name']


class Selinux(FactBase):
    '''
    Discovers the SELinux related facts on the target host.

    .. code:: python

        {
            'mode': 'enabled',
        }
    '''
    command = 'which sestatus > /dev/null && sestatus 2> /dev/null || true'

    @staticmethod
    def default():
        return {
            'mode': None,
        }

    def process(self, output):
        selinux_info = self.default()

        if not output:
            return selinux_info

        match = re.match(r'^SELinux status:\s+(\S+)', '\n'.join(output))

        if not match:
            return selinux_info

        selinux_info['mode'] = match.group(1)

        return selinux_info
