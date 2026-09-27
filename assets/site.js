/* Renders the publication list and metrics from data/publications.js
   into the same .pub-item markup used in the original draft. */

(function () {
  "use strict";

  var data = window.SITE_DATA;
  if (!data) return;

  var pubs = data.publications.slice().sort(function (a, b) {
    if (b.year !== a.year) return b.year - a.year;
    return (a.pos === 1 ? 0 : 1) - (b.pos === 1 ? 0 : 1);
  });

  var ME = data.me || "A. Trinca";

  var isFirst    = function (p) { return p.pos === 1; };
  var isSecond   = function (p) { return p.pos === 2; };
  var isCo       = function (p) { return p.pos !== 1 && p.pos !== 2; };
  var isRefereed = function (p) { return p.status === "refereed" || p.status === "accepted"; };

  var TESTS = { all: function () { return true; }, first: isFirst, second: isSecond, co: isCo, refereed: isRefereed };

  function count(fn) { return pubs.filter(fn).length; }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  function link(cls, href, label) {
    var a = el("a", cls, label);
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener";
    return a;
  }

  /* ---------------------------------------------------------- metrics --- */

  function setMetric(id, value) {
    var n = document.getElementById(id);
    if (n) n.textContent = (value === null || value === undefined) ? "—" : value;
  }

  setMetric("m-total", pubs.length);
  setMetric("m-first", count(isFirst));
  setMetric("m-cites", data.metrics.citations);
  setMetric("m-hindex", data.metrics.hindex);

  var stamp = document.getElementById("pub-stamp");
  if (stamp) {
    stamp.textContent = data.metrics.updated
      ? "Citation counts synced from NASA ADS on " + data.metrics.updated + "."
      : "Citation counts sync from NASA ADS — sync not yet run.";
  }

  /* ------------------------------------------------------------- list --- */

  var list = document.getElementById("pub-list");
  if (!list) return;

  function renderAuthors(node, authors) {
    var LIMIT = 8;

    function paint(showAll) {
      node.textContent = "";
      (showAll ? authors : authors.slice(0, LIMIT)).forEach(function (name, i) {
        if (i) node.appendChild(document.createTextNode(", "));
        if (name === ME) node.appendChild(el("strong", null, name));
        else node.appendChild(document.createTextNode(name));
      });
      if (!showAll) {
        node.appendChild(document.createTextNode(" "));
        var more = el("button", "pub-link ads", "+" + (authors.length - LIMIT) + " more");
        more.type = "button";
        more.addEventListener("click", function () { paint(true); });
        node.appendChild(more);
      }
    }

    paint(authors.length <= LIMIT);
  }

  function posTag(p) {
    if (p.pos === 1) return "First author";
    if (p.pos === 2) return "Second author";
    return "Co-author";
  }

  function renderPub(p) {
    var item = el("div", "pub-item" + (p.pos === 1 ? " is-first" : ""));

    var head = p.year + (p.ref ? " · " + p.ref : (p.arxiv ? " · arXiv:" + p.arxiv : ""));
    item.appendChild(el("p", "pub-year", head));
    item.appendChild(el("p", "pub-title", p.title));

    var au = el("p", "pub-authors");
    renderAuthors(au, p.authors);
    item.appendChild(au);

    if (p.status === "preprint") item.appendChild(el("p", "pub-journal", "Preprint — not yet refereed"));
    if (p.status === "accepted") item.appendChild(el("p", "pub-journal", "Accepted, in press"));

    var links = el("div", "pub-links");
    links.appendChild(el("span", "pub-tag" + (p.pos === 1 ? "" : " muted"), posTag(p)));
    if (p.bibcode) links.appendChild(link("pub-link ads", "https://ui.adsabs.harvard.edu/abs/" + encodeURIComponent(p.bibcode) + "/abstract", "ADS"));
    if (p.doi) links.appendChild(link("pub-link doi", "https://doi.org/" + p.doi, "DOI"));
    if (p.arxiv) links.appendChild(link("pub-link arxiv", "https://arxiv.org/abs/" + p.arxiv, "arXiv:" + p.arxiv));

    if (typeof p.cites === "number") {
      var c = el("span", "pub-cites");
      c.appendChild(el("strong", null, String(p.cites)));
      c.appendChild(document.createTextNode(" citations"));
      links.appendChild(c);
    }

    item.appendChild(links);
    return item;
  }

  function paint(which) {
    var visible = pubs.filter(TESTS[which] || TESTS.all);
    list.textContent = "";

    if (!visible.length) {
      list.appendChild(el("p", "section-intro", "Nothing in this category yet."));
      return;
    }

    var year = null;
    visible.forEach(function (p) {
      if (p.year !== year) {
        year = p.year;
        list.appendChild(el("p", "pub-group-year", String(year)));
      }
      list.appendChild(renderPub(p));
    });
  }

  document.querySelectorAll(".filter").forEach(function (btn) {
    var key = btn.dataset.filter;
    var tally = btn.querySelector("em");
    if (tally) tally.textContent = count(TESTS[key] || TESTS.all);

    btn.addEventListener("click", function () {
      document.querySelectorAll(".filter").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === btn));
      });
      paint(key);
    });
  });

  paint("all");
})();
