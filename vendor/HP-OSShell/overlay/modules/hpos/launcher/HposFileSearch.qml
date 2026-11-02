pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root
    property string query: ""
    property string completedQuery: ""
    property var matches: []
    property string smartStatus: "Expand this query using the existing local model"
    property string indexStatus: "not indexed"
    readonly property var results: query.length > 0 && completedQuery === query ? matches : []
    function refresh() {
        if (!query.length || worker.running) return
        worker.requestedQuery = query
        worker.command = ["hp-os-search", "--query", query]
        worker.running = true
    }
    function smartSearch() {
        if (!query.length || smartWorker.running) return
        settle.stop()
        smartStatus = "Searching with local IQ…"
        smartWorker.command = ["hp-os-search", "--smart", query]
        smartWorker.running = true
    }
    onQueryChanged: {
        smartStatus = "Expand this query using the existing local model"
        matches = []
        settle.restart()
    }
    // Incremental indexing is independent of typing and serialized across screens.
    Timer { interval: 30000; running: true; onTriggered: indexer.running = true }
    Timer { interval: 1800000; running: true; repeat: true; onTriggered: { if (!indexer.running) indexer.running = true } }
    Process { id: indexer; command: ["hp-os-search", "--index"] }
    Timer { id: settle; interval: 120; onTriggered: root.refresh() }
    Process {
        id: smartWorker
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const response = JSON.parse(text)
                    if (response.query === root.query) {
                        root.completedQuery = response.query
                        root.matches = response.results
                        root.smartStatus = response.smartStatus
                    }
                } catch (_) { root.smartStatus = "Local IQ unavailable" }
            }
        }
    }
    Process {
        id: worker
        property string requestedQuery: ""
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const response = JSON.parse(text)
                    if (response.query === root.query) {
                        root.completedQuery = response.query
                        root.matches = response.results
                        root.indexStatus = response.status?.state ?? "unknown"
                        if (response.smartStatus) root.smartStatus = response.smartStatus
                    }
                } catch (_) { root.matches = [] }
            }
        }
        onExited: { if (requestedQuery !== root.query) root.refresh() }
    }
}
