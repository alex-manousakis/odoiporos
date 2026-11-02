# Domain design - first draft

Status: models are a design draft; no new database or core migrations have been created.

## Inventory

27 tables including sysdiagrams; 268 columns.

| Legacy table | Columns |
|---|---:|
| ACTIVITY | 9 |
| BRANCH | 10 |
| CATEGORY | 4 |
| DAILYCOMPENSATION | 10 |
| DEPARTMENT | 6 |
| GENDER | 5 |
| HOTELCOST | 10 |
| KMALLOWANCE | 4 |
| MODULE | 6 |
| OVERNIGHTLINES | 13 |
| OVERNIGHTPLACE | 6 |
| PARAMS | 26 |
| PERIOD | 10 |
| POSITION | 4 |
| REASON | 3 |
| REPORTNAME | 2 |
| REPORTSCRIPT | 4 |
| ROUTE | 17 |
| SIGNATURE | 4 |
| SPECIALITY | 3 |
| STATUS | 2 |
| TRANSPORT | 6 |
| TRAVEL | 40 |
| TRAVELLINES | 12 |
| USERRIGHT | 8 |
| USR | 39 |
| sysdiagrams | 5 |

## Model mapping

- USR -> Employee plus optional Django user; only ISEMPLOYEE records become employees. Non-employee logins remain users. Never import PASSWORD into Django authentication; provision/reset credentials.
- CATEGORY, DEPARTMENT, SPECIALITY, POSITION -> named reference models.
- TRANSPORT, OVERNIGHTPLACE -> TransportMode, AccommodationType.
- ROUTE -> Route + ordered RouteStop. Delphi splits destination flags on hyphens (TravelP.pas:1498); preserve per-stop position and reject mismatched lists.
- DAILYCOMPENSATION, HOTELCOST, KMALLOWANCE -> effective-dated rate models, preserving legacy IDs.
- TRAVEL -> Travel + separate estimate/actual CalculationSnapshot revisions.
- TRAVELLINES -> TravelLeg; OVERNIGHTLINES -> OvernightStay. COST is not automatically both estimate and actual: import classification depends on legacy workflow state.
- STATUS, REASON -> TravelStatus, TravelReason. Do not invent a paid status or reinterpret existing codes.
- PERIOD -> future settlement batch; assess period/report filters before modeling.
- PARAMS -> future versioned policy and organization settings; do not discard distance thresholds, budget uplift/minimum or rounding settings.
- SIGNATURE, REPORTNAME, REPORTSCRIPT -> future signatories and versioned document templates.
- ACTIVITY -> preserve legacy audit, plus future web audit events.
- USERRIGHT, MODULE -> explicit mapping to Django groups/permissions, not direct password/permission copying.
- BRANCH -> organization scope to review before import.
- GENDER -> retain grammatical forms needed by Greek documents; final model pending document analysis.
- sysdiagrams -> excluded from application migration.

## Observed Delphi calculations (behavior, not legal validation)

Source: TravelP.pas:2686-2975 and :4187-4201.

- Daily allowance uses work dates; departure before work adds at most the previous day. Return on the next day affects the one-day allowance branch.
- Allowance eligibility uses total route distance against PARAMS.HOMEDISTANCELIMIT.
- The final located route influences abroad flag, compensation band and daily allowance eligibility. Mixed routes require explicit comparison scenarios.
- Rate selection requires the validity interval to cover the entire allowance date interval; overlapping or missing intervals need explicit errors in the new service.
- Mileage uses a per-travel override when positive, otherwise the latest matching KMALLOWANCE interval. Each leg is rounded before summing.
- Hotel limits depend on employee category, date, abroad, expensive city/island and total distance. Existing code caps the SUM of hotel costs at the SUM of allowed limits, not each night separately.
- Accommodation without cost clears entered cost. Preserve claimed versus reimbursable amounts separately.
- PROGNOSIS stores an initial estimate when finalized (TravelP.pas:3985); actual amounts may subsequently change.
- Approval document budget uses prognosis if positive, otherwise total; applies percentage uplift, optional ceiling to whole euros, then minimum budget.
- Money currently uses Float/Single and RoundTo(...,-2). New calculations use Decimal; half-even versus half-up and float boundary differences must be checked with reference examples.

## Review findings before implementation

- TravelDistancePrivate appears to be accumulated without explicit initialization in calculateOutandOvernightDays. Do not reproduce uninitialized state.
- Some compensation totals are not initialized on every branch; use explicit zero defaults in a pure calculation service.
- ISCANCELED exists on travel lines but the inspected calculation loop does not exclude it. Confirm intended behavior before altering totals.
- Dates imported from SQL datetime need a documented Europe/Athens timezone conversion; do not treat naive timestamps as UTC.
- Legacy foreign keys are incomplete. Validate orphan IDs using aggregate checks before data import; do not silently fabricate references.
- Decimal validators cover application validation; add database nonnegative constraints and cross-date validation in the implementation migration.
- Rate overlap validation, approved snapshot immutability, state transitions and authorization remain to be implemented before exposing write forms.
- No historical trip data, credentials or employee details were imported in this step.

## Database plan

Next: create TRAVEL_WEB_DEV as default SQL Server database after this draft is refined, generate core migrations, then migrate auth/session/core there. Keep travel alias on TRAVEL for read-only comparison. Existing local SQLite is a temporary bootstrap database; it has no migrated business records.

## First acceptance scenarios

Same-day domestic travel; return day after work; private-car multi-leg trip; ticket plus other costs; no-cost accommodation; one hotel night above its individual limit but total below aggregate limit; island/expensive-city conflict; mixed domestic/foreign stops; missing/overlapping rates; historical mileage override; changed rates after approval; cancelled leg; printed budget uplift/ceiling/minimum.

This draft deliberately does not implement a calculation engine until those cases have expected results from Delphi. Financial outputs must not be presented as verified yet.


## Accepted revisions

- Django User and Employee remain separate; ISEMPLOYEE=0 creates no Employee.
- EmployeeCategoryHistory replaces the mutable Employee.category field. Date intervals are inclusive. Travel.applied_category and calculation inputs preserve the category used. Category changes during a trip require accounting review; no automatic policy has been assumed.
- One Route on Travel; TravelLeg removed. TravelExpense holds ticket/mileage/other charges and optional transport. Multiple transport modes are supported without constructing itinerary legs in the form.
- OvernightStay points to a RouteStop, validated against its Travel.route. City/flags remain snapshots for historical use.
- AccommodationReceipt groups only its own covered nights. Total receipt: min(claimed total, sum of limits). Itemized: sum(min(nightly claim, nightly limit)). 100+60 with limits 80+80 gives 160 for a total receipt and 140 for an itemized receipt. No pooling across receipts.
- SettlementPeriod/SettlementItem associate frozen actual calculation revisions with accounting periods. These periods need not be calendar months.

Model clean() validation is not automatically called by save(), bulk updates or raw SQL. Before enabling writes, implement transaction-protected services for category interval changes, receipt reconciliation, snapshot freezing and period closure. Closed-period and frozen-snapshot immutability are NOT yet enforced across all write paths. No database has been created or modified by this design revision.
Legacy TRAVELLINES import will need explicit conversion to expenses and a single route per travel, with ambiguous historical multiple-route records reported for review. Previous mapping sections describe the initial analysis and are superseded by these revisions.


## Database initialization completed

TRAVEL_WEB_DEV is now the default SQL Server database. core/0001_initial and Django built-in migrations have been applied. Earlier statements about no database/migrations describe previous draft stages. Legacy TRAVEL remains unchanged; data import and workflow write services are pending.
