# Travel approval PDF

Uses REPORTSCRIPT preamble group 1 / budget group 2 through 18 December 2023; groups 11 / 12 afterward, matching TravelP.pas. Texts are ordered by sort_order then ID. Text is escaped as plain text, not evaluated as markup.

Requires core.print_travel plus travel visibility, optional protocol number/date, employee genitive name, current estimate, configured annual limit, signatory and confirmed prior days. Historical travel totals have not been imported, so prior days are explicitly supplied and archived with the output. The annual limit is checked against those supplied days; this does not independently verify historical usage.

Every generation archives the PDF bytes, checksum, selected text rows, signatory and source fields. Regeneration creates a new archive; old downloads remain unchanged when scripts or employee details change. Generation does not change travel status and does not apply a signature.

Fonts: Windows Arial or Linux DejaVu Sans is detected. Override with APPROVAL_FONT_REGULAR and APPROVAL_FONT_BOLD. Font files are not copied into the repository. Organizational header is editable under application parameters.

Structure follows the supplied egrisimetakinisis.pdf: numbered preamble, decision paragraph, travel table, day balance, budget wording and signature. The supplied EU and ESPA 2021-2027 logos are embedded in each page footer. Digital signatures are not applied. Annual day totals are rows within the itinerary table.
