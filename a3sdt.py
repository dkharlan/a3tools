#!/usr/bin/env python

import os
import sys
import time
import signal
import asyncio
import logging.config
from argparse import ArgumentParser
from asyncio.subprocess import PIPE

# TODO (dkharlan) - Test everything on Windows

# TODO (dkharlan) - Move these to .a3sdtrc and read overrides from that file; use platform-neutral paths
CONFIG = {
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
    'arma3_sigterm_timeout_seconds': 5000,
    'a3sdt_log_directory': '/home/arma3/logs'
}

# TODO (DKH) - Clean this up and allow it to set log levels dynamically (e.g. to support a --verbose CLI option)
logging.config.dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '%(asctime)s [%(levelname)-8s] %(message)s'
        },
        'unformatted': {
            'format': '%(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': logging.DEBUG
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': logging.DEBUG,
            'formatter': 'default',
            'filename': os.path.join(CONFIG['a3sdt_log_directory'], 'a3sdt.log'),
            'mode': 'a',
            'maxBytes': 10485760,
            'backupCount': 5
        },
        'file_unformatted': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': logging.DEBUG,
            'formatter': 'unformatted',
            'filename': os.path.join(CONFIG['a3sdt_log_directory'], 'a3sdt.log'),
            'mode': 'a',
            'maxBytes': 10485760,
            'backupCount': 5
        }
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': logging.DEBUG,
    },
    'loggers': {
        'file_only': {
            'handlers': ['file'],
            'level': logging.DEBUG,
            'propagate': False
        },
        'file_only_unformatted': {
            'handlers': ['file_unformatted'],
            'level': logging.DEBUG,
            'propagate': False,
        }
    }
})
log = logging.getLogger()

ARMA3_EXISTING_PID = None


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


def read_pid():
    if os.path.exists(CONFIG['arma3_pid_file']) and os.path.isfile(CONFIG['arma3_pid_file']):
        with open(CONFIG['arma3_pid_file'], 'r') as pid_file:
            global ARMA3_EXISTING_PID
            ARMA3_EXISTING_PID = int(pid_file.read().strip())


def process_is_running(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def check_for_orphaned_pid_file():
    if os.path.exists(CONFIG['arma3_pid_file']):
        assert ARMA3_EXISTING_PID
        if not process_is_running(ARMA3_EXISTING_PID):
            log.warning('Arma 3 PID file exists, but the specified PID is not running; cleaning up.')
            cleanup_pid_file()


async def _read_and_log(stream, logger):
    while True:
        line = await stream.readline()
        if not line:
            break
        logger(line)


async def _launch_arma3_server(command, args, working_directory):
    log.info('The Arma 3 server has been started.')

    # From now on, log only to the log file.
    logger = logging.getLogger('file_only')

    process = await asyncio.create_subprocess_exec(command, *args, cwd=working_directory, stdout=PIPE, stderr=PIPE)
    save_pid(process.pid)

    await asyncio.gather(
        _read_and_log(process.stdout, logger.info),
        _read_and_log(process.stderr, logger.error)
    )


def handle_start():
    if ARMA3_EXISTING_PID:
        log.error('The Arma 3 server is already running (PID %d); use \'restart\' instead.', ARMA3_EXISTING_PID)
        sys.exit(1)

    logging.getLogger('file_only_unformatted').info('\n\n%s', 80 * '-')
    log.info('Starting the Arma3 server...')
    log.info('\tName = %s', CONFIG['arma3_server_name'])
    log.info('\tRoot = %s', CONFIG['arma3_server_root_directory'])
    log.info('\tPort = %d', CONFIG['arma3_server_port'])

    pid = None
    process_description = 'CLI'

    # noinspection PyBroadException
    try:
        pid = os.fork()

        # Start the Arma 3 server from the child process.
        if pid == 0:
            # Mark the process name first, so that we can log it to tell where any uncaught exceptions come from.
            process_description = 'a3dst logger'

            working_directory = CONFIG['arma3_server_root_directory']
            command = os.path.join(working_directory, CONFIG['arma3_server_command'])
            args = [
                '-name="%s"' % CONFIG['arma3_server_name'],
                '-port=%d' % CONFIG['arma3_server_port'],
                '-cfg=%s' % CONFIG['arma3_basic_config_file'],
                '-config=%s' % CONFIG['arma3_config_file'],
                '-profiles=%s' % CONFIG['arma3_profiles_directory'],
                '-serverMod=%s' % CONFIG['arma3_server_mods'],
                '-nosound',
                '-autoInit'
            ]

            if os.name == "nt":
                loop = asyncio.ProactorEventLoop()
                asyncio.set_event_loop(loop)
            else:
                loop = asyncio.get_event_loop()
            loop.run_until_complete(_launch_arma3_server(command, args, working_directory))
            sys.exit(0)
    except SystemExit:
        log.debug('Caught SystemExit; shutting down %s (PID %d)', process_description, os.getpid())
        pass
    except:
        log.exception('Error while %s the Arma 3 server:', 'running' if pid == 0 else 'starting')
        sys.exit(1)


# noinspection PyTypeChecker
def handle_stop():
    if not ARMA3_EXISTING_PID:
        log.error('The Arma 3 server is not running (or the PID file %s does not exist).', CONFIG['arma3_pid_file'])
        sys.exit(1)

    log.info('Stopping the Arma 3 server...')
    os.kill(ARMA3_EXISTING_PID, signal.SIGTERM)

    kill_wait_seconds = 0
    while process_is_running(ARMA3_EXISTING_PID):
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

    return top_level_parser, handlers


def main():
    read_pid()
    check_for_orphaned_pid_file()

    parser, handlers = create_parser_and_handlers()
    args = parser.parse_args()
    handlers[args.command]()


if __name__ == '__main__':
    main()
