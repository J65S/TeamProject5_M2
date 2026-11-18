'use strict';
const $ = (id) => document.getElementById(id);
const state = { data: null, calendarMode: 'demo', source: 'demo', minutes: null, context: {}, busy: false, aiConfigured: false, aiBusy: false, generation: 0, records: [], startedAt: new Date().toISOString() };

function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = text;
  return item;
}
function duration(minutes) {
  const hours = Math.floor(minutes / 60), rest = minutes % 60;
  return [hours ? `${hours}h` : '', rest ? `${rest}m` : ''].filter(Boolean).join(' ') || '0m';
}
function prettyDate(iso) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}
async function api(path, payload, timeout = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, { method: payload === undefined ? 'GET' : 'POST',
      headers: payload === undefined ? {} : { 'Content-Type': 'application/json' },
      body: payload === undefined ? undefined : JSON.stringify(payload), signal: controller.signal });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'That didn’t work. Please try again.');
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('That took too long. Try again or ask your facilitator for help.');
    if (error instanceof TypeError) throw new Error('TaskPilot isn’t connected. Ask your facilitator to restart the local app.');
    throw error;
  } finally { clearTimeout(timer); }
}
function saveFile(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = node('a');
  anchor.href = url; anchor.download = name; document.body.append(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function assistantMessage(text, label = 'Study planner') {
  const outer = node('article', 'assistant-message');
  const avatar = node('span', 'assistant-avatar', '✧'); avatar.setAttribute('aria-hidden', 'true');
  const body = node('div', 'assistant-body');
  const heading = node('div', 'assistant-label', 'TaskPilot');
  heading.append(node('span', 'engine-label', label));
  body.append(heading, node('p', 'assistant-text', text)); outer.append(avatar, body);
  $('conversation').append(outer);
  return body;
}
function renderPlan(body, result) {
  const plan = result.plan;
  if (!plan) return;
  if (plan.blocks.length) {
    const blocks = node('div', 'answer-plan');
    plan.blocks.forEach((block, index) => {
      const row = node('div', 'answer-block');
      const main = node('div', 'block-main');
      main.append(node('strong', '', block.task), node('small', '', `${block.course} · Due ${deadlineLabel(block)}`));
      if (block.first_step) main.append(node('small', '', 'First step: ' + block.first_step));
      const unfinished = plan.unfinished.find((task) => task.task_id === block.task_id);
      main.append(node('span', 'block-state', unfinished ? `Work on it for ${duration(block.minutes)} · ${duration(unfinished.remaining_minutes)} still needed` : `Estimated to finish in ${duration(block.minutes)}`));
      if (block.overdue) main.append(node('span', 'answer-warning', 'Past-due: check whether this still needs to be done.'));
      row.append(node('span', 'block-number', index + 1), main, node('span', 'block-time', `${block.start ? clockRange(block) : `${block.start_minute}–${block.start_minute + block.minutes} min`}`));
      blocks.append(row);
    });
    body.append(blocks);
  }
  body.append(node('p', 'answer-meta', `Based on ${state.source === 'demo' ? 'fictional example assignments' : 'your project syllabus files'}. Earliest deadlines first. Calendar blocks use Eastern time when shown.`));
  const download = node('button', 'download-answer', '↓ Save this plan');
  if (plan.blocks.some(b => b.start)) {
    const ics = node('button', 'download-answer', '＋ Download calendar blocks (.ics)');
    ics.addEventListener('click', () => saveCalendar(plan)); body.append(ics);
  }
  download.addEventListener('click', () => saveFile(`TaskPilot-plan-${plan.as_of}.txt`, result.text, 'text/plain;charset=utf-8'));
  body.append(download);
  (result.warnings || []).forEach((warning) => body.append(node('p', 'answer-warning', warning)));
}
async function sendQuestion(message) {
  if (state.busy || !state.data || !message.trim()) return;
  const generation = state.generation;
  const prefs = {start_hour: Number($('pref-start').value), end_hour: Number($('pref-end').value), buffer: Number($('pref-buffer').value), block_minutes: Number($('pref-block').value), break_minutes: Number($('pref-break').value)};
  state.busy = true; $('send-button').disabled = true;
  $('welcome').classList.add('compact');
  $('conversation').append(node('div', 'user-message', message));
  $('question').value = '';
  $('chat-status').textContent = 'Waiting for the AI agents to interpret your request and check the calendar…';
  const record = { asked_at: new Date().toISOString(), question: message, source: state.source, calendar_mode: state.calendarMode, preferences: prefs, previous_minutes: state.minutes };
  state.records.push(record); $('save-chat').disabled = false;
  const started = performance.now();
  const progress = setInterval(() => { if (generation === state.generation) $('chat-status').textContent = `Waiting for AI reply · ${Math.floor((performance.now()-started)/1000)} seconds`; },1000);
  try {
    const result = await api('/api/chat', { message, previous_minutes: state.minutes, source: state.source, as_of: state.data.today, calendar_mode: state.calendarMode, preferences: prefs, context: state.context, history: state.records.slice(0,-1).slice(-5).flatMap(r => r.result ? [{role:'user',content:r.question},{role:'assistant',content:r.result.answer.slice(0,2000)}] : [{role:'user',content:r.question}]) }, 190000);
    record.response_ms = Math.round(performance.now() - started); record.result = result;
    if (generation !== state.generation) return;
    state.minutes = result.minutes; state.context = result.context || {};
    const body = assistantMessage(result.answer, result.engine === 'ai_cached_confirmation' ? 'AI · plan confirmation' : `AI · ${result.model || 'two agents'}`);
    if (result.plan || result.calendar) {
      const details = node('details','plan-details'); details.append(node('summary','', 'View study blocks & calendar details'));
      renderPlan(details, result); renderCalendarDetails(details, result); body.append(details);
    }
    renderExtras(body, result);
    $('chat-status').textContent = '';

  } catch (error) {
    record.error = error.message; record.response_ms = Math.round(performance.now() - started);
    if (generation === state.generation) {
      assistantMessage(error.message, 'Connection issue');
      $('question').value = message;
      $('chat-status').textContent = 'Your question is back in the box so you can try again.';
    }
  } finally {
    clearInterval(progress); state.busy = false; $('send-button').disabled = !state.data;
    if (generation === state.generation) {
      $('question').focus({ preventScroll: true });
      $('question').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'nearest' });
    }
  }
}
function resetConversation() {
  state.generation += 1; state.minutes = null; state.context = {}; state.records = []; state.startedAt = new Date().toISOString();
  $('conversation').replaceChildren(); $('welcome').classList.remove('compact'); $('question').value = '';
  $('chat-status').textContent = ''; $('save-chat').disabled = true;
}
function renderAssignments() {
  $('assignment-list').replaceChildren();
  const demo = state.source === 'demo';
  $('source-title').textContent = demo ? 'Your example week' : state.source === 'syllabi-relative' ? 'Text-file interview week' : 'December 1–7 text files';
  $('source-summary').textContent = `${state.data.assignments.length} ${demo ? 'fictional assignments, ready to try' : 'records, including completed work'}`;
  $('source-description').textContent = demo ? 'These are fictional assignments with dates relative to today. You don’t need to upload anything or enter personal academic data.' : state.source === 'syllabi-relative' ? 'The text-file demo offsets are anchored to the conversation date. Original December dates remain in the snapshot for comparison. Progress and deadlines are fictional.' : 'All fixed dates in these text files fall in December 1–7, 2026. Descriptions and progress values are fictional demonstration data, not your Canvas records.';
  $('connection-label').replaceChildren(node('span', 'status-dot'), document.createTextNode(`${demo ? 'Example week' : 'Syllabus files'} · AI answers · ${state.calendarMode === 'demo' ? 'fictional calendar' : 'Google snapshot'}`));
  state.data.assignments.forEach((task) => {
    const row = node('li'), title = node('div', '', task.task), due = node('div', 'assignment-due', deadlineLabel(task));
    title.append(node('small', '', `${task.course} · ${(task.status || 'not_started').replaceAll('_',' ')}`));
    if (task.description) title.append(node('small','',task.description)); due.append(node('small', '', `${duration(task.estimated_minutes)}${task.overdue ? ' · past-due' : ''}`)); row.append(title, due); $('assignment-list').append(row);
  });
  if (!state.data.assignments.length) $('assignment-list').append(node('li', 'empty-workspace', 'No valid assignments found. Ask your facilitator to review the source files.'));
}
async function loadWorkspace() {
  state.data = null; $('send-button').disabled = true; $('source').disabled = true;
  $('page-error').hidden = true;
  try {
    const workspace = await api('/api/workspace');
    state.aiConfigured = workspace.ai_configured;
    state.data = state.source === 'demo' ? workspace.data : await api(state.source === 'syllabi-relative' ? '/api/assignments-relative' : '/api/assignments');
    renderAssignments(); $('send-button').disabled = false;
  } catch (error) { $('page-error').textContent = error.message; $('page-error').hidden = false; $('connection-label').textContent = 'Workspace unavailable'; }
  finally { $('source').disabled = false; }
}
$('chat-form').addEventListener('submit', (event) => { event.preventDefault(); sendQuestion($('question').value.trim()); });
$('question').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if ($('chat-form').reportValidity()) sendQuestion($('question').value.trim()); } });
document.querySelectorAll('[data-question]').forEach((button) => button.addEventListener('click', () => sendQuestion(button.dataset.question)));
$('new-chat').addEventListener('click', () => { resetConversation(); $('question').focus(); });
$('source').addEventListener('change', async () => { state.source = $('source').value; resetConversation(); await loadWorkspace(); });
$('save-chat').addEventListener('click', () => {
  saveFile(`TaskPilot-conversation-${new Date().toISOString().replace(/[:.]/g, '-')}.json`, JSON.stringify({
    format: 'taskpilot-interview-transcript-v1', started_at: state.startedAt, exported_at: new Date().toISOString(),
    source: state.source, initial_assignment_snapshot: state.data, records: state.records,
    note: 'Observed interactions only. AI answer evidence is included per reply. Task success, user feedback, consent, and participant details must be recorded separately. Failed requests have no substitute answer.'
  }, null, 2), 'application/json');
});
loadWorkspace();

function clockRange(block) {
  const fmt = {hour:'numeric',minute:'2-digit',timeZone:'America/New_York'};
  return `${new Date(block.start).toLocaleDateString('en-US',{month:'short',day:'numeric',timeZone:'America/New_York'})} · ${new Date(block.start).toLocaleTimeString('en-US',fmt)}–${new Date(block.end).toLocaleTimeString('en-US',fmt)}`;
}
function renderCalendarDetails(body, result) {
  if (result.calendar) {
    const cal = result.calendar;
    const info = node('div','calendar-insight');
    info.append(node('strong','',cal.mode === 'demo' ? '✧ Interview calendar · fictional' : '◷ Google Calendar · read-only snapshot'));
    info.append(node('p','',cal.notice || cal.explanation || 'No calendar window selected.'));
    if (cal.synced_at) info.append(node('small','',cal.mode === 'demo' ? 'Simulation starts at 9:30 AM for repeatable interviews.' : `Last refreshed ${new Date(cal.synced_at).toLocaleString()} · primary calendar only`));
    if (cal.windows?.length) {
      info.append(node('p','', 'Other calendar openings (not reserved or assigned to tasks):'));
      cal.windows.forEach(w => info.append(node('div','window-chip',clockRange(w))));
    }
    body.append(info);
  }
}
function renderExtras(body, result) {
  if (result.follow_up) body.append(node('p','follow-up',result.follow_up));
  const actions = node('div','next-questions');
  (result.suggestions || []).forEach(question => {
    const button = node('button','',question+' ↗'); button.addEventListener('click',()=>sendQuestion(question)); actions.append(button);
  }); body.append(actions);
}
function setCalendarMode(mode) {
  state.calendarMode=mode; resetConversation();
  $('demo-mode').classList.toggle('selected',mode==='demo'); $('personal-mode').classList.toggle('selected',mode==='personal');
  $('demo-mode').setAttribute('aria-pressed',String(mode==='demo')); $('personal-mode').setAttribute('aria-pressed',String(mode==='personal'));
  $('mode-status').textContent=mode==='demo' ? 'Fictional schedule · simulated 9:30 AM' : 'Your primary calendar · timestamped snapshot';
}
$('demo-mode').addEventListener('click',()=>setCalendarMode('demo'));
$('personal-mode').addEventListener('click',()=>setCalendarMode('personal'));
$('refresh-calendar').addEventListener('click',async()=>{
  $('refresh-calendar').disabled=true; $('refresh-status').textContent='Refreshing…';
  try { const r=await api('/api/calendar/refresh',{},30000); $('refresh-status').textContent=`Refreshed ${r.event_count} events. Ask a new question to use them.`; }
  catch(e) { $('refresh-status').textContent=e.message; }
  finally { $('refresh-calendar').disabled=false; }
});
function saveCalendar(plan) {
  const stamp = iso => new Date(iso).toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
  const escape = text => text.replace(/\\/g,'\\\\').replace(/\n/g,'\\n').replace(/,/g,'\\,').replace(/;/g,'\\;');
  const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//TaskPilot//Study Plan//EN'];
  plan.blocks.filter(b=>b.start).forEach((b,i)=>lines.push('BEGIN:VEVENT',`UID:${Date.now()}-${i}@taskpilot.local`,`DTSTAMP:${stamp(new Date().toISOString())}`,`DTSTART:${stamp(b.start)}`,`DTEND:${stamp(b.end)}`,`SUMMARY:${escape('Study: '+b.task)}`,'END:VEVENT'));
  lines.push('END:VCALENDAR'); saveFile('TaskPilot-study-blocks.ics',lines.join('\r\n')+'\r\n','text/calendar');
}

function deadlineLabel(task) {
  return task.due_at ? new Date(task.due_at).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZone:task.timezone || 'America/New_York',timeZoneName:'short'}) : prettyDate(task.due_date);
}
