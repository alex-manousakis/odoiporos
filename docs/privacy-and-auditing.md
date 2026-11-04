# Personal data accountability

## Implemented audit coverage

Delphi GlobalP.pas SaveActivity writes RECORDID, ACTION, COMMENTS, MODULE, USR,
COMPANY and ACTIVITYDATE to ACTIVITY. The web app uses a separate core_auditevent
table; old ACTIVITY records remain in TRAVEL and have not been imported or rewritten.

The web application records request UUID, actor ID and username at the time,
timestamp, route name (never URL query), action, target model/ID, changed field
names and response status. No old/new field values, passwords, submitted login
names, request bodies, IP addresses or document contents are copied into logs.

Request-scoped ORM loads of personal-data models are recorded, including related
employees, calculations, declarations and permission records. This is deliberately
a superset of displayed records: internal authorization lookups can also appear.
An event means server access while processing a request, not proof a person read
the screen. HTTP status distinguishes successful and rejected requests. Download
means the server served a file, not proof of physical printing. All linked events
share a request UUID. Authentication, model creates/updates/deletes and permission
membership changes are logged. Non-HTTP model writes show a system actor.

Only superusers may open Parameters > Activity. No edit/delete interface or admin
registration exists. Audit views themselves are logged. Responses on core/admin
and authentication pages use private/no-store. Logs fail closed: logging failure
prevents returning the response; monitor server errors and database availability.

## Important limits and deployment requirements

This is an accountability feature, NOT a certification of GDPR compliance.
Raw SQL, QuerySet.update/bulk operations, values()/values_list() reads, direct SQL
Server access, scripts outside Django and static/media files served directly by
the web server bypass model-level audit hooks. Do not expose media directly; use
the protected download view. Enable separate SQL Server auditing for database
administrators and direct access. Request events still identify each core/admin
endpoint even when a projection query does not instantiate model objects.

Audit rows are protected by application interfaces, not cryptographically immutable.
Restrict production database credentials and administrator access; export logs to
separately controlled, access-restricted storage for tamper resistance and monitoring.
The app DB account should not have UPDATE/DELETE rights on core_auditevent; deploy
migrations with a separate privileged account. Review FK SET_NULL behavior before
deleting user accounts with this restriction; prefer deactivating user accounts.

The controller/DPO must determine and document lawful basis, purposes, staff privacy
notice, retention of personnel/travel/document/audit data, subject-rights procedures,
backup retention, processor contracts, incident/breach response and whether a DPIA
is necessary. No retention interval is invented and no automatic deletion enabled.
Agree a retention schedule and controlled archival/purge procedure with the DPO.
Logs themselves contain personal data and need the same safeguards.

Use named accounts, review department scopes and permissions (including legacy
accounts lacking UserAccess), deactivate leavers, use HTTPS and secure session/CSRF
cookies in production, turn DEBUG off, protect backups and SQL connections, patch
dependencies, restrict Django admin and consider MFA. Existing development settings
are not a production security configuration. Shared administrator accounts prevent
reliable attribution. Review historical archived PDFs separately for retention.

Sources:
- https://www.edpb.europa.eu/sme/be-compliant/secure-personal-data_en
- https://www.edpb.europa.eu/sme/be-compliant/be-compliant_en
- https://www.enisa.europa.eu/sites/default/files/publications/WP2016%203-2%206%20Data%20Controllers%20Risk.pdf

## Verification and operational review

Run `python manage.py test core.test_audit`. Test coverage includes attributed
employee reads, secret-free change events, transactional rollback, append-only ORM
guards, restricted/self-audited viewing, failed logins, password/permission changes,
CSRF rejection and fail-closed audit failure. Existing core workflows are also tested.

In production, alert on failed authentication, repeated denied access, unexpected
bulk access and logging failures. Assign a person to review the activity log; logging
without review does not detect misuse. Establish monitoring outside the same database.
An audit failure blocks the HTTP response, but cannot undo already committed writes
outside an explicit transaction; the existing transactional editor flows keep their
model mutation and signal-generated events together. Streaming files are audited
when the response is authorized, before transfer completes.
