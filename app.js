// ---------- Unlogged Texts ----------
// Shows the unlogged-session text messages (unlogged.json, built from the "<Brand> Unlogged Sessions
// <pay period>" Google Docs by scripts/build_unlogged.py). Pick GRIP or Elevate and a pay period,
// then text each trainer (their cell number comes from the ClubReady staff lists) or copy the text.
// What's been sent, and numbers typed in for trainers missing one, are remembered on this phone only.

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};

const S = { data: null, brand: store.get("ut.brand", "GRIP"), docId: "", filter: "todo", search: "", sent: {}, edits: {}, open: {} };
const doc = () => S.data && S.data.docs.find((d) => d.id === S.docId);
const keyOf = (t) => `${t.name}|${t.club}`;
const myPhones = () => store.get("ut.phones", {}); // numbers typed in on this phone, by brand|trainer
const phoneOf = (t) => myPhones()[`${S.brand}|${t.name}`] || t.phone || "";
const fmtPhone = (p) => `(${p.slice(0, 3)}) ${p.slice(3, 6)}-${p.slice(6)}`;
const status = (text, bad) => { $("status").textContent = text; $("status").classList.toggle("bad", !!bad); };

async function load() {
  try {
    const res = await fetch(`unlogged.json?_=${Date.now()}`);
    if (!res.ok) throw new Error("The texts aren't built yet: run the Deploy workflow.");
    S.data = await res.json();
  } catch (err) {
    console.error(err);
    return status(err.message || "Couldn't load the texts.", true);
  }
  $("asOf").textContent = `Updated ${new Date(S.data.generated).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}.`;
  if (S.data.skipped && S.data.skipped.length) {
    status(`Couldn't read: ${S.data.skipped.join(", ")}. Share it "Anyone with the link can view" or move it into the Unlogged Sessions folder.`, true);
  }
  setBrand(S.brand, true);
  $("app").hidden = false;
}

function setBrand(brand, initial) {
  S.brand = brand;
  store.set("ut.brand", brand);
  document.documentElement.dataset.brand = brand;
  document.querySelectorAll("#brandSeg button").forEach((b) => b.classList.toggle("on", b.dataset.brand === brand));
  const docs = S.data.docs.filter((d) => d.brand === brand).sort((a, b) => b.sort - a.sort);
  $("period").innerHTML = docs.length
    ? docs.map((d) => `<option value="${esc(d.id)}">${esc(d.period)}</option>`).join("")
    : `<option value="">No pay periods yet</option>`;
  const saved = store.get(`ut.period.${brand}`, "");
  S.docId = docs.some((d) => d.id === saved) ? saved : docs[0] ? docs[0].id : "";
  $("period").value = S.docId;
  if (!initial) { S.search = ""; $("search").value = ""; }
  openDoc();
}

function openDoc() {
  store.set(`ut.period.${S.brand}`, S.docId);
  S.sent = store.get(`ut.sent.${S.docId}`, {});
  S.edits = {};
  S.open = {};
  render();
}

function render() {
  const d = doc();
  if (!d) {
    $("summary").innerHTML = "";
    $("list").innerHTML = `<p class="empty">No ${esc(S.brand)} texts yet. Add a "${esc(S.brand)} Unlogged Sessions &lt;pay period&gt;" doc to the Unlogged Sessions folder.</p>`;
    $("needs").hidden = true;
    $("docLink").innerHTML = "";
    return;
  }
  const all = d.trainers;
  const sentCount = all.filter((t) => S.sent[keyOf(t)]).length;
  const sessions = all.reduce((n, t) => n + t.sessions, 0);
  $("summary").innerHTML = `
    <div class="stat"><b>${all.length}</b><span>trainers</span></div>
    <div class="stat"><b>${sessions}</b><span>sessions</span></div>
    <div class="stat"><b>${sentCount}/${all.length}</b><span>sent</span></div>
    <div class="progress" aria-hidden="true"><i style="width:${all.length ? (100 * sentCount) / all.length : 0}%"></i></div>`;
  document.querySelectorAll("#filterSeg button").forEach((b) => b.classList.toggle("on", b.dataset.filter === S.filter));

  const q = S.search.trim().toLowerCase();
  const list = all.filter((t) => {
    const sent = !!S.sent[keyOf(t)];
    if (S.filter === "todo" && sent) return false;
    if (S.filter === "sent" && !sent) return false;
    return !q || `${t.name} ${t.club}`.toLowerCase().includes(q);
  });
  $("list").innerHTML = list.length ? list.map((t) => {
    const k = keyOf(t), sent = !!S.sent[k], msg = S.edits[k] ?? t.message, long = t.sessions > 6 && !S.open[k], ph = phoneOf(t);
    const rows = Math.min(msg.split("\n").length + 1, long ? 8 : 40);
    return `<article class="card${sent ? " sent" : ""}" data-k="${esc(k)}">
      <div class="top">
        <div><div class="name">${esc(t.name)}${t.note ? `<span class="tag">${esc(t.note)}</span>` : ""}</div>
          <div class="meta">${esc(t.club)}${t.label && !/^\d+ sessions?$/.test(t.label) ? ` · ${esc(t.label)}` : ""}</div>
          <div class="meta">${ph ? `${esc(fmtPhone(ph))} <button type="button" class="more" data-act="phone">change</button>`
            : `<span class="nophone">No number on file</span> <button type="button" class="more" data-act="phone">add number</button>`}</div></div>
        <span class="count">${t.sessions} session${t.sessions === 1 ? "" : "s"}</span>
      </div>
      <textarea class="msg${long ? " collapsed" : ""}" rows="${rows}" aria-label="Text for ${esc(t.name)}">${esc(msg)}</textarea>
      ${long ? `<button type="button" class="more" data-act="expand">Show all ${t.sessions} sessions</button>` : ""}
      <div class="actions">
        <a class="btn primary" href="#" data-act="sms">${ph ? `Text ${esc(t.name.split(/\s+/)[0])}` : "Messages"}</a>
        <button type="button" class="btn" data-act="copy">Copy</button>
        <label class="check"><input type="checkbox" data-act="sent"${sent ? " checked" : ""}> Sent</label>
      </div>
    </article>`;
  }).join("") : `<p class="empty">${S.filter === "todo" && !q ? "All texts sent for this pay period." : "No one here."}</p>`;

  // Grow each message box to fit its text (long ones stay short until "Show all").
  document.querySelectorAll(".msg:not(.collapsed)").forEach(fit);

  $("needs").hidden = !d.needsLook.length;
  $("needsCount").textContent = d.needsLook.length ? `(${d.needsLook.length})` : "";
  $("needsList").innerHTML = d.needsLook.map((x) => `<li>${esc(x)}</li>`).join("");
  $("docLink").innerHTML = `${d.intro ? `${esc(d.intro)} ` : ""}<a href="${esc(d.docUrl)}" target="_blank" rel="noopener">Open the doc</a>`;
}

function fit(ta) {
  ta.style.height = "auto";
  ta.style.height = `${ta.scrollHeight + 2}px`;
}

function markSent(k, on) {
  if (on) S.sent[k] = new Date().toISOString(); else delete S.sent[k];
  store.set(`ut.sent.${S.docId}`, S.sent);
}

async function copyText(text, ta) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Older iOS: select the textarea and use the legacy copy command.
    ta.focus();
    ta.setSelectionRange(0, ta.value.length);
    try { return document.execCommand("copy"); } catch { return false; }
  }
}

// iOS reads "&body=", Android "?body=", so "?&body=" works on both. No number: pick the trainer in Messages.
const smsHref = (phone, msg) => `sms:${phone ? `+1${phone}` : ""}?&body=${encodeURIComponent(msg)}`;

$("list").addEventListener("click", async (e) => {
  const el = e.target.closest("[data-act]");
  if (!el) return;
  const card = el.closest(".card"), k = card.dataset.k, ta = card.querySelector(".msg"), t = doc().trainers.find((x) => keyOf(x) === k);
  if (el.dataset.act === "copy") {
    const ok = await copyText(ta.value, ta);
    if (!ok) return status("Couldn't copy: press and hold the text to copy it.", true);
    el.textContent = "Copied ✓";
    status(`Copied the text for ${t.name}. Paste it into Messages.`);
    setTimeout(() => { markSent(k, true); render(); }, 900);
  } else if (el.dataset.act === "sms") {
    el.href = smsHref(phoneOf(t), ta.value); // follows the link into Messages with the number and text filled in
    markSent(k, true);
    setTimeout(render, 500);
  } else if (el.dataset.act === "phone") {
    const v = prompt(`Cell number for ${t.name}`, phoneOf(t) ? fmtPhone(phoneOf(t)) : "");
    if (v == null) return;
    const d = v.replace(/\D/g, "").replace(/^1(?=\d{10}$)/, ""), all = myPhones();
    if (d && d.length !== 10) return status("Enter a 10-digit number.", true);
    if (d && d !== t.phone) all[`${S.brand}|${t.name}`] = d; else delete all[`${S.brand}|${t.name}`];
    store.set("ut.phones", all);
    status(d ? `Saved ${t.name}'s number on this phone.` : `Cleared the number for ${t.name}.`);
    render();
  } else if (el.dataset.act === "expand") {
    S.open[k] = true;
    render();
  }
});
$("list").addEventListener("change", (e) => {
  const el = e.target.closest("[data-act=sent]");
  if (!el) return;
  markSent(el.closest(".card").dataset.k, el.checked);
  render();
});
$("list").addEventListener("input", (e) => {
  if (!e.target.classList.contains("msg")) return;
  if (!e.target.classList.contains("collapsed")) fit(e.target);
  S.edits[e.target.closest(".card").dataset.k] = e.target.value;
});
$("brandSeg").addEventListener("click", (e) => {
  const b = e.target.closest("[data-brand]");
  if (b && S.data && b.dataset.brand !== S.brand) setBrand(b.dataset.brand);
});
$("filterSeg").addEventListener("click", (e) => {
  const b = e.target.closest("[data-filter]");
  if (b) { S.filter = b.dataset.filter; render(); }
});
$("period").onchange = () => { S.docId = $("period").value; openDoc(); };
$("search").oninput = () => { S.search = $("search").value; render(); };
load();
