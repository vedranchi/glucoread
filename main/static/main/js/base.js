/* App shell behaviour: delete confirmations, dismissable messages, and the
   navigation rail's overlay mode below the 900px breakpoint. */

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".message").forEach((message) => {
    message.addEventListener("click", () => message.remove());
  });

  // Delete confirmations. These were inline `onsubmit="return confirm(...)"`
  // attributes, which no nonce can authorise -- CSP treats an inline handler
  // as inline script, and the only ways to keep one are 'unsafe-inline' or
  // 'unsafe-hashes', both of which give back most of what the policy buys.
  //
  // Delegated from the document so it covers any form on any page, and bound
  // ABOVE the rail lookup below: that returns early on pages without a
  // navigation rail, which would leave those pages deleting without a prompt.
  document.addEventListener("submit", (event) => {
    const message = event.target.getAttribute?.("data-confirm");
    if (message && !window.confirm(message)) event.preventDefault();
  });

  const toggle = document.getElementById("railToggle");
  const rail = document.getElementById("rail");
  const scrim = document.getElementById("railScrim");
  if (!toggle || !rail || !scrim) return;

  const setOpen = (open) => {
    rail.classList.toggle("open", open);
    scrim.classList.toggle("open", open);
    // `hidden` rather than a style, so the scrim is out of the accessibility
    // tree while closed instead of merely invisible.
    scrim.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
  };

  toggle.addEventListener("click", () => {
    const open = !rail.classList.contains("open");
    setOpen(open);
    if (open) {
      // Move focus into the rail so a keyboard user lands on the nav they just
      // opened rather than continuing past the button.
      const first = rail.querySelector("a");
      if (first) first.focus();
    }
  });

  scrim.addEventListener("click", () => setOpen(false));

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && rail.classList.contains("open")) {
      setOpen(false);
      toggle.focus();
    }
  });

  // Leaving the overlay breakpoint returns the rail to the layout, where the
  // open class would otherwise linger and reopen it on the way back down.
  const wide = window.matchMedia("(min-width: 901px)");
  wide.addEventListener("change", (event) => {
    if (event.matches) setOpen(false);
  });
});
