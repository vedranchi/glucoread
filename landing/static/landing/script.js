/* GlucoRead landing page behaviour.

   Four small things, and nothing that runs on scroll: position is observed
   with IntersectionObserver, so the page does no work between frames.

     1. the mobile menu
     2. the topbar's hairline, once the hero passes under it
     3. one-shot reveals as sections enter
     4. the day stage's three steps, and the mmol/L <-> mg/dL switch

   Everything degrades: without JS the noscript block in index.html pins the
   reveals open and the stage to its final, fullest step. */

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const hasObserver = "IntersectionObserver" in window;

/* --- mobile menu ---------------------------------------------------------- */
const menuBtn = document.getElementById("menuBtn");
const menu = document.getElementById("menu");

if (menuBtn && menu) {
  const setMenu = (open) => {
    menu.classList.toggle("open", open);
    menuBtn.setAttribute("aria-expanded", String(open));
    menuBtn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  };

  menuBtn.addEventListener("click", () => setMenu(!menu.classList.contains("open")));

  menu.querySelectorAll("a").forEach((link) =>
    link.addEventListener("click", () => setMenu(false))
  );

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !menu.classList.contains("open")) return;
    setMenu(false);
    // Escape has to leave focus somewhere visible, and the drawer it came from
    // is now gone.
    menuBtn.focus();
  });
}

/* --- topbar gains a border once the hero scrolls under it ------------------ */
const sentinel = document.getElementById("topSentinel");
const topbar = document.getElementById("topbar");

if (sentinel && topbar && hasObserver) {
  new IntersectionObserver(([entry]) =>
    topbar.classList.toggle("is-stuck", !entry.isIntersecting)
  ).observe(sentinel);
}

/* --- scroll reveals ------------------------------------------------------- */
const revealItems = document.querySelectorAll(".reveal");

if (reducedMotion || !hasObserver) {
  revealItems.forEach((item) => item.classList.add("show"));
} else {
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("show");
        revealObserver.unobserve(entry.target);
      });
    },
    { threshold: 0.15 }
  );

  revealItems.forEach((item) => revealObserver.observe(item));
}

/* --- the day stage --------------------------------------------------------
   Three steps over one example day: the readings, the readings against the
   target band, then the insulin and meal lanes underneath. CSS does the
   drawing; this only says which step is current.

   It plays through once when the figure first comes into view, because the
   build-up IS the argument the section is making. It stops on the last step
   and never loops, and the first press of a step button cancels it for good —
   so the controls are never fighting an animation. With reduced motion set it
   does not play at all and opens on the fullest step, where all the
   information is present. */
const stage = document.querySelector("[data-stage]");

if (stage) {
  const stepButtons = Array.from(stage.querySelectorAll(".stage-steps button"));
  const captions = Array.from(stage.querySelectorAll("[data-caption]"));
  const timers = [];
  let autoplayed = false;

  /* Below the chart's 620px floor its box scrolls, and on a phone that leaves
     the evening — the 21:30 reading, the dinner and the bolus the third step's
     caption is entirely about — off the right edge. So step three brings it
     into view. Only inside the figure's own box, only when it actually
     overflows, and instantly rather than smoothly when motion is reduced. */
  const scroller = stage.querySelector(".stage-scroll");

  const showTheEvening = () => {
    if (!scroller) return;
    const hidden = scroller.scrollWidth - scroller.clientWidth;
    if (hidden <= 0) return;
    scroller.scrollTo({ left: hidden, behavior: reducedMotion ? "auto" : "smooth" });
  };

  const setStep = (step) => {
    stage.dataset.current = String(step);
    stepButtons.forEach((button) =>
      button.setAttribute("aria-pressed", String(Number(button.dataset.step) === step))
    );
    // Toggling inside the aria-live figcaption is what announces the new step.
    captions.forEach((caption) => {
      caption.hidden = Number(caption.dataset.caption) !== step;
    });
    if (step === 3) showTheEvening();
  };

  const cancelAutoplay = () => {
    autoplayed = true;
    while (timers.length) clearTimeout(timers.pop());
  };

  stepButtons.forEach((button) =>
    button.addEventListener("click", () => {
      cancelAutoplay();
      setStep(Number(button.dataset.step));
    })
  );

  if (reducedMotion || !hasObserver) {
    setStep(3);
    autoplayed = true;
  } else {
    setStep(1);

    const stageObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting || autoplayed) return;
          autoplayed = true;
          stageObserver.unobserve(entry.target);
          timers.push(setTimeout(() => setStep(2), 1500));
          timers.push(setTimeout(() => setStep(3), 3200));
        });
      },
      { threshold: 0.4 }
    );

    stageObserver.observe(stage);
  }
}

/* --- unit switch ----------------------------------------------------------
   Mirrors the app exactly: values are held in mmol/L and converted only for
   display, so switching units never rewrites what was recorded.
   1 mmol/L = 18 mg/dL, the same factor logs/conversions.py uses. */
const MGDL_PER_MMOL = 18;
const unitButtons = document.querySelectorAll("[data-unit]");
const unitValues = document.querySelectorAll(".unit-value");
const unitLabels = document.querySelectorAll(".unit-label");
const rangeBar = document.querySelector(".range-bar");

/* One decimal in BOTH units, because that is what logs/conversions.to_display
   returns — a mg/dL reading renders as 70.2, not 70. Rounding to a whole
   number here would look tidier and would misrepresent the app. */
const format = (mmol, unit) =>
  (unit === "mgdl" ? mmol * MGDL_PER_MMOL : mmol).toFixed(1);

const renderUnit = (unit) => {
  const label = unit === "mgdl" ? "mg/dL" : "mmol/L";

  unitValues.forEach((node) => {
    const mmol = Number.parseFloat(node.dataset.mmol);
    if (Number.isNaN(mmol)) return;

    node.textContent = format(mmol, unit);

    if (reducedMotion) return;
    node.classList.remove("is-swapping");
    void node.offsetWidth; // restart the swap animation
    node.classList.add("is-swapping");
  });

  unitLabels.forEach((node) => {
    node.textContent = label;
  });

  // The bar is an image with its values in its label, so the label has to
  // follow the switch or it starts describing the other unit.
  if (rangeBar) {
    rangeBar.setAttribute(
      "aria-label",
      `A reading of ${format(6.2, unit)} sits inside the target band of ` +
        `${format(3.9, unit)} to ${format(10, unit)} ${label}.`
    );
  }
};

unitButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (button.getAttribute("aria-pressed") === "true") return;

    unitButtons.forEach((other) =>
      other.setAttribute("aria-pressed", String(other === button))
    );

    renderUnit(button.dataset.unit);
  });
});
