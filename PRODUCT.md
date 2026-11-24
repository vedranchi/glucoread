# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People who take insulin, mostly type 1 and some type 2, and keep their own day-to-day
log of glucose readings, insulin doses and meals/carbs. They log on a phone or laptop
several times a day, often right before or after eating or dosing.

## Product Purpose

GlucoRead is a free web app for logging glucose, insulin and meals side by side, so a
reading is seen with the doses and meals around it. Success: logging takes a moment, and
patterns such as "high after dinner, three evenings running" become visible.

## Positioning

The three log types live on one timeline and one dashboard, so each reading carries its
context. The app has no ads, no trackers and no analytics, and it is open source under MIT.

## Capabilities and Constraints

- Glucose is stored in mmol/L and shown in mmol/L or mg/dL, per user.
- Users set their own target range. Readings are flagged against it, and the app shows
  time in range.
- Insulin is logged as basal or bolus, with units and an optional brand.
- Meals are logged as breakfast, lunch, dinner or snack, with optional macros. Bread
  units are computed from the user's own grams per unit.
- Server-rendered Django with a nonce-based CSP. The landing page loads no third-party
  scripts.
- Not yet available (planned for v1.1): back-dating entries, a restore UI for deleted
  entries, per-user time zones.

## Brand Commitments

- The name is GlucoRead, spelled exactly that way.
- The tagline is "See the pattern, not just the number."
- The whole product uses the warm "paper logbook" look: the landing page, the auth screens
  and the logged-in app (user decision, 2026-11-24, extending the 2026-11-23 decision that
  covered landing and auth only).

## Evidence on Hand

- One example day is used by every figure on the landing page: average 7.8 mmol/L,
  35.0 U insulin, 165 g carbs / 13.8 BU, 80% in range.
- There are no testimonials, user counts, press mentions or customer logos. Do not invent
  any.
- There is no founder's letter or personal story, by user decision.

## Product Principles

- It is a record, not a recommendation: GlucoRead never diagnoses, doses or advises.
- Every number on a page must agree with every other number on that page.
- Only claims that are true of the current build are made.
- Logging must be quicker than putting it off.

## Accessibility & Inclusion

Glucose status is never conveyed by colour alone. The site must work with keyboard and
screen reader, and must respect reduced-motion settings.
