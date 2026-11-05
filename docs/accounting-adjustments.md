# Accounting trips and manual calculations

New trips preselect the active Employee linked to the signed-in Django user.
Accounts without an Employee link choose a scoped employee explicitly.

## Access configuration

In Users and permissions, grant the new “Μετακινήσεις (Λογιστήριο) — χειροκίνητες
προσαρμογές” module View to expose the accounting menu. Add permits the first manual
adjustment; Change permits later changes/restoration. These permissions do not grant
unrestricted employee access. Also grant the usual trip View/Add/Change permissions
and configure the account's employee scope (selected departments or all departments).
Print permission is still required for PDFs. No ordinary user has been automatically
assigned accounting rights. Superusers already have access.

Accounting uses the same filtered list, trip editor and automatic calculation engine.
It can create a trip for any employee within the configured scope. Closed, approved
and frozen trips remain locked. Ordinary employees cannot edit a trip while active
accounting adjustments exist; accounting staff must review further changes.

## Adjustments

Open a trip through Accounting, then “Χειροκίνητες προσαρμογές υπολογισμών”. Each
field shows its automatic result and an optional replacement. Blank means automatic;
0 is a deliberate manual zero. A nonblank reason is mandatory. The financial fields,
calculated days, displayed distance and calculated overnight count may be replaced.
Dates and underlying nightly entries are not rewritten by these overrides. Changes
to days/distance/night count are output adjustments; enter corresponding financial
amounts explicitly. Day overrides on cross-year trips are rejected to avoid ambiguous
allocation between annual balances.

Example: when another organization covers flights and one hotel night, set Tickets
to 0 and Accommodation reimbursement to the amount paid by this organization. Keep
the original claimed cost if it is still the actual receipt amount. Explain the
coverage in Reason. Overall cost and document budget recompute from effective
components unless those fields are also explicitly overridden. Detailed nightly
limits remain the automatic reference and are labelled accordingly on Calculations.

Overrides persist across recalculation and trip edits. Each calculation revision
preserves original automatic values, the effective totals, adjustment reason,
accounting user ID and timestamp. The approval PDF uses the effective budget, days
and overnight count. Prior archived PDFs are unchanged. To restore automatic results,
uncheck “Εφαρμογή χειροκίνητων προσαρμογών” and save with a reason; prior snapshots
remain unchanged. Clearing individual replacement fields restores their automatic
results on the next calculation.

All adjustment endpoints enforce module rights, trip scope and lock state server-side.
Saving an adjustment and calculating its revision occur in one transaction. Failures
leave the previous adjustment intact. Adjustments participate in snapshot freshness
checks and are included in the application audit trail. Normal trip form submissions
cannot write override fields. This currently applies to estimated calculations;
the future actual settlement workflow must deliberately integrate these rules.
