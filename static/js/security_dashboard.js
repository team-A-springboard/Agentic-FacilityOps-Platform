const facilitySelect = document.getElementById('facilitySelect');
const daysSelect = document.getElementById('daysSelect');

let severityDonut, zoneRiskChart, unauthorizedTrendChart, eventTypeChart;

const CHART_TEXT = '#7A8494';
const CHART_GRID = 'rgba(20,30,45,0.06)';

function chartJsReady() {
  return typeof Chart !== 'undefined';
}

function qs() {
  const fid = facilitySelect.value;
  const days = daysSelect.value;
  return `facility_id=${fid}&days=${days}`;
}

function severityColor(sev) {
  return { Critical: '#D64545', High: '#D9720C', Medium: '#2E86C1', Low: '#1F9D6B' }[sev] || '#2E86C1';
}

async function loadSummary() {
  const res = await fetch(`/api/security/summary?${qs()}`);
  const d = await res.json();
  document.getElementById('kpiEvents').textContent = d.total_events ?? 0;
  document.getElementById('kpiUnauthorized').textContent = d.unauthorized_access_count ?? 0;
  document.getElementById('kpiCritical').textContent = d.critical_events ?? 0;
  document.getElementById('kpiZonesFlagged').textContent = d.zones_flagged ?? 0;
}

async function loadSeverityDistribution() {
  const res = await fetch(`/api/security/severity-distribution?${qs()}`);
  const d = await res.json();
  const container = document.getElementById('severityDistribution');
  const entries = Object.entries(d);
  container.innerHTML = entries.map(([label, pct]) => `
    <div class="bar-row">
      <div class="bar-label"><span>${label}</span><span>${pct}%</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%; background:${severityColor(label)};"></div></div>
    </div>`).join('');

  const ctx = document.getElementById('severityDonut');
  if (!chartJsReady()) return;
  if (severityDonut) severityDonut.destroy();
  severityDonut = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: entries.map(e => e[0]),
      datasets: [{
        data: entries.map(e => e[1]),
        backgroundColor: entries.map(e => severityColor(e[0])),
        borderWidth: 0,
      }],
    },
    options: {
      cutout: '62%',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { color: CHART_TEXT, font: { size: 11 }, boxWidth: 10 } } },
    },
  });
}

async function loadZoneRisk() {
  const res = await fetch(`/api/security/zone-risk?${qs()}`);
  const d = await res.json();
  document.getElementById('zoneRiskTag').textContent = `${d.length} ZONES`;

  const ctx = document.getElementById('zoneRiskChart');
  if (!chartJsReady()) return;
  if (zoneRiskChart) zoneRiskChart.destroy();
  zoneRiskChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: d.map(z => z.zone),
      datasets: [
        { label: 'Critical', data: d.map(z => z.critical), backgroundColor: '#D64545', stack: 's' },
        { label: 'High', data: d.map(z => z.high), backgroundColor: '#D9720C', stack: 's' },
        { label: 'Other', data: d.map(z => z.events - z.critical - z.high), backgroundColor: '#2E86C1', stack: 's' },
      ],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: CHART_TEXT, font: { size: 11 } } } },
      scales: {
        x: { stacked: true, ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
        y: { stacked: true, ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { display: false } },
      },
    },
  });
}

async function loadUnauthorizedTrend() {
  const res = await fetch(`/api/security/unauthorized-trend?${qs()}`);
  const d = await res.json();
  const ctx = document.getElementById('unauthorizedTrendChart');
  if (!chartJsReady()) return;
  if (unauthorizedTrendChart) unauthorizedTrendChart.destroy();
  unauthorizedTrendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: d.labels,
      datasets: [{
        label: 'Unauthorized-Access Events',
        data: d.counts,
        borderColor: '#D9720C',
        backgroundColor: 'rgba(217,114,12,0.12)',
        tension: 0.3,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: CHART_TEXT, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
        y: { beginAtZero: true, ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
      },
    },
  });
}

async function loadEventTypes() {
  const res = await fetch(`/api/security/event-types?${qs()}`);
  const d = await res.json();
  const entries = Object.entries(d);
  const ctx = document.getElementById('eventTypeChart');
  if (!chartJsReady() || !entries.length) return;
  if (eventTypeChart) eventTypeChart.destroy();
  eventTypeChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: entries.map(e => e[0]),
      datasets: [{
        label: 'Events',
        data: entries.map(e => e[1]),
        backgroundColor: '#2E86C1',
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
        y: { ticks: { color: CHART_TEXT, font: { size: 9.5 } }, grid: { display: false } },
      },
    },
  });
}

async function loadEvents() {
  const res = await fetch(`/api/security/events?${qs()}`);
  const d = await res.json();
  const body = document.getElementById('eventTable');
  if (!d.length) {
    body.innerHTML = '<tr><td colspan="4" class="loading-note">No security events in this window.</td></tr>';
    return;
  }
  body.innerHTML = d.map(e => `
    <tr>
      <td>${e.timestamp}</td>
      <td>${e.event_type}</td>
      <td>${e.zone ?? '—'}</td>
      <td><span class="badge ${e.severity}">${e.severity}</span></td>
    </tr>`).join('');
}

async function loadAlerts() {
  const res = await fetch(`/api/security/alerts?${qs()}`);
  const d = await res.json();
  document.getElementById('alerts').innerHTML = d.map(a => `
    <div class="rec">
      <div class="rec-head">
        <span class="rec-title">${a.title}</span>
        <span class="badge ${a.priority}">${a.priority}</span>
      </div>
      <div class="rec-detail">${a.detail}</div>
    </div>`).join('');
}

function refreshAll() {
  loadSummary();
  loadSeverityDistribution();
  loadZoneRisk();
  loadUnauthorizedTrend();
  loadEventTypes();
  loadEvents();
  loadAlerts();
}

facilitySelect.addEventListener('change', refreshAll);
daysSelect.addEventListener('change', refreshAll);
refreshAll();
setInterval(refreshAll, 60000);
