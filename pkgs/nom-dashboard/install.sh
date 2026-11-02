#!/usr/bin/env bash
# Install the shared reporting tools on a Linux or macOS nom/tmux host.
set -euo pipefail
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
destination="${NOM_DASHBOARD_INSTALL_DIR:-$HOME/.local/share/nom-dashboard/tools}"
mkdir -p "$destination/web" "$HOME/.local/bin" "$HOME/.config/nom-dashboard"
for name in nom-tmux.sh nom-dashboard-sync.sh nom-dashboard-watch.sh nom-dashboard-record.py nom-dashboard-publish.py nom_dashboard_progress.py nom_dashboard_feed.py; do
  install -m755 "$source_dir/$name" "$destination/$name"
done
for name in index.html app.js styles.css; do
  install -m644 "$source_dir/web/$name" "$destination/web/$name"
done
ln -sfn "$destination/nom-tmux.sh" "$HOME/.local/bin/nom-tmux"
ln -sfn "$destination/nom-dashboard-sync.sh" "$HOME/.local/bin/nom-dashboard-sync"
ln -sfn "$destination/nom_dashboard_progress.py" "$HOME/.local/bin/nom-dashboard-progress"
if [[ $# -gt 0 ]]; then
  printf 'export NOM_DASHBOARD_REMOTE=%q\n' "$1" > "$HOME/.config/nom-dashboard/reporting.env"
fi
printf 'Installed shared reporting in %s\nAdd ~/.local/bin to PATH. nom-tmux refreshes progress while each task runs.\n' "$destination"
