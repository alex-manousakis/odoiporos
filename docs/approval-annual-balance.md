# Approval defaults and annual days

Configure Parameters > installation year and annual day limit. Enter each employee's
days outside the office before introduction of the application in the employee screen.
The opening balance applies ONLY to the installation year. Exclude trips already
recorded in this application to avoid double counting. No historical balances are guessed.

In Auxiliary files > Signatories, mark one active signatory as the organization head.
This person is preselected; another active signatory can be chosen as deputy.
Remove the previous head flag before assigning a replacement. The management form
serializes edits and rejects multiple or inactive default heads; the print screen
rejects ambiguous defaults. The signature heading comes exclusively from
ApplicationParameters.prosfonisiproistamenou, including when another signer is selected.

Prior days = opening balance for the installation year + days of earlier trips for
the same employee. Trips are ordered by departure date, then primary key for ties.
All current statuses (new, finalized, checked) count; there is currently no cancelled
trip status. Later trips do not count in an earlier trip's approval. Another employee's
trips never count. Cross-year calculation days are allocated to the calendar year.

The number of days follows the existing calculation's allowance_from/allowance_to
interval and eligibility (daily allowance enabled and outside the home-distance limit),
using calculation-time route flags and distance thresholds. It is not recomputed using
new employee categories or new rates. Only the latest estimate per previous trip is
used, not every revision. A missing estimate or changed dates require correction rather
than silently assuming zero. Overlapping trip days are not merged; resolve duplicate
or overlapping trip entries before generating documents.

Current trip days are added once and checked against the annual maximum. Generating
or downloading a PDF never increments a counter. The read-only breakdown is displayed
before printing. Each new ApprovalDocument source stores the installation year, opening
balance, previous trip IDs/calculation IDs and counted days for traceability. Existing
archived PDFs and their source snapshots remain unchanged.

Changes use the existing employee/parameters/signatory management permissions and
audit logging. Review previously generated approvals if historical trips or opening
balances are corrected; existing archived documents are not rewritten automatically.
