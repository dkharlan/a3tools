# TODO (rabies) - Allow PBO deployment
# TODO (rabies) - Allow patching the Missions section of the configuration file

command=$1
a3lsdt_name=$(basename $0)
a3lsdt_command_timeout=5

# TODO (rabies) - Move these to .a3lsdtrc and read overrides from that file
arma3_server_name="Arma 3 Life"
arma3_server_port=2302
arma3_server_root_directory=/home/arma3/arma3server
arma3_server_command=arma3server
arma3_profile=arma3life
arma3_profiles_directory=/home/arma3/profiles
arma3_basiccfg_file=/home/arma3/config/basic.cfg
arma3_config_file=/home/arma3/config/config.cfg
arma3_server_mods="@life_server;@extDB3"
arma3_server_opts=""
arma3_pid_file=/home/arma3/.a3lsdt_arma3.pid

[[ -e $arma3_pid_file ]] && arma3_existing_pid=$(< $arma3_pid_file)
echo "PID: $arma3_existing_pid"

log() {
  printf "[%s] $1\n" "$(date)" "${@:2}"
}

show_help() {
  echo "Arma 3 Life Server Deployment Tool"
}

cleanup_pid_file() {
  rm -f $arma3_pid_file
  arma3_existing_pid=""
}

check_for_orphaned_pid() {
  if [[ -e $arma3_pid_file ]] && ! kill -0 $arma3_existing_pid; then
    log "Arma 3 PID file exists, but the specified PID is not running; cleaning up."
    cleanup_pid_file
  fi
}

handle_start() {
  if [[ -n $arma3_existing_pid ]]; then
    log "The Arma 3 server is already running (PID $arma3_existing_pid); use 'restart' instead."
    return 1
  fi

  local a3lsdt_launch_directory
  a3lsdt_launch_directory=$(pwd)

  log "Starting Arma 3 server..."
  log "\tName = %s" "$arma3_server_name"
  log "\tRoot = %s" $arma3_server_root_directory
  log "\tPort = %s" $arma3_server_port

  if ! cd $arma3_server_root_directory; then
    log "Could not change directory to $arma3_server_root_directory; exiting."
    return 1
  fi

  ./$arma3_server_command                 \
      -name=$arma3_profile                \
      -port=$arma3_server_port            \
      -cfg=$arma3_basiccfg_file           \
      -config=$arma3_config_file          \
      -profiles=$arma3_profiles_directory \
      -serverMod=$arma3_server_mods       \
      -nosound                            \
      -autoInit                           \
      $arma3_server_opts
  echo $! > $arma3_pid_file

  log "Arma 3 server has been started."

  cd "$a3lsdt_launch_directory" || return
}

handle_stop() {
  if [[ -z $arma3_existing_pid ]]; then
    log "The Arma 3 server is not running (or the PID file $arma3_pid_file does not exist)."
    return 1
  fi

  log "Stopping Arma 3 server..."
  kill -SIGTERM "$arma3_existing_pid"

  local kill_wait_seconds
  kill_wait_seconds=0
  while kill -0 $arma3_existing_pid; do
    if [[ $kill_wait_seconds -ge $a3lsdt_command_timeout ]]; then
      log "The Arma 3 server did not shut down after $a3lsdt_command_timeout seconds.  Killing forcibly..."
      kill -SIGKILL $arma3_existing_pid
    fi
    sleep 1
    ((++kill_wait_seconds))
  done

  cleanup_pid_file

  log "The Arma 3 server has been stopped."
}

handle_restart() {
  handle_stop
  handle_start
}

check_for_orphaned_pid
case $command in
"" | "-h" | "--help")
  show_help
  ;;
*)
  shift
  "handle_${command}" "$@"
  if [ $? = 127 ]; then
    echo "Error: '$command' is not a known command." >&2
    printf "\tRun '%s --help' for a list of known subcommands.\n" "$a3lsdt_name" >&2
    exit 1
  fi
  ;;
esac
