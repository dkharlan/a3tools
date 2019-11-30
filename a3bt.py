#!/usr/bin/env python

import os.path
import sys
import textwrap
import subprocess
from shutil import copy, copytree, rmtree, make_archive
from zipfile import ZipFile
from datetime import datetime
from argparse import ArgumentParser
from tempfile import TemporaryDirectory
from itertools import chain

from configparser import ConfigParser

ARMA3_MAP_TYPES = ["Altis", "Stratis", "Tanoa"]
RC_FILE = '.a3btrc'
RC_DEFAULTS = {
    'build_dir': 'build',
    'pbo_packer': 'PBOConsole.exe',

    # TODO (dkharlan) - The following options are disabled pending Linux server support.
    # 'remote_connection': '%(remote_user)s@%(remote_host)s',
    # 'remote_command': '\\AltisLifeTools\\a3sdt.cmd'
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


def _pack_pbo(config, details, manifest_output_directory):
    source_directory = os.path.realpath(details['baseName'])
    pbo_base_name = details['baseName']
    if details['type'] == 'mpmission':
        pbo_base_name += '.' + details['terrain']

    pbo_output_path = os.path.join(manifest_output_directory, '%ss' % details['type'], '%s.pbo' % pbo_base_name)

    log('Building %s from %s...' % (pbo_base_name, source_directory))

    with TemporaryDirectory() as build_directory:
        copytree(source_directory, build_directory)
        if 'sqm' in details:
            log('Using %s as mission.sqm' % details['sqm'])
            copy(os.path.realpath(details['sqm']), os.path.join(build_directory, 'mission.sqm'))

        subprocess.run([config['pbo_packer'], '-pack', build_directory, pbo_output_path], stdout=subprocess.PIPE)


class Commands:
    # noinspection PyUnusedLocal
    @staticmethod
    def clean(config, args):
        if os.path.exists(config['build_dir']):
            rmtree(config['build_dir'])
        log('Cleaned %s directory.' % config['build_dir'])

    @staticmethod
    def pack(config, args):
        manifest = config['manifest']

        timestamp = datetime.utcnow().strftime('%m%d%Y_%H%M%S')
        build_name = '%s_%s' % (manifest['baseName'], timestamp)

        results_directory = os.path.realpath('results')
        with TemporaryDirectory() as build_directory:
            config_directory = os.path.join(build_directory, 'config')

            os.makedirs(build_directory, exist_ok=True)
            os.makedirs(config_directory)
            if any(map(lambda m: m['type'] == 'mpmission', manifest['mods'])):
                os.makedirs(os.path.join(build_directory, 'mpmissions'))
            if any(map(lambda m: m['type'] == 'serverMod', manifest['mods'])):
                os.makedirs(os.path.join(build_directory, 'serverMods'))

            for mod_details in manifest['mods']:
                if mod_details['type'] in {'mpmission', 'serverMod'}:
                    _pack_pbo(config, mod_details, build_directory)
                else:
                    raise NotImplementedError('Unknown mod type "%s" for mod "%s"'
                                              % (mod_details['type'], mod_details['baseName']))

            copy(os.path.realpath(config['artifacts']['basicConfig']), os.path.join(config_directory, 'basic.cfg'))
            copy(os.path.realpath(config['artifacts']['config']), os.path.join(config_directory, 'config.cfg'))

            with ZipFile(os.path.join(results_directory, '%s.zip' % build_name), 'w') as result_archive:
                result_archive.write(build_directory)

        log('Finished building %s' % final_pbo_path)

    # TODO (dkharlan) - Re-enable when Linux server support is added.
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

    # TODO (dkharlan) - Re-enable when Linux server support is added.
    # noinspection PyUnusedLocal
    @staticmethod
    def start_server(config, args=None):
        raise NotImplementedError('start_server command is temporarily disabled pending Linux server support.')
        # subprocess.check_call(['ssh', '-t', config['remote_connection'],
        #                        '"' + config['remote_command'] + ' start"'])

    # TODO (dkharlan) - Re-enable when Linux server support is added.
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
    main_parser = ArgumentParser(description='Arma 3 Build Tool')
    subparsers = main_parser.add_subparsers(help='Commands', dest='command')
    subparsers.required = True

    subparsers.add_parser('clean', help='Clean the build directory')

    pack_parser = subparsers.add_parser('pack', help='Build a PBO')
    pack_parser.add_argument('manifest', type=str, help='The manifest to pack, defined in .a3trc', required=True)

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
    manifest = config['manifests'][args.manifest]
    del config['manifests']
    config['manifest'] = manifest

    commands_to_handlers[command](config, args)


if __name__ == '__main__':
    main()
