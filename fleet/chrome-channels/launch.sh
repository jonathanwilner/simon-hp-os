# Called by the packaged channel wrapper; Stable uses its existing launcher.
set -euo pipefail
channel="$1"
browser="$2"
shift 2
for argument in "$@"; do
  case "$argument" in
    --user-data-dir|--user-data-dir=*|-user-data-dir|-user-data-dir=*)
      echo "Chrome $channel uses its dedicated profile; --user-data-dir is reserved." >&2
      exit 2 ;;
    --remote-debugging-*|-remote-debugging-*)
      echo 'Remote debugging belongs to Chrome Stable automation.' >&2
      exit 2 ;;
  esac

done
unset GOOGLE_CHROME_PROFILE_DIR CHROME_USER_DATA_DIR CHROME_REMOTE_DEBUGGING_PORT GOOGLE_CHROME_REMOTE_DEBUGGING_PORT GOOGLE_CHROME_REMOTE_DEBUG GOOGLE_CHROME_REMOTE_DEBUG_PORT REMOTE_DEBUGGING_PORT
profile="${XDG_CONFIG_HOME:-$HOME/.config}/google-chrome-$channel"
exec "$browser" "--user-data-dir=$profile" "$@"
