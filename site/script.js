// Klaxon landing — minimal vanilla JS for the live mission-control feel.
// Two things: the topbar block number ticks up like a real chain, and
// sections gently reveal on scroll.

(function () {
  'use strict';

  // ─── Block ticker ────────────────────────────────────────────
  // Real Base Sepolia blocks land every ~2 s. We tick the displayed block
  // every 2 s with a small jitter so the page feels alive without being
  // distracting.
  const blockEl = document.getElementById('block-num');
  if (blockEl) {
    let block = 328412998;
    const fmt = (n) =>
      n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    setInterval(() => {
      block += 1 + Math.floor(Math.random() * 2);
      blockEl.textContent = fmt(block);
    }, 2000);
  }

  // ─── Reveal on scroll ───────────────────────────────────────
  // Subtle fade-in-from-below as each section enters the viewport.
  // Honors prefers-reduced-motion via the CSS layer (animations clamp to 0.001ms).
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduceMotion && 'IntersectionObserver' in window) {
    const sections = document.querySelectorAll('main .section');
    sections.forEach((s) => s.classList.add('reveal'));

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('in');
            io.unobserve(e.target);
          }
        });
      },
      { rootMargin: '0px 0px -10% 0px', threshold: 0.05 },
    );
    sections.forEach((s) => io.observe(s));
  }
})();
