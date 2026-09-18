/**
 * WorkforceOS Manager Dashboard — combined & hardened controller.
 * API-first: all workforce data comes from the FastAPI backend.
 * Graceful fallback to local demo data when the API is unavailable.
 */

/* ── auth gate ────────────────────────────────────────────────── */
const workforceosUser = JSON.parse(sessionStorage.getItem('workforceosUser') || 'null');
if (!workforceosUser || workforceosUser.role !== 'manager') {
  window.location.replace('employee.html');
}

/* ── DOM helpers ──────────────────────────────────────────────── */
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

/* ── shared state ─────────────────────────────────────────────── */
const state = {
  tasks: [],
  employees: [],
  currentEvent: 'break',
  recommendation: null,
  currentTaskId: null,
  apiLive: false,
};

/* ── local demo data (fallback when FastAPI is offline) ─────────── */
const LOCAL_EVENTS = {
  break: {
    eyebrow: 'EVENT / EXTENDED BREAK',
    title: "Arun's break has passed 30 minutes.",
    description: 'His active API task has 3.5 hours remaining. Without coverage, the delivery window is at risk.',
    details: [['Employee','Arun Kumar · Backend'],['Affected task','T-104 · Payment API'],['Break duration','47 minutes'],['Deadline','Today · 4:30 PM']],
    inactionRisk: '41% SLA breach risk',
    inactionCopy: 'Approx. ₹18,000 in potential delay cost.',
    label: 'Temporary coverage',
    recommendation: 'Priya covers 35% of T-104.',
    recDescription: 'She matches the backend requirements, has 4.2 available hours, and keeps both employees within planned capacity.',
    confidence: '92% fit',
    risk: '41% → 9%',
    coverage: '35% of task',
    impact: '₹18k avoided',
    action: 'Approve coverage',
    factors: [['Backend skill match',96],['Available capacity',84],['SLA likelihood',91],['Handoff cost',78]],
    taskId: 'T-104',
  },
  leave: {
    eyebrow: 'EVENT / LEAVE REQUEST',
    title: 'Rahul requested leave for tomorrow.',
    description: 'Two active data tasks need a qualified coverage plan before the request reaches manager review.',
    details: [['Employee','Rahul Mehta · Data'],['Leave period','Tomorrow · full day'],['Affected tasks','T-119, T-121'],['Coverage gap','6.0 hours']],
    inactionRisk: '27% SLA breach risk',
    inactionCopy: 'One analytics deliverable may be delayed by a day.',
    label: 'Coverage recommendation',
    recommendation: 'Split T-119 and T-121 across Maya and Vikram.',
    recDescription: 'Together they cover the required SQL and Python skills without moving any critical work.',
    confidence: '88% fit',
    risk: '27% → 7%',
    coverage: '100% of work',
    impact: '₹12k avoided',
    action: 'Send for approval',
    factors: [['Combined skill match',94],['Team capacity',81],['SLA likelihood',88],['Workload balance',86]],
    taskId: 'T-119',
  },
  critical: {
    eyebrow: 'EVENT / NEW CRITICAL INCIDENT',
    title: 'A production login issue needs an owner.',
    description: 'The incident has a two-hour SLA and needs both Python and production support experience.',
    details: [['Task','T-130 · Login outage'],['Priority','Critical'],['SLA','2 hours'],['Required skills','Python · Incident response']],
    inactionRisk: '64% SLA breach risk',
    inactionCopy: 'Customer impact and penalty exposure are increasing.',
    label: 'Priority reassignment',
    recommendation: 'Assign Nikhil now; defer T-108 by 90 minutes.',
    recDescription: 'Nikhil has the closest skill profile and sufficient capacity. T-108 has a safe deadline buffer.',
    confidence: '95% fit',
    risk: '64% → 11%',
    coverage: 'Immediate owner',
    impact: '₹42k avoided',
    action: 'Approve reassignment',
    factors: [['Incident skill match',98],['Available capacity',87],['SLA likelihood',95],['Disruption level',83]],
    taskId: 'T-130',
  },
};

const LOCAL_TASKS = [
  { priority:'Critical', cls:'critical', id:'T-130', title:'Production login outage', area:'Platform · New incident', owner:'Unassigned', deadline:'2h remaining', capacity:'—', risk:'High', riskCls:'high' },
  { priority:'High', cls:'high', id:'T-104', title:'Payment API reconciliation', area:'Payments · Backend', owner:'Arun Kumar', deadline:'Today, 4:30 PM', capacity:'84%', risk:'High', riskCls:'high' },
  { priority:'High', cls:'high', id:'T-119', title:'Customer churn analysis', area:'Data Intelligence', owner:'Rahul Mehta', deadline:'Tomorrow, 12 PM', capacity:'76%', risk:'Medium', riskCls:'medium' },
  { priority:'Medium', cls:'medium', id:'T-108', title:'Billing dashboard filters', area:'Experience · Frontend', owner:'Nikhil Shah', deadline:'Tomorrow, 5 PM', capacity:'62%', risk:'Low', riskCls:'low' },
  { priority:'Medium', cls:'medium', id:'T-121', title:'Warehouse data cleanup', area:'Data Intelligence', owner:'Rahul Mehta', deadline:'Friday, 3 PM', capacity:'76%', risk:'Low', riskCls:'low' },
];

const LOCAL_EMPLOYEES = [
  ['E001','Gautam Nair','AI Engineer','Mumbai'],['E002','Rohan Srinivasan','Data Analyst','Coimbatore'],
  ['E003','Varun Chopra','Data Analyst','Chennai'],['E004','Divya Singh','Data Engineer','Chennai'],
  ['E005','Swati Mehta','DevOps Engineer','Bengaluru'],['E006','Ishita Kumar','Product Manager','Mumbai'],
  ['E008','Rajesh Mehta','Software Developer','Bengaluru'],['E009','Meera Iyer','DevOps Engineer','Mumbai'],
  ['E010','Ishita Gupta','Security Specialist','Bengaluru'],['E011','Aditya Srinivasan','Security Specialist','Bengaluru'],
  ['E012','Siddharth Patel','Software Developer','Mumbai'],['E013','Sneha Gupta','Software Developer','Pune'],
  ['E014','Nisha Chawla','DevOps Engineer','Coimbatore'],['E015','Tanvi Nair','Security Specialist','Pune'],
  ['E016','Aarav Joshi','DevOps Engineer','Chennai'],['E017','Meera Reddy','Software Developer','Bengaluru'],
  ['E018','Rahul Pillai','AI Engineer','Coimbatore'],['E020','Tanvi Pillai','DevOps Engineer','Chennai'],
  ['E021','Varun Reddy','Security Specialist','Bengaluru'],['E022','Priya Gupta','Software Developer','Coimbatore'],
  ['E023','Varun Verma','Software Developer','Coimbatore'],['E024','Aditya Chopra','Software Developer','Mumbai'],
  ['E025','Priya Nair','Security Specialist','Hyderabad'],['E026','Gautam Nair','AI Engineer','Hyderabad'],
  ['E027','Arjun Patel','Data Analyst','Chennai'],['E028','Ananya Chopra','Product Manager','Coimbatore'],
  ['E029','Aditya Deshmukh','AI Engineer','Chennai'],['E030','Divya Chopra','Security Specialist','Mumbai'],
  ['E031','Ishita Verma','Security Specialist','Bengaluru'],['E032','Ananya Kulkarni','AI Engineer','Chennai'],
  ['E033','Kavya Srinivasan','DevOps Engineer','Coimbatore'],['E034','Aditya Singh','Software Developer','Bengaluru'],
  ['E035','Arjun Das','DevOps Engineer','Coimbatore'],['E036','Suresh Gupta','Data Engineer','Bengaluru'],
  ['E037','Aarav Chopra','Data Engineer','Mumbai'],['E038','Ishita Patel','Data Engineer','Bengaluru'],
  ['E039','Rhea Joshi','Product Manager','Coimbatore'],['E040','Gautam Joshi','Software Developer','Mumbai'],
  ['E041','Suresh Patel','DevOps Engineer','Coimbatore'],['E042','Suresh Verma','Data Engineer','Chennai'],
  ['E043','Simran Patel','Software Developer','Chennai'],['E044','Nisha Gupta','Data Engineer','Chennai'],
  ['E045','Rajesh Bhat','Data Engineer','Bengaluru'],['E046','Amit Joshi','Data Engineer','Mumbai'],
  ['E047','Suresh Joshi','Software Developer','Pune'],['E048','Meera Kulkarni','AI Engineer','Hyderabad'],
  ['E049','Tanvi Reddy','Data Engineer','Hyderabad'],['E050','Simran Kumar','DevOps Engineer','Bengaluru'],
];

/* synthetic per-employee metrics for local mode */
const LOCAL_METRICS = {};
(function () {
  let rng = 42;
  const next = () => { rng = (rng * 1664525 + 1013904223) & 0xffffffff; return (rng >>> 0) / 0xffffffff; };
  LOCAL_EMPLOYEES.forEach(([id]) => {
    const cap = 8, work = +(1.5 + next() * 6).toFixed(1);
    LOCAL_METRICS[id] = { capacity: cap, workload: work, rating: +(3.3 + next() * 1.6).toFixed(2), sla: +(82 + next() * 17).toFixed(1) };
  });
})();

/* ── utility ──────────────────────────────────────────────────── */
const initials = n => n.split(' ').map(x => x[0]).join('').slice(0, 2);
const money    = n => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n || 0);
const pct      = n => (n == null ? 'Unavailable' : `${(n * 100).toFixed(1)}%`);
const fmtDate  = s => { try { return new Date(s).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }); } catch { return s; } };

function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3200);
}

/* ── API wrapper with timeout ─────────────────────────────────── */
async function api(url, options = {}, timeoutMs = 8000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const r = await fetch(url, { ...options, signal: controller.signal });
    if (!r.ok) {
      const body = await r.text().catch(() => '');
      throw new Error(body || `HTTP ${r.status}`);
    }
    return await r.json();
  } finally {
    clearTimeout(timer);
  }
}

/* ── ROSTER ───────────────────────────────────────────────────── */
function renderRoster() {
  const roster = $('#employeeRoster');
  const analytics = $('#analyticsRoster');
  if (!roster || !analytics) return;

  if (state.apiLive && state.employees.length) {
    /* API mode — use live employee objects */
    roster.innerHTML = state.employees.map(e =>
      `<article class="employee-card">
        <div class="employee-avatar">${initials(e.name)}</div>
        <div><strong>${e.name}</strong><span>${e.employee_id}</span>
        <small>${e.job_role} · ${e.location}</small></div>
      </article>`
    ).join('');

    analytics.innerHTML = [...state.employees]
      .sort((a, b) => a.utilization_percentage - b.utilization_percentage)
      .map(e => {
        const load = Math.min(e.utilization_percentage || 0, 100);
        const avail = e.availability ? 'good' : 'low';
        const availLabel = e.availability ? 'Available' : (e.status || 'Unavailable');
        return `<tr>
          <td><div class="workforce-person"><div class="employee-avatar">${initials(e.name)}</div>
            <div><strong>${e.name}</strong><small>${e.employee_id}</small></div></div></td>
          <td>${e.job_role} · ${e.location}</td>
          <td><div class="workload-track ${load >= 100 ? 'over' : ''}"><i style="width:${load}%"></i></div>
            <small>${e.current_workload_hours}h / ${e.daily_capacity_hours}h</small></td>
          <td><span class="rate ${avail}">${availLabel}</span></td>
          <td><span class="rate good">${e.sla_success_rate}%</span></td>
        </tr>`;
      }).join('');
  } else {
    /* Fallback mode — use local arrays */
    roster.innerHTML = LOCAL_EMPLOYEES.map(([id, name, role, location]) =>
      `<article class="employee-card">
        <div class="employee-avatar">${initials(name)}</div>
        <div><strong>${name}</strong><span>${id}</span>
        <small>${role} · ${location}</small></div>
      </article>`
    ).join('');

    analytics.innerHTML = [...LOCAL_EMPLOYEES]
      .map(([id, name, role, location]) => {
        const m = LOCAL_METRICS[id] || { capacity: 8, workload: 4, rating: 4, sla: 90 };
        const load = Math.round(m.workload / m.capacity * 100);
        const avail = Math.max(0, Math.round((m.capacity - m.workload) / m.capacity * 100));
        const perf = Math.round((m.rating / 5) * 55 + (m.sla / 100) * 45);
        return `<tr>
          <td><div class="workforce-person"><div class="employee-avatar">${initials(name)}</div>
            <div><strong>${name}</strong><small>${id}</small></div></div></td>
          <td>${role} · ${location}</td>
          <td><div class="workload-track ${load > 100 ? 'over' : ''}"><i style="width:${Math.min(load, 100)}%"></i></div>
            <small>${m.workload}h / ${m.capacity}h</small></td>
          <td><span class="rate ${avail >= 30 ? 'good' : 'low'}">${avail}% available</span></td>
          <td><span class="rate ${perf >= 80 ? 'good' : 'low'}">${perf}%</span></td>
        </tr>`;
      })
      .sort((a, b) => {
        const av = el => { const m = el.match(/(\d+)% available/); return m ? -parseInt(m[1]) : 0; };
        return av(a) - av(b);
      })
      .join('');
  }
}

/* ── TASKS TABLE ──────────────────────────────────────────────── */
function renderTasks() {
  const filter = document.querySelector('[data-task-filter].selected')?.dataset.taskFilter || 'all';
  const term   = ($('#taskSearch')?.value || '').trim().toLowerCase();

  let rows;
  if (state.apiLive && state.tasks.length) {
    /* API data uses uppercase risk labels */
    rows = state.tasks.filter(t => {
      if (filter === 'risk') return ['HIGH','CRITICAL'].includes((t.risk || '').toUpperCase());
      if (filter === 'unassigned') return (t.owner || '').toLowerCase() === 'unassigned';
      return true;
    });
    if (term) rows = rows.filter(t =>
      `${t.task_name} ${t.task_id} ${t.owner}`.toLowerCase().includes(term)
    );
    $('#taskBody').innerHTML = rows.map(t => {
      const riskRaw = (t.risk || 'MEDIUM').toLowerCase();
      const priRaw  = (t.priority || 'Medium').toLowerCase();
      const prob    = t.sla_breach_probability != null ? ` (${(t.sla_breach_probability * 100).toFixed(0)}%)` : '';
      return `<tr>
        <td><span class="priority ${priRaw}">${t.priority}</span></td>
        <td class="task-title"><strong>${t.task_id} · ${t.task_name}</strong><small>${t.department || ''}</small></td>
        <td>${t.owner || 'Unassigned'}</td>
        <td>${fmtDate(t.deadline)}</td>
        <td>${t.remaining_hours != null ? t.remaining_hours + 'h' : '—'}</td>
        <td><span class="risk-pill ${riskRaw}">${t.risk}${prob}</span></td>
        <td><button class="table-action" data-task="${t.task_id}">Review →</button></td>
      </tr>`;
    }).join('') || '<tr><td colspan="7">No tasks match this view.</td></tr>';
  } else {
    /* Fallback local tasks */
    rows = LOCAL_TASKS.filter(t => {
      if (filter === 'risk') return t.risk !== 'Low';
      if (filter === 'unassigned') return t.owner === 'Unassigned';
      return true;
    });
    if (term) rows = rows.filter(t =>
      `${t.title} ${t.id} ${t.owner}`.toLowerCase().includes(term)
    );
    $('#taskBody').innerHTML = rows.map(t =>
      `<tr>
        <td><span class="priority ${t.cls}">${t.priority}</span></td>
        <td class="task-title"><strong>${t.id} · ${t.title}</strong><small>${t.area}</small></td>
        <td>${t.owner}</td>
        <td>${t.deadline}</td>
        <td>${t.capacity}</td>
        <td><span class="risk-pill ${t.riskCls}">${t.risk}</span></td>
        <td><button class="table-action" data-task="${t.id}">Review →</button></td>
      </tr>`
    ).join('') || '<tr><td colspan="7">No tasks match this view.</td></tr>';
  }
}

/* ── DECISION PANEL ───────────────────────────────────────────── */
function renderLocalDecision(type) {
  const e = LOCAL_EVENTS[type] || LOCAL_EVENTS.break;
  $('#eventEyebrow').textContent = e.eyebrow;
  $('#eventTitle').textContent   = e.title;
  $('#eventDescription').textContent = e.description;
  $('#eventDetails').innerHTML = e.details.map(([k, v]) =>
    `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
  $('#inactionRisk').textContent  = e.inactionRisk;
  $('#inactionCopy').textContent  = e.inactionCopy;
  $('#recommendationLabel').textContent = e.label;
  $('#recommendationTitle').textContent = e.recommendation;
  $('#recommendationDescription').textContent = e.recDescription;
  $('#confidence').textContent = e.confidence;
  $('#riskChange').innerHTML   = e.risk.replace('→', '<i>→</i>');
  $('#coverageValue').textContent = e.coverage;
  $('#impactValue').textContent   = e.impact;
  $('#applyPlan').innerHTML = `${e.action} <span>→</span>`;
  $('#applyPlan').disabled  = false;
  $('#factors').innerHTML = e.factors.map(([name, value]) =>
    `<div class="factor"><span>${name}</span><div class="bar"><i style="width:${value}%"></i></div><b>${value}</b></div>`
  ).join('');
  state.currentTaskId = e.taskId;
}

async function renderApiDecision(type) {
  /* pick the most relevant task for the selected event tab */
  let task;
  if (type === 'critical') {
    task = state.tasks.find(t => t.priority === 'Critical') || state.tasks[0];
  } else if (type === 'leave') {
    task = state.tasks.find(t => (t.owner || '').toLowerCase().includes('rahul')) || state.tasks[1];
  } else {
    task = state.tasks.find(t => t.priority === 'High') || state.tasks[0];
  }
  if (!task) { renderLocalDecision(type); return; }
  state.currentTaskId = task.task_id;

  /* populate event details immediately with task data */
  const tabLabel = { break: 'EXTENDED BREAK', leave: 'LEAVE REQUEST', critical: 'CRITICAL INCIDENT' };
  $('#eventEyebrow').textContent = `LIVE ANALYSIS / ${tabLabel[type] || type.toUpperCase()}`;
  $('#eventTitle').textContent   = task.task_name;
  $('#eventDescription').textContent = `${task.remaining_hours || '?'} hours remaining. Risk is evaluated live by the backend models.`;
  $('#eventDetails').innerHTML = [
    ['Task', task.task_id],
    ['Priority', task.priority],
    ['Deadline', fmtDate(task.deadline)],
    ['Current owner', task.owner || 'Unassigned'],
  ].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
  const prob = task.sla_breach_probability;
  $('#inactionRisk').textContent = prob != null ? `${pct(prob)} current SLA exposure` : 'Evaluating risk…';
  $('#inactionCopy').textContent = task.sla_penalty_inr
    ? `${money(task.sla_penalty_inr)} potential SLA penalty if breached.`
    : 'Penalty estimate loading…';

  /* fetch live recommendation */
  try {
    const rec = await api(`/api/tasks/${task.task_id}/recommendation`);
    state.recommendation = rec;
    const sel = rec.selected;
    const feasible = rec.feasible;

    $('#recommendationLabel').textContent = feasible ? 'OR-Tools recommendation' : 'Action required';
    $('#recommendationTitle').textContent = feasible
      ? `${sel.name} can cover ${task.task_id}.`
      : 'No safe allocation found.';
    $('#recommendationDescription').textContent = feasible
      ? (rec.explanation || []).join(' ')
      : (rec.suggestions || []).join(' · ');
    $('#confidence').textContent = feasible ? `${sel.skill_match_score}% skills` : 'Review constraints';
    $('#riskChange').innerHTML = feasible
      ? `${pct(rec.before?.sla_risk)} <i>→</i> ${pct(rec.after?.sla_risk)}`
      : '—';
    $('#coverageValue').textContent = feasible ? `${sel.available_capacity_hours}h capacity` : '—';
    $('#impactValue').textContent   = feasible ? money(task.sla_penalty_inr) : 'No plan';
    $('#applyPlan').innerHTML = feasible ? 'Request approval <span>→</span>' : 'No feasible plan';
    $('#applyPlan').disabled  = !feasible;

    if (feasible) {
      const factorData = [
        ['Skill match',      sel.skill_match_score],
        ['Available capacity', Math.min(100, sel.available_capacity_hours / 8 * 100)],
        ['SLA success',      100 - (sel.sla_breach_probability || 0) * 100],
        ['Performance',      (sel.performance_rating || 0) / 5 * 100],
      ];
      $('#factors').innerHTML = factorData.map(([n, v]) =>
        `<div class="factor"><span>${n}</span><div class="bar"><i style="width:${Math.max(0, Math.min(100, v))}%"></i></div><b>${Math.round(v)}</b></div>`
      ).join('');
    } else {
      $('#factors').innerHTML = '';
    }
  } catch (err) {
    /* recommendation fetch failed — fall back to local for this tab */
    renderLocalDecision(type);
    toast(`Recommendation unavailable: ${err.message}`);
  }
}

async function renderDecision(type) {
  state.currentEvent = type;
  if (state.apiLive) {
    await renderApiDecision(type);
  } else {
    renderLocalDecision(type);
  }
}

/* ── APPROVE PLAN ─────────────────────────────────────────────── */
async function approvePlan() {
  if (!state.apiLive) {
    toast(`${LOCAL_EVENTS[state.currentEvent]?.label || 'Plan'} approved locally. Start FastAPI to persist.`);
    $('#riskCount').textContent = Math.max(0, parseInt($('#riskCount').textContent || '0') - 1);
    return;
  }
  try {
    const r = await api('/api/reallocate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: 'REALLOCATION', task_id: state.currentTaskId }),
    });
    if (!r.feasible) throw new Error(r.reason || 'Not feasible');
    await api(`/api/recommendations/${r.recommendation_id}/approve`, { method: 'POST' });
    toast('Manager-approved allocation applied and saved.');
    await loadDashboard();
  } catch (err) {
    toast(`Could not approve: ${err.message}`);
  }
}

/* ── SIMULATION ───────────────────────────────────────────────── */
const LOCAL_SIMULATIONS = {
  leave:    [['Plan health','93%','Coverage found for all affected work'],['SLA exposure','7%','↓ from 27% without plan'],['Recommended change','2 people','Maya + Vikram provide coverage']],
  incident: [['Plan health','89%','One planned task moves safely'],['SLA exposure','11%','↓ from 64% without plan'],['Recommended change','1 reassignment','Nikhil takes incident ownership']],
  capacity: [['Plan health','91%','No critical task needs to move'],['SLA exposure','13%','↑ 4 points from baseline'],['Recommended change','1 task deferred','Move T-108 to tomorrow morning']],
};

async function runSimulation() {
  const scenario = $('#scenarioSelect')?.value || 'leave';
  const resultEl = $('#simulationResult');
  if (!resultEl) return;

  if (state.apiLive) {
    try {
      const map = { leave: 'leave', incident: 'critical_incident', capacity: 'multiple_unavailable' };
      const employeeIds = scenario === 'capacity'
        ? state.employees.filter(e => e.job_role?.includes('Engineer')).slice(0, 1).map(e => e.employee_id)
        : [];
      const r = await api('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_type: map[scenario] || scenario, task_id: state.currentTaskId, payload: { task_id: state.currentTaskId, employee_ids: employeeIds } }),
      });
      resultEl.innerHTML = (r.results || []).map(([a, b, c]) =>
        `<div><span>${a}</span><strong>${b}</strong><small>${c}</small></div>`).join('');
      return;
    } catch (err) {
      toast(`Simulation failed: ${err.message}`);
    }
  }
  /* fallback */
  const data = LOCAL_SIMULATIONS[scenario] || LOCAL_SIMULATIONS.leave;
  resultEl.innerHTML = data.map(([a, b, c]) =>
    `<div><span>${a}</span><strong>${b}</strong><small>${c}</small></div>`).join('');
}

/* ── CHAT / ANALYST ───────────────────────────────────────────── */
async function answer() {
  const input = $('#chatInput');
  const output = $('#chatOutput');
  if (!input || !output) return;
  const q = input.value.trim();
  if (!q) return;

  if (state.apiLive) {
    try {
      const r = await api(`/api/agent/chat?question=${encodeURIComponent(q)}`, { method: 'POST' });
      output.textContent = r.answer || 'No answer returned.';
      return;
    } catch (err) {
      /* fall through to local */
    }
  }
  /* local fallback */
  const ql = q.toLowerCase();
  if (ql.includes('risk')) {
    output.textContent = 'Three tasks need attention today. T-130 is unassigned with high risk; T-104 needs temporary backend coverage; T-119 needs leave coverage for tomorrow.';
  } else if (ql.includes('cover') || ql.includes('t-104')) {
    output.textContent = 'Priya is the strongest coverage option for T-104: 96% backend skill match, 4.2 free hours, and a predicted SLA risk reduction from 41% to 9%.';
  } else if (ql.includes('capacity')) {
    output.textContent = 'The team is operating at 78% capacity. Five qualified people have enough room for priority work.';
  } else {
    output.textContent = 'I can check availability, task risk, capacity, coverage options, and simulated changes. Try "Who can cover T-104?" or "What is at risk today?".';
  }
}

/* ── NOTIFICATIONS ────────────────────────────────────────────── */
const ALERTS = [
  { title: 'Break check unanswered', body: 'An employee did not respond to the 30-minute break check. Task coverage required.' },
  { title: 'Coverage plan ready',    body: 'A candidate can cover T-104 and reduce SLA risk to 9%.' },
  { title: 'Leave request received', body: 'A leave request for tomorrow has a coverage plan available for review.' },
  { title: 'New critical incident',  body: 'T-130 needs an incident owner within two hours.' },
];

async function loadNotifications() {
  // Notifications are intentionally not shown in the simplified manager dashboard.
  return;
}

function toggleDrawer(open) {
  $('#notificationDrawer').classList.toggle('open', open);
  $('#overlay').classList.toggle('open', open);
  $('#notificationDrawer').setAttribute('aria-hidden', String(!open));
  if (open && state.apiLive) api('/api/notifications/read', {method:'POST'}).then(()=>{$('#notificationCount').textContent='0';}).catch(err=>toast(`Unable to mark notifications read: ${err.message}`));
}

/* ── LOAD DASHBOARD (API) ─────────────────────────────────────── */
async function loadDashboard() {
  try {
    const [dash, people] = await Promise.all([
      api('/api/dashboard'),
      api('/api/employees'),
    ]);
    state.apiLive    = true;
    state.tasks      = dash.tasks || [];
    state.employees  = people || [];

    const m = dash.metrics || {};
    $('#riskCount').textContent = m.risk_count ?? state.tasks.filter(t => ['HIGH','CRITICAL'].includes((t.risk || '').toUpperCase())).length;
    if ($('#lastEvaluated')) $('#lastEvaluated').textContent = 'API live';

    const countEl = document.querySelector('.metrics article:nth-child(1) strong');
    if (countEl) countEl.innerHTML = `${m.active_employees ?? people.length}<span>/${m.total_employees ?? people.length}</span>`;

    const utilEl = document.querySelector('.metrics article:nth-child(3) strong');
    if (utilEl) utilEl.innerHTML = `${m.utilization ?? 78}<span>%</span>`;

    renderRoster();
    renderTasks();
    await renderDecision(state.currentEvent);
  } catch (err) {
    state.apiLive = false;
    /* non-blocking: dashboard still renders with local data */
    if ($('#lastEvaluated')) $('#lastEvaluated').textContent = 'offline';
    toast(`API unavailable — using local demo data. (${err.message})`);
    $('#chatOutput').textContent = 'Start the FastAPI backend for live workforce data. Local demo is active.';
    renderRoster();
    renderTasks();
    renderDecision(state.currentEvent);
  }
}

/* ── WIRE UP EVENTS ───────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  /* Main navigation: underline the section the manager selected. */
  const mainNavLinks = [...document.querySelectorAll('.topbar nav a')];
  const setActiveNav = hash => {
    const target = hash || '#overview';
    mainNavLinks.forEach(link => link.classList.toggle('active', link.getAttribute('href') === target));
  };
  mainNavLinks.forEach(link => link.addEventListener('click', () => setActiveNav(link.getAttribute('href'))));
  window.addEventListener('hashchange', () => setActiveNav(window.location.hash));
  setActiveNav(window.location.hash);

  /* sign out */
  const signOutBtn = $('#managerSignOut');
  if (signOutBtn) signOutBtn.addEventListener('click', () => {
    sessionStorage.removeItem('workforceosUser');
    window.location.href = 'employee.html';
  });

  /* event tabs */
  $$('.event-tab').forEach(btn => btn.addEventListener('click', async () => {
    document.querySelector('.event-tab.active')?.classList.remove('active');
    btn.classList.add('active');
    await renderDecision(btn.dataset.event);
  }));

  /* task filters */
  $$('[data-task-filter]').forEach(btn => btn.addEventListener('click', () => {
    document.querySelector('[data-task-filter].selected')?.classList.remove('selected');
    btn.classList.add('selected');
    renderTasks();
  }));

  /* task search */
  $('#taskSearch')?.addEventListener('input', renderTasks);

  /* task table row review button (delegate) */
  $('#taskBody')?.addEventListener('click', e => {
    const btn = e.target.closest('[data-task]');
    if (!btn) return;
    location.hash = 'tasks';
    if ($('#taskSearch')) $('#taskSearch').value = btn.dataset.task;
    renderTasks();
  });

  /* approve plan */
  $('#applyPlan')?.addEventListener('click', approvePlan);

  /* show alternatives (local hint) */
  $('#showAlternatives')?.addEventListener('click', () =>
    toast('Two alternatives compared: the recommended candidate remains the lowest-risk plan.')
  );

  /* view affected task */
  $('#viewTaskBtn')?.addEventListener('click', () => {
    location.hash = 'tasks';
    const taskId = state.apiLive
      ? (state.currentTaskId || '')
      : (LOCAL_EVENTS[state.currentEvent]?.taskId || '');
    if ($('#taskSearch')) $('#taskSearch').value = taskId;
    renderTasks();
  });

  /* simulator */
  $('#openScenario')?.addEventListener('click', () => { location.hash = 'simulator'; });
  $('#runSimulation')?.addEventListener('click', runSimulation);

  /* analyst chat */
  $('#askBtn')?.addEventListener('click', answer);
  $('#chatInput')?.addEventListener('keydown', e => { if (e.key === 'Enter') answer(); });
  $$('.chips button').forEach(b => b.addEventListener('click', () => {
    if ($('#chatInput')) $('#chatInput').value = b.textContent;
    answer();
  }));

  /* roster tabs */
  $$('[data-roster-view]').forEach(b => b.addEventListener('click', () => {
    document.querySelector('[data-roster-view].active')?.classList.remove('active');
    b.classList.add('active');
    const analytics = b.dataset.rosterView === 'analytics';
    if ($('#directoryPanel')) $('#directoryPanel').hidden = analytics;
    if ($('#analyticsPanel')) $('#analyticsPanel').hidden = !analytics;
  }));

  /* pulse-card quick filters */
  $$('.pulse-card .text-link').forEach(b => b.addEventListener('click', () => {
    location.hash = 'tasks';
    const f = b.dataset.filter || 'all';
    const target = document.querySelector(`[data-task-filter="${f === 'available' ? 'all' : 'risk'}"]`);
    if (target) {
      document.querySelector('[data-task-filter].selected')?.classList.remove('selected');
      target.classList.add('selected');
    }
    renderTasks();
    toast(f === 'available' ? 'Showing people with available capacity.' : 'Showing work that requires attention.');
  }));

  /* notifications drawer */
  $('#notificationsBtn')?.addEventListener('click', () => toggleDrawer(true));
  $('.close-drawer')?.addEventListener('click', () => toggleDrawer(false));
  $('#overlay')?.addEventListener('click', () => toggleDrawer(false));

  /* initial simulation render */
  runSimulation();

  /* boot */
  loadDashboard();
});
