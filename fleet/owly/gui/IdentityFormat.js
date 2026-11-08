.pragma library

// Decode local URLs once so spaces, Unicode and literal percent signs survive.
// Remote authorities and NUL bytes cannot identify an importable local folder.
function localPath(url) {
    const value = String(url);
    if (value.indexOf("file:///") !== 0) return "";
    try {
        const path = decodeURIComponent(value.substring(7));
        return path.indexOf("\u0000") >= 0 ? "" : path;
    } catch (e) { return ""; }
}
