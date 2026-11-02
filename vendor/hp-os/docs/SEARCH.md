# Desktop search

The taskbar magnifier beside Start and Super+S open Search. Application Center remains a separate app grid available through its taskbar button and Start's All Apps action. Super+A and Super+Space open Application Center in the packaged bindings. Existing custom keyboard bindings remain user choices.

Search uses the existing application, settings, action, calculator and configured web-search providers. Local file results are added without uploading file contents. Press Up/Down to select, Enter to open, and Escape to close. Web search opens the configured search engine in the default browser only when selected.

Local files are searched by filename under Desktop, Documents, Downloads, Pictures, Music and Videos. Small plain-text documents also match their contents. Each request is limited to one second, 30,000 entries and eight results. Hidden paths, symlinks and build/dependency directories are excluded. This on-demand search has no persistent index. Large collections may return only the files visited within the budget. PDF and Office document content, translated XDG folder names, semantic image search, OCR, calendar/notes integration, Huawei cloud files, document previews and AI summaries are not implemented.

## Reference and scope

Huawei's [PC search guide](https://consumer.huawei.com/cn/support/content/zh-cn16045813/) describes 小艺搜索 (Celia Search) as a separate lower-left entry with Harmony+S, local applications and settings, file search, online search and document actions. Its [search scope](https://consumer.huawei.com/cn/support/content/zh-cn16045816/) includes proprietary semantic and cloud capabilities. These official pages were checked on 2 November 2026. HP-OS implements the local Linux search workflow above; it does not claim complete equivalence with those Huawei services.
