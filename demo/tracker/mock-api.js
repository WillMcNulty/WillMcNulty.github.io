/* Demo-only stand-in for the tracker's Python API.
 * Serves invented sample data and keeps every edit in this browser's localStorage,
 * so the real dashboard code runs unchanged with no server and no personal data. */
(function () {
  "use strict";
  var KEY = "jobstracker-demo-v1";
  var STATUSES = ["materials_ready", "applied", "followup_sent", "screening", "interview", "offer", "rejected", "withdrawn", "unknown"];
  var FAMILIES = ["Software & IT", "Product", "BD & Strategy", "Finance & Analytics", "Policy & Ops"];

  function iso(offsetDays) {
    var d = new Date();
    d.setDate(d.getDate() + offsetDays);
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  function slug(s) { return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "application"; }

  function make(company, role, family, status, fit, strength, applied, deadline, extra) {
    var a = {
      id: slug(company + "-" + role), company: company, role: role, family: family, status: status,
      dateApplied: applied === null ? null : iso(applied), dateApprox: false, fit: fit, strength: strength,
      expectedResponse: "2-4 weeks", location: "Remote", summary: "", timing: "", deadline: deadline === null ? null : iso(deadline),
      windowStart: null, windowEnd: null, resumeFile: "sample_resume.pdf", coverFile: null, lastContact: null,
      followUpSentOn: null, nextAction: "", notes: "", followUpDraft: "", source: "demo"
    };
    for (var k in extra) a[k] = extra[k];
    return a;
  }

  function seed() {
    var draft = function (co, role) {
      return "Subject: Following up on my application - " + role + ", " + co + "\n\nHi [Name],\n\nI applied for the " + role +
        " position at " + co + " and wanted to check on the status of my application. I remain very interested and would be glad to share anything that would help.\n\nThank you,\nSample Student";
    };
    var rows = [
      make("Northwind Analytics", "Data Analyst Intern", "Finance & Analytics", "applied", 9.2, 9.0, -30, null, { summary: "Sample role: analyze sales data and build weekly dashboards.", followUpDraft: draft("Northwind Analytics", "Data Analyst Intern"), nextAction: "Send a follow-up (30 days since applying)" }),
      make("Contoso Robotics", "Software Engineering Intern", "Software & IT", "interview", 9.6, 9.4, -20, null, { summary: "Sample role: build tooling for a warehouse-robot fleet.", lastContact: iso(-2), nextAction: "Technical interview on Thursday", notes: "Two rounds. Practice explaining the projects without notes." }),
      make("Fabrikam Consulting", "Strategy Intern", "BD & Strategy", "screening", 9.0, 8.8, -14, null, { summary: "Sample role: market research and slides for a growth strategy team.", nextAction: "Prepare for the recruiter screen" }),
      make("Tailspin Health", "Product Intern", "Product", "materials_ready", 8.6, null, null, 6, { summary: "Sample role: support roadmap and user research for a patient app.", nextAction: "Submit before the deadline" }),
      make("Adventure Works", "Business Development Intern", "BD & Strategy", "materials_ready", 8.9, null, null, 12, { summary: "Sample role: build a prioritized list of prospects.", nextAction: "Confirm availability, then submit" }),
      make("Litware Systems", "Solutions Engineer Intern", "Software & IT", "applied", 9.3, 9.1, -8, 9, { summary: "Sample role: help customers configure and integrate a platform.", nextAction: "Wait for a response" }),
      make("Wingtip Cloud", "Cloud Consulting Intern", "Software & IT", "followup_sent", 8.7, 8.5, -35, null, { followUpSentOn: iso(-4), lastContact: iso(-4), summary: "Sample role: document cloud migrations.", nextAction: "Check back in a week" }),
      make("Proseware Capital", "Research Analyst Intern", "Finance & Analytics", "unknown", 8.4, null, null, null, { summary: "Sample role: materials exist but submission was never confirmed.", nextAction: "Confirm whether this was submitted" }),
      make("Trey Research", "Policy Analyst Intern", "Policy & Ops", "rejected", 8.8, 8.6, -45, null, { summary: "Sample role: policy briefs.", lastContact: iso(-10), nextAction: "Send a thank-you note" }),
      make("Blue Yonder Labs", "AI Engineering Intern", "Software & IT", "offer", 9.7, 9.5, -40, null, { summary: "Sample role: evaluate and deploy language models.", lastContact: iso(-1), nextAction: "Reply to the offer by Friday" }),
      make("Coho Winery", "Operations Intern", "Policy & Ops", "applied", 8.2, 8.3, -22, 25, { summary: "Sample role: improve scheduling and inventory workflows.", nextAction: "Wait for a response" }),
      make("Lucerne Publishing", "Digital Product Intern", "Product", "materials_ready", 8.5, null, null, 40, { summary: "Sample role: help ship a reading app feature.", nextAction: "Tailor the cover letter" })
    ];
    return { schema: 1, cycle: "Demo (sample data)", applications: rows };
  }

  function load() {
    try { var raw = localStorage.getItem(KEY); if (raw) return JSON.parse(raw); } catch (e) {}
    return null;
  }
  function save(db) { try { localStorage.setItem(KEY, JSON.stringify(db)); } catch (e) {} }
  var db = load() || seed();
  save(db);

  function reply(status, obj) {
    return new Response(JSON.stringify(obj), { status: status, headers: { "Content-Type": "application/json" } });
  }
  function clean(fields) {
    var out = {};
    for (var k in fields) {
      if (k === "id" || k === "source") continue;
      if (k === "status" && STATUSES.indexOf(fields[k]) < 0) throw new Error("status must be one of " + STATUSES.join(", "));
      if (k === "family" && FAMILIES.indexOf(fields[k]) < 0) throw new Error("family must be one of " + FAMILIES.join(", "));
      if ((k === "fit" || k === "strength") && fields[k] !== null && !(typeof fields[k] === "number" && fields[k] >= 0 && fields[k] <= 10)) throw new Error(k + " must be a number from 0 to 10");
      out[k] = fields[k];
    }
    return out;
  }

  var realFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    var url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (url.pathname.indexOf("/api/applications") === -1) return realFetch(input, init);
    var method = ((init && init.method) || "GET").toUpperCase();
    var id = url.pathname.split("/api/applications")[1].replace(/^\//, "");
    var body = {};
    try { body = init && init.body ? JSON.parse(init.body) : {}; } catch (e) { return Promise.resolve(reply(400, { error: "body is not valid JSON" })); }
    try {
      if (method === "GET") return Promise.resolve(reply(200, db));
      if (method === "POST") {
        var f = clean(body);
        if (!f.company || !String(f.company).trim()) throw new Error("company is required");
        var base = slug(f.company + (f.role ? "-" + f.role : "")), n = 2, nid = base;
        while (db.applications.some(function (a) { return a.id === nid; })) nid = base + "-" + n++;
        var app = make(f.company, f.role || "", f.family || FAMILIES[2], f.status || "applied", null, null, null, null, f);
        app.id = nid; app.source = "demo";
        db.applications.push(app); save(db); return Promise.resolve(reply(200, app));
      }
      var target = db.applications.filter(function (a) { return a.id === id; })[0];
      if (!target) return Promise.resolve(reply(404, { error: "no such application" }));
      if (method === "PATCH") {
        var upd = clean(body);
        for (var k in upd) target[k] = upd[k];
        save(db); return Promise.resolve(reply(200, target));
      }
      if (method === "DELETE") {
        db.applications = db.applications.filter(function (a) { return a.id !== id; });
        save(db); return Promise.resolve(reply(200, { ok: true }));
      }
    } catch (err) {
      return Promise.resolve(reply(400, { error: err.message }));
    }
    return Promise.resolve(reply(404, { error: "not found" }));
  };

  document.addEventListener("DOMContentLoaded", function () {
    var b = document.createElement("div");
    b.setAttribute("role", "note");
    b.style.cssText = "max-width:1240px;margin:0 auto 12px;padding:10px 14px;border:1px solid var(--line);border-radius:6px;background:var(--panel);font-size:13px;";
    b.innerHTML = 'Demo with invented sample data. Edits stay in your browser. <a href="#" id="demoReset">Reset the demo</a> or <a href="../../">go back to the portfolio</a>.';
    var wrap = document.querySelector(".wrap");
    if (wrap) wrap.insertBefore(b, wrap.firstChild);
    document.getElementById("demoReset").addEventListener("click", function (e) {
      e.preventDefault();
      try { localStorage.removeItem(KEY); } catch (err) {}
      location.reload();
    });
  });
})();
