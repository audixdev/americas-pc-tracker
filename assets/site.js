// Live touches on a static page: how long ago it was checked, and the playable countdown.
// Wording of the countdown matches rel_until() in tools/build.py.
(function () {
  "use strict";

  function ago(iso) {
    var mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (!isFinite(mins) || mins < 0) { return ""; }
    if (mins < 1) { return "just now"; }
    if (mins < 90) { return mins + " min ago"; }
    var hours = Math.round(mins / 60);
    if (hours < 48) { return hours + " h ago"; }
    return Math.round(hours / 24) + " days ago";
  }

  function until(iso) {
    var hours = (new Date(iso).getTime() - Date.now()) / 3600000;
    if (!isFinite(hours)) { return null; }
    if (hours < 0) { return "Any time now"; }
    if (hours < 12) { return "Within hours"; }
    if (hours < 36) { return "About a day"; }
    var halfDays = Math.round(hours / 12) / 2;
    var whole = Math.floor(halfDays);
    return "About " + (halfDays % 1 ? whole + "½" : whole) + " days";
  }

  function shortForm(text) {
    return text.replace("About ", "~").replace(" days", "d").replace("a day", "1d");
  }

  function tick() {
    try {
      document.querySelectorAll(".js-ago-suffix").forEach(function (el) {
        var t = ago(el.getAttribute("data-from"));
        el.textContent = t ? ", " + t : "";
      });
      document.querySelectorAll(".js-ago").forEach(function (el) {
        var t = ago(el.getAttribute("datetime"));
        if (t) { el.textContent = t; el.title = el.getAttribute("datetime"); }
      });
      document.querySelectorAll(".js-countdown").forEach(function (el) {
        var t = until(el.getAttribute("data-target"));
        if (!t) { return; }
        el.textContent = el.hasAttribute("data-short") ? shortForm(t) : t;
      });
    } catch (e) { /* leave the server-rendered text in place */ }
  }

  tick();
  setInterval(tick, 60000);
})();
