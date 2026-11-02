# Desktop search

The taskbar magnifier beside Start and Super+S open Search. Application Center remains a separate app grid available through its taskbar button and Start's All Apps action. Super+A and Super+Space open Application Center in the packaged bindings. Existing custom keyboard bindings remain user choices.

Search uses the existing application, settings, action, calculator and configured web-search providers. Local file results are added without uploading file contents. Press Up/Down to select, Enter to open, and Escape to close. Web search opens the configured search engine in the default browser only when selected.

Local files are searched by filename under Desktop, Documents, Downloads, Pictures, Music and Videos. Small plain-text documents also match their contents. Each request is limited to one second, 30,000 entries and eight results. Hidden paths, symlinks and build/dependency directories are excluded. This fallback complements the persistent content index described below. Large collections may return only the files visited within the fallback budget. Translated XDG folder names, semantic image search, calendar/notes integration, Huawei cloud files and AI summaries remain separate work.

## Reference and scope

Huawei's [PC search guide](https://consumer.huawei.com/cn/support/content/zh-cn16045813/) describes 小艺搜索 (Celia Search) as a separate lower-left entry with Harmony+S, local applications and settings, file search, online search and document actions. Its [search scope](https://consumer.huawei.com/cn/support/content/zh-cn16045816/) includes proprietary semantic and cloud capabilities. These official pages were checked on 2 November 2026. HP-OS implements the local Linux search workflow above; it does not claim complete equivalence with those Huawei services.

## Indexed document content and OCR

HP-OS also packages Recoll with its PDF and Office extractors and Tesseract with
English and Simplified Chinese data. The index starts 30 seconds after Search's
service loads and updates every 30 minutes while HP-OS runs. It runs at low CPU
priority with one extraction thread, a 30-second per-document extraction limit,
and a 15-minute job limit. OCR results are cached. Typing queries the existing
index with a 1.5-second timeout; it never starts extraction.

The first index configuration includes existing Desktop, Documents, Downloads,
Pictures, Music and Videos directories directly under the user's home. Hidden
folders and symlinks are skipped. Configuration, index, OCR cache, latest log and
status live in `$XDG_STATE_HOME/hp-os/search` (default `~/.local/state/hp-os/search`).
Edit `recoll.conf` there to change `topdirs`; new directories created after initial
configuration need to be added. `.recoll-noindex` excludes a folder. An empty
initial folder set uses a private empty folder, so Recoll never defaults to
indexing the entire home directory.

Use `hp-os-search --index` for a manual incremental update, and
`hp-os-search --status` for state and timestamps. Search shows the latest status
beside “Search indexed documents.” That action opens Recoll's full result and
preview window with the query. This also exposes configured folders through
Recoll's indexing preferences. A partial or interrupted index retains earlier
results and retries at the next interval. Errors are available in `index.log`.

PDF text, Word, PowerPoint and Excel contents are indexed using Recoll's bundled
extractors. PNG, JPEG and TIFF OCR and wholly textless PDF OCR use Tesseract.
Mixed PDFs with some embedded text keep normal text extraction by default.
Password-protected documents, unsupported formats and documents that exceed the
extraction timeout may have only a filename result. The direct filename/plaintext
fallback remains available while the first index is being built.

Semantic descriptions such as “photos of a beach” remain a separate extension.
Recoll's semantic branch is experimental. A production local semantic provider
could use Sentence Transformers with a pinned, licensed model and an explicit
resource budget, returning the same `name`, `path`, and `url` result schema.
Cloud calendars, Huawei cloud data and AI summaries require separate provider
integrations. No document content is sent to a cloud service by this backend.

References: [Recoll OCR](https://recoll.org/usermanual/webhelp/docs/RCL.INDEXING.OCR.html),
[Recoll semantic search](https://recoll.org/pages/recoll-semantic.html).

## Local Qwen

“Ask Qwen to search” is an explicit action in Search. It sends only the typed
query to the configured loopback chat service, requests keyword synonyms or
translations, and retrieves matching local indexed documents. The panel stays
open and shows busy, completed or unavailable status. This is query expansion,
not image embeddings or document question answering. Normal typing does not
contact a model or start a server.

The default endpoint is `http://127.0.0.1:30002/v1` (the dedicated small search model).
`HP_OS_SEARCH_AI_URL` can select another loopback HTTP endpoint and
`HP_OS_SEARCH_AI_MODEL` can select its model. Otherwise `/models` supplies the
first available model. Remote URLs are rejected. Model discovery waits at most
one second and completion at most 20 seconds; unavailable services retain
keyword results. The search UI downloads no model weights. The optional host service supplies
the small model; keyword search works when that service is absent or unavailable.
