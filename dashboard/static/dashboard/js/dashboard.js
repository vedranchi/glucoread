/* Glucose trend chart.

   Ported from the source design's Recharts AreaChart: a teal line over a
   vertical gradient fill, a dashed grid, and the target range marked on the
   plot. Recharts marks it with a pair of ReferenceLines; Chart.js has no
   equivalent, so `targetBand` below shades the region between them instead —
   the same information, and it reads better against the "time in range"
   number the rest of the page leads with.

   Colours come from the theme tokens rather than fixed hex values, so the
   chart follows the light/dark switch (main/js/theme.js fires themechange).
   The legend is markup in the template, not a Chart.js legend, so it can sit
   centred under the plot the way the design has it. */

(function () {
  const canvas = document.getElementById("glucoseChart");
  if (!canvas) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const token = (name) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const readJSON = (id) => {
    try {
      return JSON.parse(document.getElementById(id).textContent);
    } catch (error) {
      return [];
    }
  };

  const rangeLow = parseFloat(canvas.dataset.rangeLow);
  const rangeHigh = parseFloat(canvas.dataset.rangeHigh);
  const hasBand = Number.isFinite(rangeLow) && Number.isFinite(rangeHigh);

  /* Shades the in-range band behind the line. Drawn on beforeDatasetsDraw so
     the line and points stay on top of it. */
  const targetBand = {
    id: "targetBand",
    beforeDatasetsDraw(chart) {
      if (!hasBand) return;
      const { ctx, chartArea, scales } = chart;
      if (!chartArea) return;

      const top = scales.y.getPixelForValue(rangeHigh);
      const bottom = scales.y.getPixelForValue(rangeLow);

      ctx.save();
      ctx.beginPath();
      ctx.rect(chartArea.left, chartArea.top, chartArea.width, chartArea.height);
      ctx.clip();

      ctx.fillStyle = token("--range-wash");
      ctx.fillRect(chartArea.left, top, chartArea.width, bottom - top);

      ctx.strokeStyle = token("--range-soft");
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      [top, bottom].forEach((y) => {
        ctx.beginPath();
        ctx.moveTo(chartArea.left, y);
        ctx.lineTo(chartArea.right, y);
        ctx.stroke();
      });
      ctx.restore();
    },
  };

  /* Canvas gradients interpolate in premultiplied-alpha RGB, so a stop of
     `transparent` — which is rgba(0,0,0,0) — drags the ramp through black and
     turns a teal wash into grey silt. Both stops must therefore be the same
     RGB at different alphas, which means deriving them from a token whose
     value is a plain hex in both themes (--accent-bright is; --accent-soft is
     already an rgba() in dark). */
  const withAlpha = (hex, alpha) => {
    const digits = hex.replace("#", "");
    if (digits.length !== 6) return hex;
    const n = parseInt(digits, 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
  };

  /* The source fills the area under the line with a vertical teal gradient
     (0.3 alpha at the top, clear at the axis). Chart.js wants a
     CanvasGradient, which cannot be built until the chart area exists. */
  const areaFill = (context) => {
    const { chart } = context;
    const { ctx, chartArea } = chart;
    if (!chartArea) return "transparent";

    const teal = token("--accent-bright");
    const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    gradient.addColorStop(0, withAlpha(teal, 0.3));
    gradient.addColorStop(1, withAlpha(teal, 0));
    return gradient;
  };

  let chart = null;

  const draw = () => {
    if (typeof Chart === "undefined" || chart) return;

    const labels = readJSON("glucose-labels");
    const values = readJSON("glucose-values");
    const unitLabel = canvas.dataset.unitLabel || "";
    const accent = token("--accent-bright");

    chart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: `Glucose (${unitLabel})`,
            data: values,
            borderColor: accent,
            backgroundColor: areaFill,
            tension: 0.3,
            fill: true,
            borderWidth: 2,
            pointRadius: 4,
            pointBackgroundColor: accent,
            pointBorderColor: token("--surface"),
            pointBorderWidth: 2,
            pointHoverRadius: 6,
          },
        ],
      },
      plugins: [targetBand],
      options: {
        responsive: true,
        // .chart-wrap sets the height; letting Chart.js keep a ratio instead
        // would fight it and leave the canvas overflowing the card.
        maintainAspectRatio: false,
        animation: reducedMotion ? false : { duration: 700 },
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: token("--ink"),
            titleColor: token("--paper"),
            bodyColor: token("--paper"),
            padding: 10,
            cornerRadius: 8,
            displayColors: false,
            callbacks: {
              label: (item) => `${item.formattedValue} ${unitLabel}`,
            },
          },
        },
        scales: {
          y: {
            beginAtZero: false,
            // Keep the target band in frame even on a day whose readings all
            // sit above or below it — otherwise the band silently vanishes and
            // the legend describes something the reader cannot see.
            suggestedMin: hasBand ? rangeLow : undefined,
            suggestedMax: hasBand ? rangeHigh : undefined,
            ticks: { color: token("--ink-3") },
            grid: { color: token("--line-soft"), borderDash: [3, 3] },
            border: { display: false },
          },
          x: {
            ticks: { color: token("--ink-3") },
            grid: { display: false },
            border: { color: token("--line") },
          },
        },
      },
    });
  };

  const repaint = () => {
    if (!chart) return;
    const accent = token("--accent-bright");
    const dataset = chart.data.datasets[0];

    dataset.borderColor = accent;
    dataset.pointBackgroundColor = accent;
    dataset.pointBorderColor = token("--surface");

    chart.options.plugins.tooltip.backgroundColor = token("--ink");
    chart.options.plugins.tooltip.titleColor = token("--paper");
    chart.options.plugins.tooltip.bodyColor = token("--paper");
    chart.options.scales.y.ticks.color = token("--ink-3");
    chart.options.scales.y.grid.color = token("--line-soft");
    chart.options.scales.x.ticks.color = token("--ink-3");
    chart.options.scales.x.border.color = token("--line");

    // The area fill is a callback, so it rebuilds its gradient from the new
    // tokens on its own; the band is painted per-frame and needs no reset.
    chart.update("none");
  };

  document.addEventListener("DOMContentLoaded", draw);
  document.addEventListener("themechange", repaint);
})();
