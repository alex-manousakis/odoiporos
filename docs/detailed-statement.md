# Detailed employee period statement

Menu: Μετακινήσεις > Εκτ. Αναλυτικής Κατάστασης. Requires the existing travel View
and Print rights. Employee and optional department choices follow employee_scope;
the current user's linked employee and active head signatory are preselected.
The period must be defined in Περίοδοι. Preview opens a PDF suitable for browser
printing; Export downloads it. Neither action marks a trip paid or closes a period.

The layout follows analytiki_katastasi.pdf: chronological trip rows, purpose, days
inside/outside headquarters, domestic/foreign factors, tickets, private-car distance
and reimbursement, accommodation, other costs, general totals, deductions and the
signature section. Dates use dd/mm/yyyy and amounts Greek number formatting.

Rules ported from PrintKartelaP.pas / PrintKartelaP.dfm:
- Select trips by departure date within the inclusive period, not by overlap.
- Sum each trip's selected calculation once; never every revision.
- Apply MTPY/GEOTEE only when both employee and period flags permit it.
- Deduction base is domestic + foreign daily allowance, not overall expenses.
- Percentages come from application parameters; positive amounts round half-up
  to cents, matching SQL Server ROUND in the Delphi query.

The new nullable Employee.has_mtpy/has_geotee flags distinguish unknown from No.
Unknown flags block a report only when the period enables the corresponding deduction.
They are editable in employee management. import_employee_payment_flags --apply
fills only unknown flags from legacy USR HASMTPY/HASGEOTEE, preserving configured
web values. Import is restricted to TRAVEL_WEB_DEV and never writes to TRAVEL.

Each trip uses its settlement-linked calculation, otherwise its latest frozen actual
calculation, otherwise its latest fresh estimate. A trip settled in another period,
a missing calculation or a stale estimate causes an error; it is never silently omitted.
The archived source records whether estimates/accounting adjustments were used.
The print screen explains this basis; the PDF does not display a provisional notice. This is not a substitute for a future actual-cost approval
and payment workflow. Rates and eligibility are read from calculation snapshots.
Daily factors are effective daily allowance divided by the applicable captured band-1
rate; absent/ambiguous denominators cause an error. Unknown data is not guessed.
Accounting total overrides that differ from component sums are shown as a separate
reconciliation amount in the summary.

DetailedStatement archives PDF bytes, SHA-256, employee/period/signatory identifiers,
print date, author and complete source totals, calculation IDs/revisions, rates and
deduction flags. Previously generated PDFs are served unchanged. Downloads require
current print rights and employee scope and use private/no-store. Archive creation
and downloads are audited. These archives contain AFM/IBAN and are subject to the
organization's documented personal-data and financial-record retention policy.

Validation: core.test_detailed_statement covers totals/deductions, flags, period
boundaries, duplicate calculation revisions, scope, freshness, accounting reconciliation,
archived/private downloads and long-report pagination. A seven-trip layout was also
rendered and compared with the supplied three-page example.
