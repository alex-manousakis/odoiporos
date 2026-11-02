# Odoiporika

Python 3.12 / Django 5.2 / HTMX / SQL Server 2022.

## Start (PowerShell)
```
cd "D:\OneDrive - code It\django\odoiporika"
.\.venv\Scripts\python.exe manage.py runserver
```
Open http://127.0.0.1:8000/ . Business forms are still under development.

## Databases
- default: SQL Server TRAVEL_WEB_DEV. Initial auth, admin, session and core migrations applied.
- travel: existing TRAVEL, mapped by unmanaged legacy models. Application router blocks ORM writes and migrations on this alias, but is not a SQL permission boundary.
- db.sqlite3: retained from bootstrap; no longer used by settings.
Windows authentication is used for both SQL connections. Local development connection options are not production TLS settings.
Reference registers have been imported; no historical trips or passwords were imported. No superuser has been created.

## Commands
```
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test core
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py showmigrations --database default
```
Credentials/settings go in ignored .env; .env.example documents variable names.
See docs/domain-design.md for model design, migration mapping and pending business rules.


## Reference import and first travel form

Reference registers have been imported into TRAVEL_WEB_DEV; no legacy logins/passwords or historical trips were imported.
Import is create-only by legacy_id. Existing entries, categories and route stops are not overwritten on rerun.
Preview: `python manage.py import_registers --category-as-of 2026-11-02`
Apply: add `--apply`. Preview rolls back its transaction. Reports: docs/import-preview.json and docs/import-applied.json (IDs and aggregate counts only).
Category history starts at the explicitly chosen reference date; no earlier history is inferred. Trips outside known history are marked for accounting review.
Legacy destination flags contain padded slots; only destination positions are imported. Foreign multi-stop and legacy FORCHECK routes remain flagged for review.

Create an administrator using `python manage.py createsuperuser`, then visit `/accounts/login/`.
Users with core.add_travel may create for any active employee; ordinary linked employees can create for themselves. core.view_travel grants organization-wide visibility. No existing passwords were copied and no default password was set.
The first form stores employee, single route, travel/work dates, reason, purpose and notes. Costs, accommodation input forms, approval and printing are not implemented yet.
