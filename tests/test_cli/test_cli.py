from os import path
from random import shuffle
from unittest import TestCase

from click.testing import CliRunner

import pyinfra

from pyinfra import pseudo_state
from pyinfra_cli.main import _main, cli

from ..paramiko_util import PatchSSHTestCase


def run_cli(*arguments):
    pyinfra.is_cli = True
    runner = CliRunner()
    result = runner.invoke(cli, arguments)
    pyinfra.is_cli = False
    return result


class TestCliEagerFlags(TestCase):
    def test_print_help(self):
        result = run_cli('--version')
        assert result.exit_code == 0

        result = run_cli('--help')
        assert result.exit_code == 0

    def test_print_facts_list(self):
        result = run_cli('--facts')
        assert result.exit_code == 0

    def test_print_operations_list(self):
        result = run_cli('--operations')
        assert result.exit_code == 0


class TestCliDeployRuns(PatchSSHTestCase):
    def setUp(self):
        pseudo_state.reset()

    def test_invalid_deploy(self):
        result = run_cli(
            '@local',
            'not-a-file.py',
        )
        assert result.exit_code == 1
        assert 'No deploy file: not-a-file.py' in result.stdout

    def test_deploy_inventory(self):
        result = run_cli(
            path.join('tests', 'deploy', 'inventories', 'inventory.py'),
            'server.shell',
            '--debug-data',
        )
        assert result.exit_code == 0

    def test_get_facts(self):
        result = run_cli(
            path.join('tests', 'deploy', 'inventories', 'inventory.py'),
            'fact',
            'os',
        )
        assert result.exit_code == 0
        assert '"somehost": null' in result.stdout

    def test_deploy_operation(self):
        result = run_cli(
            path.join('tests', 'deploy', 'inventories', 'inventory.py'),
            'server.shell',
            'echo hi',
        )
        assert result.exit_code == 0

    def test_deploy_operation_with_all(self):
        result = run_cli(
            path.join('tests', 'deploy', 'inventory_all.py'),
            'server.shell',
            'echo hi',
        )
        assert result.exit_code == 0

    def test_exec_command(self):
        result = run_cli(
            path.join('tests', 'deploy', 'inventories', 'inventory.py'),
            'exec',
            '--',
            'echo hi',
        )
        assert result.exit_code == 0

    def test_exec_command_with_options(self):
        result = run_cli(
            path.join('tests', 'deploy', 'inventories', 'inventory.py'),
            'exec',
            '--sudo',
            '--sudo-user', 'pyinfra',
            '--su-user', 'pyinfrawhat',
            '--port', '1022',
            '--user', 'ubuntu',
            '--',
            'echo hi',
        )
        assert result.exit_code == 0

    def test_exec_command_with_serial(self):
        result = run_cli(
            path.join('tests', 'deploy', 'inventories', 'inventory.py'),
            'exec',
            '--serial',
            '--',
            'echo hi',
        )
        assert result.exit_code == 0

    def test_exec_command_with_no_wait(self):
        result = run_cli(
            path.join('tests', 'deploy', 'inventories', 'inventory.py'),
            'exec',
            '--no-wait',
            '--',
            'echo hi',
        )
        assert result.exit_code == 0

    def test_exec_command_with_debug_operations(self):
        result = run_cli(
            path.join('tests', 'deploy', 'inventories', 'inventory.py'),
            'exec',
            '--debug-operations',
            '--',
            'echo hi',
        )
        assert result.exit_code == 0

    def test_exec_command_with_debug_facts(self):
        result = run_cli(
            path.join('tests', 'deploy', 'inventories', 'inventory.py'),
            'exec',
            '--debug-facts',
            '--',
            'echo hi',
        )
        assert result.exit_code == 0

    def test_exec_command_with_debug_data_limit(self):
        result = run_cli(
            path.join('tests', 'deploy', 'inventories', 'inventory.py'),
            'exec',
            '--debug-data',
            '--limit', 'somehost',
            '--',
            'echo hi',
        )
        assert result.exit_code == 0


class TestCliDeployState(PatchSSHTestCase):
    def test_deploy(self):
        # Run 3 iterations of the test - each time shuffling the order of the
        # hosts - ensuring that the ordering has no effect on the operation order.
        for _ in range(3):
            self._do_test_deploy()

    def _do_test_deploy(self):
        pseudo_state.reset()

        correct_op_name_and_host_names = [
            ('First main operation', True),  # true for all hosts
            ('Second main operation', ('somehost',)),
            ('tests/deploy/tasks/a_task.py | First task operation', ('anotherhost',)),
            ('tests/deploy/tasks/a_task.py | Second task operation', ('anotherhost',)),
            ('tests/deploy/tasks/a_task.py | First task operation', True),
            ('tests/deploy/tasks/a_task.py | Second task operation', True),
            ('Loop-0 main operation', True),
            ('Loop-1 main operation', True),
            ('Third main operation', True),
            ('Order loop 1', True),
            ('2nd Order loop 1', True),
            ('Order loop 2', True),
            ('2nd Order loop 2', True),
            ('Final limited operation', ('somehost',)),
        ]

        hosts = ['somehost', 'anotherhost', 'someotherhost']
        shuffle(hosts)

        result = run_cli(
            ','.join(hosts),
            path.join('tests', 'deploy', 'deploy.py'),
        )
        assert result.exit_code == 0

        state = pseudo_state
        op_order = state.get_op_order()

        assert (
            len(correct_op_name_and_host_names) == len(op_order)
        ), 'Incorrect number of operations detected'

        for i, (correct_op_name, correct_host_names) in enumerate(
            correct_op_name_and_host_names,
        ):
            op_hash = op_order[i]
            op_meta = state.op_meta[op_hash]

            assert list(op_meta['names'])[0] == correct_op_name

            for host in state.inventory:
                op_hashes = state.meta[host]['op_hashes']
                if correct_host_names is True or host.name in correct_host_names:
                    self.assertIn(op_hash, op_hashes)
                else:
                    self.assertNotIn(op_hash, op_hashes)


class TestDirectMainExecution(PatchSSHTestCase):
    '''
    These tests are very similar as above, without the click wrappers - basically
    here because coverage.py fails to properly detect all the code under the wrapper.
    '''

    def test_deploy_operation_direct(self):
        with self.assertRaises(SystemExit) as e:
            _main(
                inventory=path.join('tests', 'test_deploy', 'inventories', 'inventory.py'),
                operations=['server.shell', 'echo hi'],
                verbosity=0, user=None, port=None, key=None, key_password=None,
                password=None, sudo=False, sudo_user=None, su_user=None, parallel=None,
                fail_percent=0, dry=False, limit=None, no_wait=False, serial=False,
                winrm_username=None, winrm_password=None, winrm_port=None,
                shell_executable=None, quiet=False,
                debug=False, debug_data=False, debug_facts=False, debug_operations=False,
            )
            assert e.args == (0,)
