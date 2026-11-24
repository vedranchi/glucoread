---
name: GlucoRead
description: See the pattern, not just the number. The public face of GlucoRead as a paper glucose diary that finally does the adding-up.
colors:
  paper: "#f7efdf"
  paper-deep: "#efe4cc"
  surface: "#fbf6ea"
  ink: "#2f241a"
  ink-2: "#5b4b3a"
  ink-3: "#6f5f4c"
  line: "#dccdb0"
  line-soft: "#e8dcc3"
  cloth: "#5a6534"
  cloth-deep: "#4c5629"
  cloth-ink: "#f4ecd8"
  cloth-ink-2: "#e6e0c6"
  sage-action: "#4f5b2a"
  sage-action-hover: "#3f4920"
  sage: "#5d6a33"
  sage-ink: "#fbf6ea"
  biro: "#24357a"
  rule: "#b9c7dd"
  grid: "rgba(36, 53, 122, 0.08)"
  margin-rose: "#d4867a"
  plum: "#7a4580"
  ochre: "#a7610f"
  leaf: "#4a7a2e"
  leaf-soft: "#dde7c9"
  leaf-wash: "#ebf0dd"
  alarm-red: "#b13f28"
  alarm-soft: "#f2d5c9"
  alarm-wash: "#f7e4da"
  error-red: "#a3311f"
  paper-dark: "#241e17"
  surface-dark: "#2b241c"
  ink-dark: "#f0e6d2"
  ink-2-dark: "#cfbfa5"
  ink-3-dark: "#ad9c82"
  cloth-dark: "#2a3019"
  cloth-ink-dark: "#ece3cc"
  sage-action-dark: "#bcc684"
  sage-ink-dark: "#1d2110"
  biro-dark: "#a9b9f2"
  rule-dark: "rgba(169, 185, 242, 0.2)"
  margin-rose-dark: "#a2584c"
  plum-dark: "#d7a2dc"
  ochre-dark: "#e9ad5f"
  leaf-dark: "#a8d083"
  alarm-red-dark: "#f29478"
typography:
  display:
    fontFamily: "Young Serif, Georgia, Times New Roman, serif"
    fontSize: "clamp(2.6rem, 5.4vw, 4.6rem)"
    fontWeight: 400
    lineHeight: 1.03
    letterSpacing: "-0.015em"
  headline:
    fontFamily: "Young Serif, Georgia, Times New Roman, serif"
    fontSize: "clamp(1.9rem, 3.6vw, 2.9rem)"
    fontWeight: 400
    lineHeight: 1.08
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Young Serif, Georgia, Times New Roman, serif"
    fontSize: "1.35rem"
    fontWeight: 400
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8rem"
    fontWeight: 700
    lineHeight: 1.35
  figure:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.98rem"
    fontWeight: 700
    fontFeature: "\"tnum\", \"lnum\""
  hand:
    fontFamily: "Kalam, Segoe Print, Bradley Hand, cursive"
    fontSize: "1.2rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0em"
rounded:
  hairline: "2px"
  page: "3px"
  control: "4px"
spacing:
  page-inline: "clamp(1.35rem, 4.2vw, 4rem)"
  page-top: "clamp(1.75rem, 4.2vw, 4rem)"
  page-bottom: "clamp(2.75rem, 5vw, 4.5rem)"
  section: "clamp(1.75rem, 4vw, 3.25rem)"
  margin-x: "clamp(2.1rem, 4.4vw, 3.6rem)"
  graph-cell: "18px"
components:
  button-stamp:
    backgroundColor: "{colors.sage-action}"
    textColor: "{colors.sage-ink}"
    rounded: "{rounded.control}"
    padding: "0.85rem 1.35rem"
  button-stamp-hover:
    backgroundColor: "{colors.sage-action-hover}"
    textColor: "{colors.sage-ink}"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0.85rem 1.35rem"
  button-paper:
    backgroundColor: "{colors.cloth-ink}"
    textColor: "{colors.cloth-deep}"
    rounded: "{rounded.control}"
    padding: "0.42rem 0.85rem"
  button-cloth:
    backgroundColor: "transparent"
    textColor: "{colors.cloth-ink}"
    rounded: "{rounded.control}"
  spread:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.page}"
    padding: "{spacing.page-inline}"
  cover-label:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.page}"
    width: "640px"
  tick-option:
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    height: "44px"
  tickbox:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.hairline}"
    size: "1.3rem"
  graph-paper:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.hairline}"
  diary-entry:
    textColor: "{colors.biro}"
    typography: "{typography.hand}"
    height: "2.05rem"
  diary-total:
    textColor: "{colors.ink}"
    typography: "{typography.figure}"
---

# Design System: GlucoRead

## Overview

**Creative North Star: "The Paper Logbook"**

GlucoRead's public face is the paper glucose diary every insulin user was handed at diagnosis, laid open on its own sage book-cloth cover, finally doing the adding-up. The ground is cloth; everything a visitor reads sits on a page of diary paper resting on it. Pages carry the booklet's printed furniture: faint blue rules, a double rose margin line, a darkening gutter between facing pages, folio numbers at the foot. Entries are written into that paper in biro; what GlucoRead works out (totals, averages, time in range) is printed beneath them. The contrast between the hand and the print is the product's argument, made visually.

The palette is three inks plus paper. Biro navy writes glucose, plum pencil writes insulin, ochre pencil writes meals, leaf green marks in range, sage cloth binds the book and carries every action, and red is the one alarm. Density is that of a well-kept booklet: generous page margins, tight ruled rows inside them. Depth is physical and shallow, paper lying on cloth, never floating UI. Motion is a pen: ink strokes draw themselves on once, and the rest of the page holds still.

**Scope.** This world governs the whole product: the landing page (`landing/`), the auth screens (sign in, register, password reset, via `users/templates/users/auth_base.html`) and the authenticated app (`main/templates/main/base.html` and everything extending it). The user extended it to the app on 2026-11-24, reversing the 2026-11-23 "landing and auth only" decision. The world is delivered by `main/static/main/css/warm.css`, which redefines theme.css's raw `-l` / `-d` tokens and is loaded once, for every page, by `main/templates/main/_theme_head.html`, straight after theme.css. Never link it from an individual template, and never load theme.css without it. theme.css still carries the token names, the primitives and the original teal values underneath; warm.css overrides those values.

**Key Characteristics:**
- Sage book-cloth ground; every readable block is a sheet of paper on it.
- Handwriting (Kalam, biro) for what a person logs; print for everything GlucoRead computes or says.
- Colour is data: each log type has its own ink, and red means above range.
- Printed booklet furniture: rules, double margin line, gutter, folios, double-ruled totals line.
- One motion: hand-drawn strokes draw on once.
- Light is the diary on a desk by day; dark is the same diary under a lamp at night.

## Colors

A warm paper-and-cloth ground written over in a small set of inks, each ink bound to one kind of data.

### Primary
- **Book-Cloth Sage** (`cloth`, dark `cloth-dark`): the page ground (`body.cloth`), drawn with a fine two-way hairline weave at 3.5% and 5% alpha. The topbar, the closing back cover and the footer print directly onto it in Cover Cream (`cloth-ink`, secondary `cloth-ink-2`).
- **Stamp Sage** (`sage-action`, hover `sage-action-hover`; dark `sage-action-dark` on `sage-ink-dark`): every primary action, the stamp button, the `.text-link` and auth links. Sage acts because the booklet is bound in it and red is spoken for.

### Secondary
- **Biro Navy** (`biro`, dark `biro-dark`): glucose entries, the hand, the trace and points on the graph page, the tick in a tick box, the underline stroke, focus outlines on paper, text selection (22% mix) and the caret. Glucose is biro everywhere (`.t-glucose` is remapped to biro), including the dashboard chart's trend line and area fill, which read `--biro`.
- **Plum Pencil** (`plum`, dark `plum-dark`): insulin entries and the bolus lane. Basal is drawn in Ink Brown 2, matching `.t-neutral`.
- **Ochre Pencil** (`ochre`, dark `ochre-dark`): meal and carb entries and the meal lane.
- **Leaf Green** (`leaf`, soft `leaf-soft`, wash `leaf-wash`; dark `leaf-dark`): in range. The target band on the graph page, the range scale's band, in-range cells, the ticks beside the everyday list, the "80% in range" total.

### Tertiary
- **Alarm Red** (`alarm-red`, soft `alarm-soft`, wash `alarm-wash`; dark `alarm-red-dark`): above range, and nothing else on a diary page. The ring around a high reading, the high value itself (also bolded), the high point on the graph, the dashed focus window and the evening column wash where highs run.
- **Error Red** (`error-red`): form validation and error messages on the auth screens. It is the same alarm family used for the same meaning, "this is wrong".

### Neutral
- **Diary Paper** (`paper`, dark `paper-dark`): every page, the cover label, the auth card. Deeper Paper (`paper-deep`) is the theme switch track.
- **Writing Surface** (`surface`, dark `surface-dark`): what you write into: inputs, tick boxes, the graph paper, the tucked-in app slip.
- **Ink Brown** (`ink` / `ink-2` / `ink-3`, dark variants): headings and totals / body copy and column heads / labels, units, folios, captions and box strokes.
- **Printed Rule Blue** (`rule`, dark `rule-dark`) and **Graph Grid** (`grid`): ruled diary rows and the 18px graph-paper grid.
- **Margin Rose** (`margin-rose`, dark `margin-rose-dark`): the double margin line on ruled pages Ruling only.
- **Paper Line** (`line`, `line-soft`): hairline dividers between printed blocks (column guide rows, notices, the time-in-range title).

### Named Rules
**The One Alarm Rule.** Alarm Red means a reading is above range. On the public surfaces its only other use is a form error. Nothing decorative is red, and a high is never colour alone: it is also circled, bolded, enlarged or labelled "above range" for screen readers.

**The Margin Is Ruling Rule.** Margin Rose is printed ruling, a 1px double line set inside the page. It never colours text, values, fills or states, and it is deliberately lighter and pinker than Alarm Red so the two never read as one.

**The Column Ink Rule.** Each log type writes in its own ink everywhere it appears: glucose biro, insulin plum, meals ochre, in range leaf. A new figure inherits these through the `.t-*` tones; it never picks a fresh hue for a log type.

## Typography

**Display Font:** Young Serif (with Georgia, Times New Roman, serif)
**Body Font:** Atkinson Hyperlegible Next (with ui-sans-serif, system-ui, sans-serif)
**Hand Font:** Kalam 400/700 (with Segoe Print, Bradley Hand, cursive)

**Character:** A chunky, warm printed serif for everything the booklet prints as a heading, a low-vision-legible sans for reading and figures, and a quick biro hand for what the diary's owner wrote in. All three are self-hosted woff2 in `main/static/main/fonts/`, latin and latin-ext subsets, `font-display: swap`.

### Hierarchy
- **Display** (Young Serif 400, clamp(2.6rem, 5.4vw, 4.6rem), 1.03, -0.015em, max 11ch): the hero headline only. The back cover label's headline is a near sibling at clamp(2.2rem, 5vw, 3.6rem), 1.04, max 12ch.
- **Headline** (Young Serif 400, clamp(1.9rem, 3.6vw, 2.9rem), 1.08): one per spread.
- **Title** (Young Serif 400, 1.3 to 1.45rem, 1.2 to 1.25): column guide rows, notices, the targets form title, the auth card heading. Young Serif also sets the strong lede (1.3rem, 1.35), the everyday list (1.25rem), the time-in-range figure (1.9rem), folios (0.82rem) and the brand name (1.3rem).
- **Body** (Atkinson 400, 1.0625rem, 1.65, Ink Brown 2, 44 to 48ch, `text-wrap: pretty`): page copy. Captions drop to 0.88rem in Ink Brown 3.
- **Label** (Atkinson 700, 0.78 to 0.82rem, Ink Brown 3, sentence case): field labels, table column heads with their unit on a second line in 400, total sub-labels.
- **Figure** (Atkinson 700, 0.98rem, tabular lining numerals, Ink Brown): the printed totals row and every value the unit switch rewrites.
- **Hand** (Kalam 400, 1 to 1.6rem, line-height 1, Biro or the column's ink): diary entries, filled-in form lines, margin notes.

### Named Rules
**The Hand Logs, Print Computes Rule.** Kalam is only ever something the diary's owner wrote: a reading, a dose, a meal, a date, their own margin note. Totals, averages, labels, headings, copy and controls are printed. If the visitor has to read it to act, it is print.

**The Lining Figures Rule.** Any number that is computed or can be rewritten by the unit switch uses `tabular-nums lining-nums`, so a value never shifts sideways when it changes.

## Layout

The page is a booklet on cloth. A centred container (max 1160px, gutter clamp(1.25rem, 4vw, 2.5rem), 1rem below 560px) holds a vertical run of **spreads**: two equal pages across one gutter, or one full-width fold-out page. Sections are spaced clamp(1.75rem, 4vw, 3.25rem) apart so cloth shows between spreads; the closer gets clamp(3.5rem, 8vw, 6rem) of cloth around its label.

Pages pad generously (clamp(1.75rem, 4.2vw, 4rem) top, clamp(1.35rem, 4.2vw, 4rem) inline, extra at the foot for the folio). Ruled pages indent their content past the double margin line (margin at clamp(2.1rem, 4.4vw, 3.6rem), content 0.9rem beyond it). Inside a page, rhythm is the ruled row: 2.05rem diary rows, 4.25rem week rows. Full-width pages open with a 7fr / 5fr headline-and-lede head; the column guide runs 5fr / 7fr rows.

**Responsive.** At 960px and below every spread stacks to one column: the gutter shading is removed, the right page follows below a 1px dashed fold line, only the right page keeps its folio, and page heads and guide rows collapse to one column. At 860px the menu becomes a drawer laid over the cloth. Below 700px the graph page shows a scroll hint; the graph holds between 620px and 900px and scrolls sideways in its own box rather than shrinking its labels. At 560px the diary's note column drops, field grids go to one column and buttons in an action row go full width.

## Elevation & Depth

Depth is physical and shallow: sheets of paper lying on cloth. Only objects that are paper lift off the ground; everything on a page is flat and separated by printed rules, never by cards or shadows.

### Shadow Vocabulary
- **Sheet on cloth** (`--shadow-lg`, light `0 1px 2px rgba(35,40,14,0.25), 0 22px 44px -22px rgba(35,40,14,0.6)`): spreads, the cover label, the auth card. Also the stamp button's hover lift.
- **Resting mark** (`--shadow-sm`, light `0 1px 2px rgba(47,36,26,0.12)`): buttons at rest.
- **Tucked slip** (`--shadow-sm` plus `0 14px 28px -18px rgba(47,36,26,0.45)`): the app slip tucked into a page, rotated -1.2deg.
- **Gutter** (a 72px horizontal gradient, brown at 7% / 20% / 7% in light, black at 18% / 45% / 18% in dark): the fold between facing pages, drawn on the left page only.

### Named Rules
**The Paper On Cloth Rule.** If it is not a sheet of paper (a spread, the cover label, the auth card, a tucked slip), it does not cast a shadow. Inside a page, structure comes from rules, the double totals rule and hairlines.

## Shapes

Paper is cut, not moulded. Radii are barely there: 2px for printed boxes (tick boxes, graph paper, range band, time-in-range cells, the sample stamp), 3px for sheets (spreads, cover label, auth card), 4px for controls (buttons, inputs via `--r-md`). The rest of the form language is ink: 1px rules, a 1.5px rule under column heads, a 3px double rule over totals, the double printed frame inset on the cover label, and hand-drawn strokes with round caps. A few marks sit slightly askew the way stamped and pencilled things do: margin notes (-3deg), the beat line (-1deg), the sample stamp (2deg), the slip (-1.2deg, straightened when stacked).

## Components

### Buttons
Rubber stamps and printed labels: confident, flat, a little physical.
- **Shape:** squared-off (4px), Atkinson 700 at +0.005em; large size 1.02rem with 0.85rem 1.35rem padding.
- **Stamp (primary):** Stamp Sage fill in Cream, with a 3px inset gap in the fill colour and then a 1px inner frame in the text colour at 45%, so it reads as an inked stamp. Hover deepens the fill, strengthens the frame to 55%, lifts 2px and takes the sheet shadow.
- **Quiet (secondary on paper):** transparent with an Ink Brown 3 border; hover darkens the border to Ink Brown and adds a 5% ink wash.
- **Paper (on the cover):** Cover Cream fill with Cloth Deep text; hover brightens to `#fffaf0` and lifts 2px. Used in the topbar.
- **Cloth (on the cover):** transparent, Cover Cream text and a 55% cream border; hover takes a 10% black wash.
- **Focus:** 2px outline in Biro on paper, in Cover Cream on the cover (topbar, closer, footer).

### Spread, page, gutter and folio
The world's container. A spread is a two-column grid of pages on Diary Paper, 3px radius, sheet shadow. A page is padded by the page spacing; the left page draws the gutter, a page can span both columns as a fold-out, and each carries a small Young Serif folio (0.82rem, Ink Brown 3) at its outer foot. A **ruled page** adds the double Margin Rose line inside its left edge.

### Ruled diary table
The hero's example day, and the week table after it. Column heads are printed labels (0.78rem 700, unit beneath in 400) over a 1.5px Ink Brown 3 rule; body rows are 2.05rem tall on 1px Rule Blue lines, set in the hand at 1.2rem, each value in its column's ink, the time and note in biro at 72% on paper. A high reading turns Alarm Red and is ringed. The **printed totals row** closes it: a 3px double Ink Brown 2 rule, then Atkinson 700 tabular figures in Ink Brown, with small 400 sub-labels ("avg", "13.8 BU") and the in-range note in deep leaf. That row is the part a paper diary never did, and it must always be print.

### Ink strokes (ring, tick, underline)
Three authored SVG paths defined once (`#ink-circle`, `#ink-tick`, `#ink-underline`) and placed with `<use>`. Each has `pathLength="1"`, no fill, round caps and joins, `stroke: currentColor`, and `stroke-dasharray: 1`, so one `stroke-dashoffset` from 1 to 0 draws it regardless of real length. The ring circles a high in Alarm Red (2.6 stroke); the underline sits under a key word in Biro (4 stroke); the tick fills a tick box in Biro and overshoots it the way a quick tick does, or marks the everyday list in Leaf.

### Tick-option controls
Printed choices with a box to tick, used for the graph page's steps and the signature unit switch (mmol/L or mg/dL). A borderless button, min 44px tall, Atkinson 600 1rem in Ink Brown 2, with a 1.3rem tick box (1.5px Ink Brown 3 border, 2px radius, Writing Surface fill). Hover and the pressed state darken the text to Ink Brown; pressing draws the biro tick in 0.4s. `aria-pressed` carries state. Cumulative steps keep earlier boxes ticked while only the current is pressed. Switching units redraws the tick and rewrites every `.unit-value` with a 0.45s fade-from-blur.

### Graph-paper stage
The diary's graph page: an inline SVG on Writing Surface with an 18px Graph Grid, a 1px Rule Blue border and 2px radius. One example day builds in three steps: biro readings and trace; the leaf target band (wash fill, dashed 0.7 opacity edges) and the dashed alarm focus window; then the plum, ink-brown basal and ochre lanes. Axis and lane labels are Atkinson 13px in Ink Brown 3, values are Kalam 17px in biro, highs bold Alarm Red with a larger dot. The steps play once when the figure first arrives, never loop, and the first press of a step cancels the autoplay. With reduced motion or no JS it opens on the fullest step.

### Column guide
The booklet's printed column guide, one row per log type. Each row is a hairline-topped 5fr / 7fr grid (one column at 960px or below). The left side opens directly on its Young Serif title (1.35rem, 1.25) followed by copy (1rem, max 42ch); nothing sits above the heading. The right side is the column itself: a printed **column header** naming it ("Glucose column", "Insulin column", "Carbs column"; Atkinson 700 0.82rem in the column's ink) over a 2px rule in the column's own tone, then three sample form lines. Their labels are printed (0.8rem 700, Ink Brown 3). Their values are filled in once in the hand, in the column's ink, over underlines tinted with the tone at 35%. The fields run three across, or stack below 560px. The row's tone (`.t-glucose`, `.t-insulin`, `.t-meal`) supplies every ink. The column name is a header over its fields, the way a diary prints a ruled column head, and never a label above the row's heading.

### Cover-label closer
The back cover: cloth, with the booklet's printed label pasted on it. A centred Diary Paper panel up to 640px wide, 3px radius, framed by a double printed rule drawn as stacked insets (10px paper, 1px Ink Brown 3, 3px paper, 1px Ink Brown 3) and lifted by the sheet shadow. Inside: a Young Serif headline, a short line of body copy and a centred stamp-and-quiet action pair.

### Inputs / Fields (auth)
The shared `.field` primitive on Writing Surface, 1px Paper Line, 4px radius. On the auth card the caret is biro and focus turns the border Biro with a 3px biro ring at 18%. Errors are Error Red. The auth card itself is a sheet: Diary Paper, no border, 3px radius, sheet shadow, centred on the cloth at 452px.

### Navigation
The topbar prints onto the cover: the Young Serif "GlucoRead" wordmark on its own (no logo mark; the user removed the diary-page mark on 2026-11-24), cloth-ink-2 links that brighten to Cover Cream on hover, the theme switch re-skinned through scoped custom properties, and a Paper button. Below 860px the menu is a drawer over the cloth. The footer is cloth too, with cream underlined-on-hover links and the not-medical-advice disclaimer.

### The app shell (Operate mode)
The logged-in app wears the same world with less ornament, because people use it to log in a hurry. The 64px app bar and the 256px rail are the cover: they are drawn in the book cloth, with Cover Cream text and a 1px dark rule under the bar. The working column is the open page, in Diary Paper. The home link is the Young Serif "GlucoRead" wordmark at 1.3rem, in Cover Cream. Beside it, set off by a hairline, is the page label in Atkinson 600 Cover Cream 2; the label hides at 720px and below, where it could only truncate. There is no logo mark. The current section in the rail is a paper tab on the cloth, printed in Ink Brown, with the sheet shadow. Hover on the cloth is a 14% black wash. The rail's time-in-range note is a paper label pasted on the cover. The dashboard banner is one more piece of cloth: a cover band in Young Serif with Cover Cream copy. Page titles, card titles, section titles and profile section headings are Young Serif 400. Every figure stays Atkinson 700 with tabular lining numerals. In the app, entries are printed, not handwritten: tables and rows have to scan at a glance, so Kalam stays off the app. Cards, rows, forms and buttons keep their shapes; only the tokens changed. The app bar re-skins the theme switch through scoped custom properties (`--accent`, `--accent-ink`, `--paper-2`, `--line-soft`, `--ink-3`), the same way the landing topbar does.

### Motion
**The One Ink Motion Rule.** Ink draws on once, and only ink moves of its own accord. Hero strokes draw on load (1s, 0.5s delay; the ring at 1.1s). Every other stroke waits until its section arrives, then draws in 0.9s on `cubic-bezier(0.16, 1, 0.3, 1)`, staggered 0.15s in lists. Nothing loops and nothing reacts to scroll position. State changes a person causes (a tick, a step layer fading in over 0.5s, the unit rewrite, hover) may transition briefly; nothing else animates. Strokes are drawn by default and only wait when the script has marked the root `ink-ready`; under reduced motion every stroke is simply present.

## Do's and Don'ts

### Do:
- **Do** deliver this world to every page through `_theme_head.html`, which loads warm.css after theme.css, so it re-binds the raw `-l` / `-d` tokens everywhere at once.
- **Do** put every readable block on a sheet of Diary Paper; the cloth carries only the topbar, the closer and the footer, in Cover Cream.
- **Do** write logged values in Kalam in their column ink (glucose biro, insulin plum, meals ochre) and print every computed value in Atkinson 700 with tabular lining figures.
- **Do** mark a high with Alarm Red plus a second signal: the ink ring, bold weight, a larger point, or "above range" text for screen readers.
- **Do** draw new hand marks as single SVG paths with `pathLength="1"` and draw them on with `stroke-dashoffset`, once.
- **Do** use the same example day for every figure (avg 7.8, 35.0 U, 165 g / 13.8 BU, 80% in range).
- **Do** stack spreads below 960px with a dashed fold line, and let wide figures scroll in their own box rather than shrink their labels.

### Don't:
- **Don't** link warm.css from individual templates or hard-code a hex in app CSS; and don't handwrite entries in the app, where they have to scan.
- **Don't** use Alarm Red or Margin Rose for decoration, emphasis, links or brand moments.
- **Don't** set copy, headings, labels, controls or totals in the hand.
- **Don't** give shadows or cards to anything inside a page; separate with rules and hairlines.
- **Don't** add entrance, scroll-linked, looping or parallax motion; only ink draws on.
- **Don't** round sheets or controls beyond 4px.
- **Don't** put a small label or eyebrow above a heading; a column's name is a printed header over its own fields.
