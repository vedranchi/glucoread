---
version: 1
slug: "landing"
primary_target: "landing"
related_targets: ["users/templates/users/auth_base.html"]
---

# Landing page (landing/templates/landing/index.html)

Mode: Persuade. Audience: insulin users deciding whether to start a log. Action: Start tracking for free (register); Log in is secondary.
Constraints: one example day everywhere (avg 7.8, 35.0 U, 165 g / 13.8 BU, 80% in range); no testimonials, logos, or founder letter; zero third-party scripts; warm palette shared with the auth screens only; light and dark both ship. Inspiration (craft bar, not world): linkletter.press.

## Direction contract

THESIS: GlucoRead is the paper glucose diary every insulin user was handed at diagnosis — finally doing the adding-up. It refuses the split hero of phone mockup plus feature-card row.

OWN-WORLD: Clinic-booklet diary paper (warm, faint blue rules, a red margin line), a sage book-cloth cover that owns the ground and the closing back cover, printed headings in a chunky warm serif (Young Serif), body in Atkinson Hyperlegible Next, entries handwritten in biro (Kalam, navy ink). Three inks plus paper: biro navy (glucose), margin red (the only alarm, used for highs), sage (cover and actions). The app's log tones carry over as pencil: insulin in plum, meals in ochre, in-range in leaf green. Hand-drawn circles and ticks as authored SVG strokes.

STORY: A visitor recognises the diary they already keep, sees the same day computed (printed totals row under the biro), sees the pattern down a column across three evenings, trusts the privacy and not-medical-advice page, and starts a log from the back cover, a printed label pasted on the cloth.

FIRST VIEWPORT: The open booklet across one gutter on the sage cloth. Left page: headline "See the pattern, not just the number." at display size, lead, Start tracking for free as a stamped primary button, Log in, meta line. Right page: the example day ruled into Time / Glucose / Insulin / Carbs columns in biro, 21:30's 11.4 circled in red, and a printed totals row labelled "Day" beneath. On phones the right page follows the left.

FORM: The Paper Logbook — IMPECCABLE'S PICK (my #1 grounded candidate; the roll assigned #5, The Kitchen Calendar; user chose the pick). seed:f305cdf1de9bad58. Signature interaction: the unit switch on the "My targets" page is a pair of printed tick boxes — choosing one draws a biro tick and rewrites the values. Motion grammar: ink draws on (stroke-dashoffset) once per section; nothing else animates.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
