// Whetstone site enhancements — progressive: the site is fully functional without this file.
(function () {
  "use strict";

  // Copy-to-clipboard for install/terminal blocks. A .ws-copy button copies the text of the
  // command it is associated with (its sibling <code data-cmd> or [data-clipboard-text]).
  function initCopy() {
    document.querySelectorAll(".ws-copy").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var text = btn.getAttribute("data-clipboard-text");
        if (!text) {
          var host = btn.closest(".ws-install") || btn.parentElement;
          var code = host && host.querySelector("code");
          text = code ? code.textContent.trim() : "";
        }
        if (!text) return;
        var done = function () {
          var prev = btn.textContent;
          btn.textContent = "copied";
          btn.classList.add("ws-copied");
          setTimeout(function () {
            btn.textContent = prev;
            btn.classList.remove("ws-copied");
          }, 1400);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done).catch(function () {});
        } else {
          var ta = document.createElement("textarea");
          ta.value = text;
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand("copy"); done(); } catch (e) {}
          document.body.removeChild(ta);
        }
      });
    });
  }

  // Reveal-on-scroll for .ws-reveal elements.
  function initReveal() {
    var els = document.querySelectorAll(".ws-reveal");
    if (!els.length) return;
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) {
      els.forEach(function (el) { el.classList.add("ws-in"); });
      return;
    }
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) {
            e.target.classList.add("ws-in");
            io.unobserve(e.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.06 }
    );
    els.forEach(function (el) { io.observe(el); });
  }

  function init() {
    initCopy();
    initReveal();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
