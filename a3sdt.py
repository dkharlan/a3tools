#!/usr/bin/env python

import os
import sys
import time
import signal
import logging
import subprocess
from argparse import ArgumentParser

# noinspection PyUnresolvedReferences
logging.dictConfig({
    'formatters': {
        'f': {
            'format': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
        }
    },
    'handlers': {
        'h': {
            'class': 'logging.StreamHandler',
            'formatter': 'f',
            'level': logging.DEBUG
        }
    },
    'root': {
        'handlers': ['h'],
        'level': logging.DEBUG
    }
})
CONFIG = {  # TODO (dkharlan) - Move these to .a3sdtrc and read overrides from that file
    'arma3_server_name': 'Arma 3 Life',
    'arma3_server_port': 2302,
    'arma3_server_root_directory': '/home/arma3/arma3server',
    'arma3_server_command': 'arma3server',
    'arma3_profile': 'arma3life',
    'arma3_profiles_directory': '/home/arma3/profiles',
    'arma3_basic_config_file': '/home/arma3/config/basic.cfg',
    'arma3_config_file': '/home/arma3/config/config.cfg',
    'arma3_server_mods': '@life_server;@extDB3',
    'arma3_server_opts': '',
    'arma3_pid_file': '/home/arma3/.a3sdt.arma3.pid',
    'arma3_sigterm_timeout_seconds': 5000
}
ARMA3_EXISTING_PID = None
log = logging.getLogger()


def cleanup_pid_file():
    try:
        os.remove(CONFIG['arma3_pid_file'])
    except FileNotFoundError:
        pass

    global ARMA3_EXISTING_PID
    ARMA3_EXISTING_PID = None


def save_pid(pid):
    with open(CONFIG['arma3_pid_file'], 'w') as pid_file:
        pid_file.write('%s' % pid)


# noinspection PyTypeChecker
def check_for_orphaned_pid_file():
    assert ARMA3_EXISTING_PID
    if os.path.exists(CONFIG['arma3_pid_file']) and os.kill(ARMA3_EXISTING_PID, 0):
        log.warning('Arma 3 PID file exists, but the specified PID is not running; cleaning up.')
        cleanup_pid_file()


def handle_start():
    if ARMA3_EXISTING_PID:
        log.error('The Arma 3 server is already running (PID %d); use \'restart\' instead.', ARMA3_EXISTING_PID)
        sys.exit(1)

    log.info('Starting the Arma3 server...')
    log.info('\tName = %s', CONFIG['arma3_server_name'])
    log.info('\tRoot = %s', CONFIG['arma3_server_root_directory'])
    log.info('\tPort = %d', CONFIG['arma3_server_port'])

    pid = None
    # noinspection PyBroadException
    try:
        pid = os.fork()

        # Start the Arma 3 server from the child process.
        if pid == 0:
            arma3_server_process = subprocess.Popen([
                CONFIG['arma3_server_command'],
                '-name=%s' % CONFIG['arma3_server_name'],
                '-port=%d' % CONFIG['arma3_server_port'],
                '-cfg=%s' % CONFIG['arma3_basic_config_file'],
                '-config=%s' % CONFIG['arma3_config_file'],
                '-profiles=%s' % CONFIG['arma3_profiles_directory'],
                '-serverMod=%s' % CONFIG['arma3_server_mods'],
                '-nosound',
                '-autoInit'
            ], cwd=CONFIG['arma3_server_root_directory'])
            save_pid(arma3_server_process.pid)
            log.info('The Arma 3 server has been started.')
            arma3_server_process.wait()
    except:
        log.exception('Error while %s the Arma 3 server:', 'running' if pid == 0 else 'starting')
        sys.exit(1)


# noinspection PyTypeChecker
def handle_stop():
    if ARMA3_EXISTING_PID is not None:
        log.error('The Arma 3 server is not running (or the PID file %s does not exist).', CONFIG['arma3_pid_file'])
        sys.exit(1)

    log.info('Stopping the Arma 3 server...')
    os.kill(ARMA3_EXISTING_PID, signal.SIGTERM)

    kill_wait_seconds = 0
    while os.kill(ARMA3_EXISTING_PID, 0):
        if kill_wait_seconds >= CONFIG['arma3_sigterm_timeout_seconds']:
            log.warning('The Arma 3 server did not shut down after %d seconds.  Killing forcibly...',
                        CONFIG['arma3_sigterm_timeout_seconds'])
            os.kill(ARMA3_EXISTING_PID, signal.SIGKILL)
        time.sleep(1)
        kill_wait_seconds += 1

    cleanup_pid_file()

    log.info('The Arma 3 server has been stopped.')


def handle_restart():
    handle_stop()
    handle_start()


def create_parser_and_handlers():
    top_level_parser = ArgumentParser(description='Arma 3 Server Management Tool')
    subparsers = top_level_parser.add_subparsers(help='Commands', dest='command', required=True)
    handlers = {}

    subparsers.add_parser('start', help='Start the Arma 3 server')
    handlers['start'] = handle_start

    subparsers.add_parser('stop', help='Stop the Arma 3 server')
    handlers['stop'] = handle_stop

    subparsers.add_parser('restart', help='Restart the Arma 3 server')
    handlers['restart'] = handle_restart

    return top_level_parser


def main():
    check_for_orphaned_pid_file()
    parser, handlers = create_parser_and_handlers()
    args = parser.parse_args()
    handlers[args.command]()


if __name__ == '__main__':
    main()
