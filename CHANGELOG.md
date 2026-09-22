# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.7.4] — Unreleased ( Expected : 2026-06-10 )

### Changed

- `Readme.md` updated with Competitor Matrix.
- updated internal `page` & `wapisession` to be mandatory for cleaner visibility.

### Security

- Fixed JavaScript injection in `WAJS_Scripts`. Caller-supplied identifiers (`chat_id`,
  `contact_id`, `group_id`, `invite_code`, `newsletter_id`, `label_id`, `community_id`,
  `call_id`, `msg_id`, `theme`, `value`) were spliced into single-quoted JS string
  literals, so a crafted JID containing a single quote could close the literal early and
  execute arbitrary JS inside the authenticated WhatsApp Web context. All 65 call sites
  now embed values via `json.dumps()`. Regression tests added in
  `tests/unit/WhatsApp/test_wajs_scripts.py`.
- Hardened media file writes against path traversal. `WapiWrapper._save_bytes()` now
  resolves its destination and refuses any path that escapes a configured `media_root`,
  raising `ValueError` before any directory is created. The `media_root` argument is
  optional and validated on construction, so existing callers are unaffected.
- `WapiWrapper.media_save_path()` now neutralises path separators in the
  attacker-influenced `id_serialized` and `type` fields of a `MsgModel` dump. A crafted
  `type` such as `../../../etc/cron.d/x` previously produced a traversing filename.
  Filenames generated from ordinary identifiers are unchanged.
- The WhatsApp pairing code is no longer written to INFO-level logs in the clear. It is a
  one-time credential that links a device to the account, so INFO now records a redacted
  form (`AB*****`) and the full code is emitted at DEBUG only. Headless/Docker setups that
  cannot scan a QR code should enable DEBUG logging to read the code; the Docker startup
  hint was updated to say so.

---

## [0.7.3] — 2026-05-03

### Added

- Added `Agent.md` for agents.
- added on_encrypt hook in the `RegisteryConfig()` , it now encrypts the messages at runtime.
- added storage/query.py , it contains all the queries for the database , additionally adding much flexible queries to fetch data.
- added min_insert_time in the enqueue_insert method as kwargs param , can set the flush interval via this too.
- Added `flush()` method to `SQLAlchemyStorage` for manual and immediate batch insertion.
- Improved `SQLAlchemyStorage` background writer with adaptive timeout calculation to guarantee exact flush intervals.
- Enhanced `SQLAlchemyStorage` shutdown logic (`close_db`) to instantly stop the background loop via sentinels without data loss.
- Added smoke test script for JS synthetic clicks vs Camoufox physical humanized clicks.
- Added `mentionList` parameter support to send mentions via `send_api_text()`.
- fallback check for newsletter/channels in open_chat()
- Added storage decorator @on_storage inside @on_newMsg decorator , added RegistryConfig to handle these inside @on_newMsg.

### Fixed

- test/E2E/ scripts fixed with new changes.
- fixed `WapiSession` to have `page` based registery.
- fixed `login` to have profile based login to stop redundant calls or same profile and browser but diff page call to whatsapp.
- Added vairable `key_typing` in `send_api_text()` method to enable or disable key-typing.This fixes the issue of 0 keyup/keydown events.
- Fixed `open_chat()` reliability under heavy load using enhanced retry logic, mouse micro-corrections, and virtualized `scrollIntoView` (fully supports headless/Xvfb).
- Hardened API stealth engine bridge execution, enhanced _evaluate_stealth with success , error dict, and some tweaks.
- SqlalchmeyStorage is now uses new ProfileManager Structure , and dialect can be changed with db_credendials and much more control over database.
- scripts added and fixed in order to test new Hooks.
- smoke test script added in order to test new hooks.
- on_newMsg now adds RegistryConfig which can handle these inside `@on_newMsg` and `RegistryConfig` can fetch the storage.
- giving profile in the Registry now send msg to be automatically to be in storage saved.

### Changed

- FileTyped is added in native now , no more core dependency
- `test/E2E/script_msgEvent.py` updated with latest hooks and code.

---

## [0.7.2] — 2026-04-18

### Fixed
- Fixed Quick Start code example in README.

## [0.7.1] — 2026-04-15

### Fixed
- Updated README documentation.

---

## [0.7.0] — 2026-04-15

This release marks the extraction of the WhatsApp plugin from the original CamouChat monorepo into a standalone, independently versioned package.

### Added

- **Plugin Independence**: Extracted from the CamouChat monorepo into a standalone `camouchat-whatsapp` package.
- **RAM-Level Bridge**: Implemented a comprehensive internal JavaScript bridge (`WapiSession`, `WapiWrapper`) for real-time access to messages, chats, contacts, and privacy state — eliminating all DOM scraping.
- **Stealth Engine**: Hardened the bridge with non-enumerable, randomly-keyed property handles to resist WhatsApp integrity scanner enumeration.
- **Media Extraction Pipeline**: Introduced `MediaController.save_media` with automatic type-based categorisation (image, video, audio, document, sticker) and local-first retrieval prioritising the browser LRU cache over CDN calls.
- **Message Event Hook**: Added the `@on_newMsg` decorator for zero-latency, asynchronous interception of incoming WhatsApp messages.
- **Extended Data Models**: Expanded `ChatModelAPI` and `MessageModelAPI` to achieve full schema parity with internal WhatsApp structures.
- **Unified Boolean Direction**: Introduced type-safe `fromMe` boolean across all models and storage layers, replacing legacy string-based `direction` literals.
- **Normalized Attribute Schema**: Standardized `Chat` and `Message` models with `id_serialized`, `name`, and `ui` fields for cross-platform consistency.
- **Contextual Reply**: Integrated `WapiSession` into `InteractionController`, enabling precise message quoting via DOM-focus fallback and scroll-to-message support.
- **Bridge API Parity**: Added `mark_is_composing` and `decrypt_media` methods to the `WAJS_Scripts` layer, completing the internal API surface.
- **License Compliance**: Added `NOTICE` file with correct Apache 2.0 attribution for the bundled `wa-js` integration.
- **Documentation**: Created `docs/` with dedicated guides for `wa_js`, `api_models`, `controllers`, and `storage`.

### Changed

- **Storage Architecture**: Refactored `SQLAlchemyStorage` into a normalized ingestion pipeline supporting both Browser (DOM) and API (RAM) message sources.
- **Type-Safe Filtering**: Rebuilt `MessageFilter` to use `id_serialized` for deterministic message identification and deduplication.
- **Media API Contract**: Unified the `extract_media` return schema across `WapiWrapper`, `MessageApiManager`, and `MediaController`.
- **Binary Serialisation**: Improved `Uint8Array`-to-base64 handling for reliable `mediaKey` and media metadata extraction.
- **README**: Rewrote with professional installation guide, Security & Usage policy, WA-JS acknowledgements, and full docs links.
- **pyproject.toml**: Expanded keywords and classifiers for improved PyPI SEO.

### Fixed

- **Static Analysis**: Resolved all Mypy type errors via protocol stubs, strict assertions, and corrected Liskov substitution violations.
- **Unit Test Parity**: Restored 100% pass rate across the full test suite.
- **Manager Instantiation**: Fixed critical initialization bug in `WapiSession` ensuring all API managers receive required page references.
- **Unit Tests**: Corrected `InteractionController` test suite to reflect method renames from the `quote_only` API refactor.

### Removed

- **Diagnostic Verbosity**: Stripped redundant media debug output from `MessageModelAPI.__str__`.
- **Legacy Scraping Layer**: Removed the monolithic `ChatProcessor` DOM scraper.
- **Deprecated Attrs**: Eliminated `chat_name`, `chat_ui`, and `direction` string references.

---

## [0.6.1] — 2026-03-20

### Added

- **Documentation**: Refined all files in the `docs/` directory for improved clarity and structural consistency.

### Fixed

- **README**: Addressed minor content inaccuracies and formatting inconsistencies.

---

## [0.6.0] — 2026-03-20

### Added

- **WA-JS Integration**: First integration of the `wa-js` bridge for internal WhatsApp Web API access.
- **Encrypted Storage**: AES-GCM-256 encryption for all locally persisted messages.
- **Multi-Account Support**: Isolated profiles across Linux, macOS, and Windows.
- **Database Abstraction**: SQLAlchemy-backed storage with SQLite, PostgreSQL, and MySQL support.
- **Humanised Interaction**: Keyboard telemetry and timing simulation to reduce detection risk.

### Changed

- **Architecture**: Transitioned to an interface-driven design pattern.
- **Test Coverage**: Raised automated test coverage to ≥ 76%.

---

## [0.1.5] — 2026-02-01

Final release in the 0.1.x series prior to the 0.6.0 core infrastructure overhaul.
