pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root
    property string query: ""
    property string completedQuery: ""
    property var matches: []
    readonly property var results: query.length > 0 && completedQuery === query ? matches : []
    function refresh() {
        if (!query.length || worker.running) return
        worker.requestedQuery = query
        worker.command = ["hp-os-search", query]
        worker.running = true
    }
    onQueryChanged: {
        matches = []
        settle.restart()
    }
    Timer { id: settle; interval: 120; onTriggered: root.refresh() }
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
                    }
                } catch (_) { root.matches = [] }
            }
        }
        onExited: { if (requestedQuery !== root.query) root.refresh() }
    }
}
