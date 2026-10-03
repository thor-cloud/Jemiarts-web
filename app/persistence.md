# Persistence foundation — checklist item 1

This phase adds backend persistence only. The existing entry page remains unchanged; no public gallery, signup form, checkout, payment QR, products, or administrator interface is supplied.

## Guarantees

- Uses Python's standard-library SQLite directly, not a managed database or the deprecated Reflex ORM.
- Startup initializes the local schema transactionally and idempotently. A singleton settings row is the only seed. Schema version 1 is recorded; unsupported versions fail rather than resetting data. Future schema changes require explicit migrations, not merely changing CREATE TABLE statements.
- Short-lived connections enable foreign keys, a busy timeout, and transactions with rollback. Writes and price reads used to create orders are serialized together. Values use SQL parameters.
- Account passwords use unique random salts and PBKDF2-HMAC-SHA256 with 600,000 iterations. Verification uses constant-time digest comparison. Customer representations exclude password hashes.
- Signup defaults to customer access. Only a phone explicitly designated in the backend environment can acquire administrator status at signup; an absent designation grants no administrator role and malformed designation fails closed. Changing the designation does not silently change existing roles. No first-user promotion occurs.
- Phone numbers are normalized international numbers with explicit country codes. Optional email is stored as an empty string. Nonempty emails and normalized phones are unique.
- All monetary values are integers in paise. Orders retain unit and total price snapshots and text details; later bouquet edits do not change existing orders. Portrait prices must come from trusted server-side pricing logic added in a later phase, never a client-supplied total.
- Settings retain editable background, text, and accent hex colors, brand name, welcome text, biography, hero filename, and contact number. Default palette: ivory #F7F3EC, charcoal #29231E, terracotta #B76D50. Editorial serif headings, clean sans-serif body, and airy spacing remain the design direction for subsequent UI phases.

## Later integration requirements

Call repository methods from backend event handlers. Authenticated actor IDs must originate in a trusted server-side session, never an input, URL, or client-supplied ID. Privileged repository operations already recheck the persisted administrator role. Later authentication must also provide session lifecycle protections, signup/credential rate limiting, and ownership checks at every event boundary. A designated phone match is not proof of phone ownership: before enabling public signup with administrator designation, implement verified phone ownership or a separate trusted administrator onboarding process. This foundation alone does not claim public authentication is production-ready.

Image upload helpers cap reads at 10 MB, accept PNG/JPEG/WebP signatures, generate unpredictable filenames, and save using rx.get_upload_dir(). Save the returned filename only in the database. Frontend public image URLs must be produced with rx.get_upload_url(filename), never assets URLs. Signature checks are not full image decoding or malware scanning. Check require_saved_upload before linking a new file, and clean up orphan files if a database write fails. Repository path validation permits portable filenames without requiring files to exist, allowing restored records and pure database tests.

Portrait reference images and payment proofs are sensitive. Reflex upload URLs are not an authorization mechanism; do not expose these paths in public lists. Before enabling private uploads, provide an authenticated file-serving strategy rather than assuming an unpredictable filename alone provides access control. This phase implements no public upload endpoint or upload UI.

## Local durability and tests

SQLite and uploaded files are local to this app instance. They may disappear on hosted redeployments, container replacement, or ephemeral storage; separate instances do not share them. Back up the SQLite file consistently together with uploaded files, and use durable attached storage before relying on hosted persistence. No remote durability is implied.

The isolated standard-library unit suite is runnable with `python -m unittest app.states.test_store`. It uses temporary SQLite files and covers settings-only initialization, password salts, duplicate accounts, explicit administrator designation, authorization, price snapshots, saved path round trips, rollback, singleton constraints, and persistence across repository instances. Tests are supplied but are not executed by the editing tools.
