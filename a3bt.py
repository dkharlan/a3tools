#!/usr/bin/env python

import os
import sys
import os.path
import textwrap
import subprocess
from shutil import copy, copytree, rmtree
from itertools import chain
from datetime import datetime
from argparse import ArgumentParser
from configparser import ConfigParser

ARMA3_MAP_TYPES = ["Altis", "Stratis", "Tanoa"]
RC_FILE = '.a3lbtrc'
RC_DEFAULTS = {
    'build_dir': 'build',
    'pbo_packer': 'PBOConsole.exe',

    # TODO (rabies) - The following options are disabled pending Linux server support.
    # 'remote_connection': '%(remote_user)s@%(remote_host)s',
    # 'remote_command': '\\AltisLifeTools\\a3lsdt.cmd'
}


def log(message):
    print(textwrap.dedent(message))


def error(message):
    print(textwrap.dedent(message), file=sys.stderr)
    sys.exit(1)


def load_config():
    parser = ConfigParser(defaults=RC_DEFAULTS)
    if os.path.exists(RC_FILE):
        with open(RC_FILE, 'r') as rc_file:
            rc_file = chain(('[top]',), rc_file)
            parser.read_file(rc_file)
        return parser['top']
    else:
        return parser['DEFAULT']


def mod_directory(relative_path):
    _relative_path = relative_path.rstrip('/')
    if not os.path.exists(_relative_path):
        raise ValueError('%s is not a valid directory.')
    return _relative_path


def pbo_filename(pbo_name):
    if not pbo_name.lower().endswith('.pbo'):
        raise ValueError('%s is not a .pbo file' % pbo_name)
    return pbo_name


def sqm_filename(sqm_name):
    if not sqm_name.lower().endswith('.sqm'):
        raise ValueError('%s is not a .sqm file' % sqm_name)
    return sqm_name


def map_type(map_name):
    if map_name not in ARMA3_MAP_TYPES:
        map_names = ' or '.join([', '.join(ARMA3_MAP_TYPES[:-1]), ARMA3_MAP_TYPES[-1]])
        raise ValueError('%s does not appear to be an Arma 3 mod (doesn\'t end in %s).' % (map_type, map_names))
    return map_name


class Commands:
    # noinspection PyUnusedLocal
    @staticmethod
    def clean(config, args):
        if os.path.exists(config['build_dir']):
            rmtree(config['build_dir'])
        log('Cleaned %s directory.' % config['build_dir'])

    @staticmethod
    def pack(config, args):
        input_dir = args.source_directory
        pbo_base_name = '%s.%s' % (args.base_name, args.map_type)
        timestamp = datetime.utcnow().strftime('%m%d%Y_%H%M%S')

        if args.force_output_pbo_name:
            relative_pbo_path = args.force_output_pbo_name
        else:
            relative_pbo_path = os.path.join(config['build_dir'], pbo_base_name + '_' + timestamp + '.pbo')

        absolute_input_dir = os.path.realpath(input_dir)
        temp_dir = os.path.join(config['build_dir'], timestamp)
        relative_build_path = os.path.join(temp_dir, pbo_base_name)
        final_build_path = os.path.realpath(relative_build_path)

        final_pbo_path = os.path.realpath(relative_pbo_path)
        log('Building %s from %s' % (final_pbo_path, absolute_input_dir))
        copytree(absolute_input_dir, relative_build_path)
        if args.mission_sqm:
            existing_sqm_name = os.path.join(final_build_path, 'mission.sqm')
            if os.path.exists(existing_sqm_name):
                os.remove(existing_sqm_name)
            copy(args.mission_sqm, existing_sqm_name)
            log('Used %s for mission.sqm' % args.mission_sqm)
        try:
            subprocess.run([config['pbo_packer'], '-pack', final_build_path, final_pbo_path],
                           stdout=subprocess.PIPE)
        except FileNotFoundError as ex:
            if ex.filename is None:
                hint = '(Hint: Make sure %s is accessible via your PATH environment variable.)' % config['pbo_packer']
            else:
                hint = None
            error(
                '''
                Could not pack PBO because the file %s could not be found.
                Details:
                \tpbo_packer = %s %s
                \tbuild path = %s
                \tpbo path = %s
                '''
                % (ex.filename, config['pbo_packer'], hint, final_build_path, final_pbo_path)
            )

        if not os.path.exists(final_pbo_path):
            raise RuntimeError('Failed to build PBO.')

        log('Finished building %s' % final_pbo_path)

    # TODO (rabies) - Re-enable when Linux server support is added.
    @staticmethod
    def deploy(config, args):
        raise NotImplementedError('deploy command is temporarily disabled pending Linux server support.')
        # base_name = args.__dict__['<mod base path>']
        # server_relative_path = args.__dict__['<deployment path>']
        #
        # pbo_pattern = config['build_dir'] + os.path.sep + base_name + '*.[pP][bB][oO]'
        # newest_pbo = max(glob.iglob(pbo_pattern), key=os.path.getctime).replace('\\', '/')
        #
        # subprocess.check_call(['scp', newest_pbo, '%s:' % config['remote_connection']])
        # Commands.stop_server(config)
        # subprocess.check_call(['ssh', config['remote_connection'], config['remote_command'],
        #                        'deploy', base_name, server_relative_path])

    # TODO (rabies) - Re-enable when Linux server support is added.
    # noinspection PyUnusedLocal
    @staticmethod
    def start_server(config, args=None):
        raise NotImplementedError('start_server command is temporarily disabled pending Linux server support.')
        # subprocess.check_call(['ssh', '-t', config['remote_connection'],
        #                        '"' + config['remote_command'] + ' start"'])

    # TODO (rabies) - Re-enable when Linux server support is added.
    # noinspection PyUnusedLocal
    @staticmethod
    def stop_server(config, args=None):
        raise NotImplementedError('stop_server command is temporarily disabled pending Linux server support.')
        # subprocess.check_call(['ssh', config['remote_connection'],
        #                        '"' + config['remote_command'] + ' stop' + '"'])

    # noinspection PyUnusedLocal
    @staticmethod
    def restart_server(config, args=None):
        Commands.stop_server(config)
        Commands.start_server(config)


def create_parser():
    main_parser = ArgumentParser(description='Arma 3 Altis/Tanoa Life Build Tool')
    subparsers = main_parser.add_subparsers(help='Commands', dest='command')
    subparsers.required = True

    subparsers.add_parser('clean', help='Clean the build directory')

    pack_parser = subparsers.add_parser('pack', help='Build a PBO')
    pack_parser.add_argument('--source-directory', '-s', type=mod_directory, help='The source path for the mod')
    pack_parser.add_argument('--base-name', '-b', type=str, help='The base name for the mod')
    pack_parser.add_argument('--map-type', '-m', type=map_type,
                             help=' or '.join([', '.join(ARMA3_MAP_TYPES[:-1]), ARMA3_MAP_TYPES[-1]]))
    pack_parser.add_argument('--mission-sqm', '-S', type=sqm_filename, help='The file to use as mission.sqm in the PBO')
    pack_parser.add_argument('--force-output-pbo-name', '-o', type=pbo_filename, help='The name of the PBO to create')

    deploy_parser = subparsers.add_parser('deploy', help='Deploy a PBO')
    deploy_parser.add_argument('<mod base path>', type=str, help='The base directory for the mod')
    deploy_parser.add_argument('<deployment path>', type=str,
                               help='Deployment path relative to the server root directory')

    server_parser = subparsers.add_parser('server', help='Remote server administration')
    server_subparsers = server_parser.add_subparsers(help='Server admin commands', dest='server_command')

    server_subparsers.add_parser('start', help='Start the remote server')
    server_subparsers.add_parser('stop', help='Stop the remote server')
    server_subparsers.add_parser('restart', help='Restart the remove server')

    return main_parser


def main():
    commands_to_handlers = {
        'clean':                Commands.clean,
        'pack':                 Commands.pack,
        'deploy':               Commands.deploy,
        ('server', 'start'):    Commands.start_server,
        ('server', 'stop'):     Commands.stop_server,
        ('server', 'restart'):  Commands.restart_server
    }

    args = create_parser().parse_args()
    log('args = %s' % args)

    try:
        command = (args.command, args.server_command)
    except AttributeError:
        command = args.command

    config = load_config()
    commands_to_handlers[command](config, args)


if __name__ == '__main__':
    main()
