const state = {
  manifest: null,
  selected: null,
  detailsHidden: false,
  refreshMs: 15000,
  manifestViewKey: "",
  selectedLogKey: "",
  refreshInFlight: false,
};

const els = {
  machines: document.getElementById("machines"),
  generated: document.getElementById("generated"),
  runningCount: document.getElementById("runningCount"),
  failedCount: document.getElementById("failedCount"),
  okCount: document.getElementById("okCount"),
  selectedTitle: document.getElementById("selectedTitle"),
  selectedMeta: document.getElementById("selectedMeta"),
  logOutput: document.getElementById("logOutput"),
  layout: document.querySelector(".layout"),
  details: document.querySelector(".details"),
  toggleDetailsButton: document.getElementById("toggleDetailsButton"),
  refreshButton: document.getElementById("refreshButton"),
};

function statusLabel(session) {
  if (session.status === "succeeded") return `exit 0`;
  if (session.status === "failed") return `exit ${session.exit_code}`;
  if (session.status === "running") return "running";
  return "unknown";
}

function statusClass(status) {
  return ["running", "failed", "succeeded"].includes(status) ? status : "unknown";
}

function progressLabel(progress) {
  if (!progress || !Number.isFinite(progress.percent)) return "";
  const percent = Math.max(0, Math.min(100, progress.percent));
  // Flooring keeps incomplete work below 100% even near completion.
  const shown = Math.floor(percent * 10) / 10;
  const count = progress.unit === "bytes"
    ? `${(progress.completed / 1e9).toFixed(2)} / ${(progress.total / 1e9).toFixed(2)} GB`
    : `${progress.completed} / ${progress.total} ${progress.unit || "items"}`;
  return `${progress.label || "Progress"}${progress.scope === "phase" ? " (phase)" : ""}: ${shown.toFixed(1)}% · ${count}`;
}

function progressHtml(progress) {
  const label = progressLabel(progress);
  if (!label) return "";
  const percent = Math.max(0, Math.min(100, progress.percent));
  return `<span class="taskProgress"><small>${escapeHtml(label)}</small><progress max="100" value="${percent}" aria-label="${escapeHtml(label)}"></progress></span>`;
}

function shortCommand(command) {
  if (!command) return "command unavailable";
  return command.length > 130 ? `${command.slice(0, 127)}...` : command;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function allSessions(manifest) {
  return (manifest?.machines || []).flatMap((machine) =>
    (machine.sessions || []).map((session) => ({ ...session, host: session.host || machine.host }))
  );
}

function updatedAt(session) {
  return String(session?.updated_at || session?.started_at || "");
}

function newestSession(machine) {
  return [...(machine?.sessions || [])].sort((a, b) =>
    updatedAt(b).localeCompare(updatedAt(a))
  )[0];
}

function machineSortKey(machine) {
  const hasRunning = (machine?.sessions || []).some((session) => session.status === "running");
  return { hasRunning, updatedAt: updatedAt(newestSession(machine)) };
}

async function fetchManifest() {
  const response = await fetch(`/dashboard/manifest.json?ts=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`manifest fetch failed: ${response.status}`);
  return response.json();
}

async function fetchLog(session) {
  if (!session?.log_url) return "";
  const response = await fetch(`/${session.log_url}?ts=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`log fetch failed: ${response.status}`);
  return response.text();
}

function sessionIdentity(session) {
  return `${session?.host || ""}/${session?.safe_session || ""}`;
}

function sessionLogKey(session) {
  return [
    sessionIdentity(session),
    session?.log_url || "",
    session?.updated_at || "",
    session?.bytes_published || 0,
    session?.status || "",
    session?.exit_code ?? "",
  ].join("|");
}

function manifestViewKey(manifest) {
  const machines = (manifest?.machines || []).map((machine) => ({
    host: machine.host,
    totals: machine.totals || {},
    sessions: (machine.sessions || []).map((session) => ({
      session: session.session,
      safe_session: session.safe_session,
      host: session.host || machine.host,
      status: session.status,
      exit_code: session.exit_code,
      command: session.command,
      cwd: session.cwd,
      started_at: session.started_at,
      updated_at: session.updated_at,
      finished_at: session.finished_at,
      log_url: session.log_url,
      bytes_published: session.bytes_published,
      progress: session.progress,
    })),
  }));
  return JSON.stringify({ totals: manifest?.totals || {}, machines });
}

function updateSummary(manifest) {
  const totals = manifest.totals || {};
  els.runningCount.textContent = totals.running || 0;
  els.failedCount.textContent = totals.failed || 0;
  els.okCount.textContent = totals.succeeded || 0;
  els.generated.textContent = manifest.generated_at
    ? `Updated ${formatTime(manifest.generated_at)}`
    : "Feed loaded";
}

function renderManifest(manifest) {
  updateSummary(manifest);
  els.machines.replaceChildren();
  const machines = [...(manifest.machines || [])].sort((a, b) => {
    const left = machineSortKey(a);
    const right = machineSortKey(b);
    if (left.hasRunning !== right.hasRunning) return right.hasRunning - left.hasRunning;
    return right.updatedAt.localeCompare(left.updatedAt);
  });
  if (machines.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No machines have published nom output yet.";
    els.machines.append(empty);
    return;
  }

  for (const machine of machines) {
    const section = document.createElement("section");
    section.className = "machine";

    const heading = document.createElement("div");
    heading.className = "machineHeading";
    heading.innerHTML = `<h2>${escapeHtml(machine.host)}</h2><span>${machine.sessions?.length || 0}${machine.total_sessions > (machine.sessions?.length || 0) ? ` / ${machine.total_sessions}` : ""} runs</span>`;
    section.append(heading);

    const sessions = [...(machine.sessions || [])].sort((a, b) =>
      updatedAt(b).localeCompare(updatedAt(a))
    );
    for (const session of sessions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `session ${statusClass(session.status)}`;
      if (state.selected?.host === machine.host && state.selected?.safe_session === session.safe_session) {
        button.classList.add("selected");
      }
      button.innerHTML = `
        <span class="statusDot"></span>
        <span class="sessionMain">
          <strong>${escapeHtml(session.session)}</strong>
          <small>${escapeHtml(shortCommand(session.command))}</small>
          ${progressHtml(session.progress)}
        </span>
        <span class="sessionSide">
          <span>${escapeHtml(statusLabel(session))}</span>
          <time>${escapeHtml(formatTime(session.updated_at))}</time>
        </span>
      `;
      button.addEventListener("click", () => selectSession({ ...session, host: machine.host }));
      section.append(button);
    }

    els.machines.append(section);
  }
}

async function updateSelectedLog(session, { showLoading = false, force = false } = {}) {
  const nextLogKey = sessionLogKey(session);
  if (!force && nextLogKey === state.selectedLogKey) return;
  if (showLoading) els.logOutput.textContent = "Loading nom output...";
  state.selectedLogKey = nextLogKey;
  try {
    const text = await fetchLog(session);
    els.logOutput.textContent = text || "No log output published yet.";
  } catch (error) {
    els.logOutput.textContent = error.message;
  }
}

async function selectSession(session, { showLoading = true, forceLog = true } = {}) {
  const previousIdentity = sessionIdentity(state.selected);
  state.selected = session;
  els.selectedTitle.textContent = `${session.host} / ${session.session}`;
  els.selectedMeta.textContent = `${statusLabel(session)} | ${session.cwd || "cwd unavailable"}${progressLabel(session.progress) ? ` | ${progressLabel(session.progress)}` : ""}`;
  if (sessionIdentity(session) !== previousIdentity) {
    renderManifest(state.manifest);
  }
  await updateSelectedLog(session, { showLoading, force: forceLog });
}

async function refresh({ force = false } = {}) {
  if (state.refreshInFlight) return;
  state.refreshInFlight = true;
  els.refreshButton.disabled = true;
  try {
    const manifest = await fetchManifest();
    state.manifest = manifest;
    const sessions = allSessions(manifest);
    updateSummary(manifest);
    const nextViewKey = manifestViewKey(manifest);
    if (force || nextViewKey !== state.manifestViewKey) {
      state.manifestViewKey = nextViewKey;
      renderManifest(manifest);
    }
    if (state.selected) {
      const updated = sessions.find(
        (session) =>
          session.host === state.selected.host &&
          session.safe_session === state.selected.safe_session
      );
      if (updated) {
        await selectSession(updated, { showLoading: false, forceLog: force });
      }
    } else {
      const newest = [...sessions].sort((a, b) => updatedAt(b).localeCompare(updatedAt(a)));
      const running = newest.find((session) => session.status === "running");
      const initial = running || newest[0];
      if (initial) await selectSession(initial, { showLoading: true, forceLog: true });
    }
  } catch (error) {
    els.generated.textContent = error.message;
  } finally {
    els.refreshButton.disabled = false;
    state.refreshInFlight = false;
  }
}

els.refreshButton.addEventListener("click", () => refresh({ force: true }));
els.toggleDetailsButton.addEventListener("click", () => {
  state.detailsHidden = !state.detailsHidden;
  els.details.hidden = state.detailsHidden;
  els.layout.classList.toggle("detailsHidden", state.detailsHidden);
  els.toggleDetailsButton.textContent = state.detailsHidden ? "Show log" : "Hide log";
});
refresh();
setInterval(refresh, state.refreshMs);
