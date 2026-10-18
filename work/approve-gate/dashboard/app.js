'use strict';
const $ = id => document.getElementById(id);
let data = {pending: [], decided: []}, armed = null, busy = false, healthy = false;
let loading = null, revision = 0, rendered = null;
const uncertain = new Set();
let outcome = '', sourceError = '';
const showMessage = () => { $('message').textContent = [outcome, sourceError].filter(Boolean).join(' '); };
const controls = new Map();
const choices = [['approve', 'Approve', 'approve'], ['deny', 'Decline', 'decline']];
const rowChoices = p => p.closed ? [] : p.revoke ? [['revoke', 'Revoke', 'decline']] : choices;
function visibleRows() {
  const taskRow = (t, active) => ({...t, task: true, revoke: active, closed: !!t.status && !active,
    comment_id: 'task-' + t.ticket, action_digest: t.scope_digest,
    action: t.scope.outcome, rollback: t.scope.rollback});
  return [...data.pending,
    ...(data.tasks?.pending || []).map(t => taskRow(t, false)),
    ...(data.tasks?.grants || []).map(t => taskRow(t, t.status === 'approved'))];
}
const isArmed = (p, decision) => armed && armed.id === p.comment_id && armed.digest === p.action_digest && armed.decision === decision;
function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
}
function safeLink(url, label) {
  const a = el('a', 'ticket', label);
  try { const u = new URL(url); if (u.protocol === 'https:' && u.hostname === 'linear.app') { a.href = u.href; a.rel = 'noreferrer'; } } catch {}
  return a;
}
function requestCard(p) {
  const c = el('article', 'request'); c.id = p.comment_id;
  c.append(safeLink(p.url, p.ticket), el('h2', 'label', p.task ? 'Task outcome' : 'Exact action'), el('p', 'action', p.action));
  if (!p.task) c.append(el('p', 'context', `Verified Linear author: ${p.verified_actor} · Worker signature: ${p.worker}`));
  if (p.task) {
    c.append(el('h2', 'label', 'Existing resources'), el('p', 'context', p.scope.resources.join('\n')));
    c.append(el('h2', 'label', 'Permitted effects'));
    for (const s of p.scope.steps) c.append(el('p', 'action', `${s.id}: ${s.effect} on ${s.resource} — ${s.action}`));
    c.append(el('h2', 'label', 'Still needs approval'), el('p', 'risk', data.tasks.gated));
    c.append(el('p', 'context', p.revoke ? 'Approved until completion or revocation. Revoke stops subsequent steps once observed; it cannot undo in-flight effects.' : 'One decision covers this scope across retries and handoffs until completion or revocation.'));
    if (p.closed) c.append(el('p', 'context', 'Task authority is ' + p.status + '. This scope cannot be reused.'));
  }
  c.append(el('h2', 'label', 'Why'), el('p', 'context', p.title ? 'Ticket context: ' + p.title + ' (rationale not supplied).' : 'Not supplied.'));
  c.append(el('h2', 'label', 'Risk'), el('p', 'risk', 'Not supplied.'));
  c.append(el('h2', 'label', 'Rollback'), el('p', 'rollback', p.rollback || 'Not supplied.'));
  const buttons = el('div', 'buttons');
  const refs = [];
  for (const [decision, label, cls] of rowChoices(p)) {
    const b = el('button', cls, label);
    b.onclick = () => {
      if (busy || (!healthy && !p.revoke) || uncertain.has(p.comment_id)) return;
      if (isArmed(p, decision)) send(p, decision);
      else { armed = {id: p.comment_id, digest: p.action_digest, decision}; updateButtons(); }
    };
    buttons.append(b); refs.push(b);
  }
  const note = el('p', 'confirm-note', 'Tap confirm to record this exact decision, or choose the other button.');
  note.hidden = true;
  c.append(buttons, note);
  controls.set(p.comment_id, {p, refs, note});
  return c;
}
function updateButtons() {
  for (const {p, refs, note} of controls.values()) {
    rowChoices(p).forEach(([decision, label, cls], i) => {
      const hot = isArmed(p, decision);
      refs[i].textContent = hot ? (busy ? 'Recording…' : 'Confirm ' + label.toLowerCase()) : label;
      refs[i].className = hot ? 'confirm' : cls;
      refs[i].disabled = busy || (!healthy && !p.revoke) || uncertain.has(p.comment_id);
    });
    note.textContent = uncertain.has(p.comment_id) ? 'This decision could not be confirmed. Reload to check before trying again.' : 'Tap confirm to record this exact decision, or choose the other button.';
    note.hidden = !uncertain.has(p.comment_id) && (!armed || armed.id !== p.comment_id);
  }
  $('retry').hidden = healthy;
  $('retry').disabled = busy || !!loading;
}
function render() {
  // Ignore changing notification metadata: unchanged requests keep focus and scroll.
  const rows = visibleRows();
  const key = JSON.stringify([rows, data.tasks?.grants]);
  if (key !== rendered) {
    controls.clear(); rendered = key;
    $('pending').replaceChildren(...(rows.length ? rows.map(requestCard) : [el('p', 'empty', 'Nothing is waiting for your approval.')]));
    const id = location.hash.slice(1);
    if (id && !armed) document.getElementById(id)?.scrollIntoView({block: 'nearest'});
  }
  if (!rows.length) $('pending').firstChild.textContent = healthy ? 'Nothing is waiting for your approval.' : 'Requests could not be checked. Try again.';
  updateButtons();
}
function load() {
  if (busy) return Promise.resolve();
  if (loading) return loading.promise;
  const task = {revision, controller: new AbortController()};
  loading = task;
  task.promise = (async () => {
    try {
      const r = await fetch('/api/general', {cache: 'no-store', signal: task.controller.signal});
      if (!r.ok) throw new Error('Requests could not be checked (' + r.status + ').');
      const next = await r.json();
      if (task.revision !== revision) return;
      if (!Array.isArray(next.pending)) throw new Error('Requests could not be checked.');
      data = next; healthy = next.source?.available !== false;
      sourceError = healthy ? '' : 'Linear is unavailable. New approvals are disabled; existing task authority can still be revoked.'; showMessage();
      if (armed && !visibleRows().some(p => !p.closed && p.comment_id === armed.id && p.action_digest === armed.digest)) armed = null;
      render();
    } catch (e) {
      if (task.revision !== revision) return;
      healthy = false; armed = null;
      sourceError = e.message + ' Try again before deciding.'; showMessage();
      render();
    } finally {
      if (loading === task) { loading = null; updateButtons(); }
    }
  })();
  return task.promise;
}
async function send(p, decision) {
  if (busy || (!healthy && !p.revoke) || uncertain.has(p.comment_id) || !isArmed(p, decision)) return;
  // Cancel reads only. A decision is sent once and never aborted or retried.
  revision++; loading?.controller.abort(); loading = null;
  busy = true; updateButtons();
  outcome = 'Checking the current action and recording your decision…'; showMessage();
  try {
    const body = p.task ? {ticket: p.ticket, scope_digest: p.scope_digest, decision} : {comment_id: p.comment_id, action_digest: p.action_digest, decision};
    const r = await fetch(p.task ? '/api/general/task-decide' : '/api/general/decide', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-approve-gate': '1'},
      body: JSON.stringify(body)});
    const j = await r.json();
    outcome = r.ok ? p.ticket + ': ' + j.message + '.' : 'Not recorded: ' + j.message; showMessage();
    if (r.ok) { data.pending = data.pending.filter(row => row.comment_id !== p.comment_id); render(); }
  } catch { uncertain.add(p.comment_id); outcome = 'The result could not be confirmed. Reload to check the decision before trying again.'; showMessage(); }
  finally { armed = null; busy = false; updateButtons(); await load(); }
}
$('retry').onclick = () => { armed = null; load(); updateButtons(); };
load();
setInterval(() => { if (!document.hidden && !armed && !busy) load(); }, 15000);
window.addEventListener('pageshow', () => { if (!armed && !busy) load(); });
document.addEventListener('visibilitychange', () => { if (!document.hidden && !armed && !busy) load(); });
