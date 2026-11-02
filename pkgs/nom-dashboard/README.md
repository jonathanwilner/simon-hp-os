# Task progress

`nom-tmux` exports `NOM_DASHBOARD_PROGRESS_FILE` to its command. A task can
publish counters with the installed `nom-dashboard-progress` command:

```sh
nom-dashboard-progress --completed 42 --total 100 --unit items --label 'Index files'
```

Use `--scope phase` when the percentage covers one phase of a larger task.
Use `--clear` when entering a phase whose total is unknown. Counters retain
their last measurement when a task fails; the task's exit status stays separate.
Tasks with unknown totals display their existing status without a percentage.

For resumable model downloads, register the source once:

```sh
nom-dashboard-progress --download-manifest /path/models.json \
  --download-root /path/models --label 'Model download' --scope phase
```

The manifest contains `models[].directory` and `models[].files[]` with `path`
and positive byte `size`. The publisher measures final files and the saved
aria2 v1 complete-piece bitmap of `FILE.aria2.partial.aria2`. Final files are
expected to have been verified and renamed by the downloader. Partial sparse
file lengths never count as downloaded bytes. In-flight pieces and unsaved
bitmap changes appear after aria2 saves them, so the percentage is conservative.
The source paths remain local; published JSON contains only counters and labels.

For an already-running task, supply `--file STATE_DIR/SESSION.progress.json`.
Flash model downloads register their source automatically on subsequent runs.
The current running task can receive the sidecar without restarting its workers.

Publishers refresh counters each time `nom-dashboard-sync` runs. Machine feeds
include `progress` with `completed`, `total`, `percent`, `unit`, `scope`, `label`,
and `updated_at`. The UI displays phase labels, decimal GB, percentages and
accessible progress bars. Percentage display floors to tenths so incomplete
work stays below 100%. The task status indicates installation success separately.

Each machine also publishes its current UI at
`/machines/HOST/dashboard/`. That preview reads the central manifest and remains
available while the central host awaits its usual guarded configuration deploy.
The root dashboard can use the same UI. A central host with the older publisher preserves the new
machine feed fields and the machine-local preview.

Validation:

```sh
nom-tmux test-nom-progress -- python3 -m unittest discover \
  -s pkgs/nom-dashboard -p test_progress.py
```

# Shared host setup

Reports remain local by default. Set `NOM_DASHBOARD_REMOTE` or the Home Manager
`services.nomDashboard.remote` option to your own authorized SSH destination to
publish reports. An empty value keeps reporting local.

```sh
bash pkgs/nom-dashboard/install.sh user@dashboard.example:/srv/nom-dashboard/public
```

The installer supports Linux and macOS hosts with bash, Python 3, nom, tmux,
rsync and SSH available. Local reports are under
`~/.local/state/nixos-intc/nom-dashboard/public`. Open `dashboard.html` through
a local web server or an authenticated server you control.

Each task refreshes reports approximately every 30 seconds and on completion.
Concurrent timers and tasks share a nonblocking per-machine synchronization lock.
