const facilitySelect = document.getElementById('facilitySelect');
let healthDonut, assetHealthChart, fleetTrendChart, assetTypeChart;

const CHART_TEXT = '#7A8494';
const CHART_GRID = 'rgba(20,30,45,0.06)';

function chartJsReady() {
  return typeof Chart !== 'undefined';
}

function qs() {
  return `facility_id=${facilitySelect.value}`;
}

async function loadSummary() {
  const res = await fetch(`/api/maintenance/summary?${qs()}`);
  const d = await res.json();
  document.getElementById('kpiAssets').textContent = d.assets_monitored ?? 0;
  document.getElementById('kpiHealth').innerHTML = `${d.avg_health_score ?? '—'}<span class="unit">/100</span>`;
  document.getElementById('kpiFailures').textContent = d.predicted_failures ?? 0;
  document.getElementById('kpiDowntime').innerHTML = `${d.downtime_reduction_pct ?? 0}<span class="unit">%</span>`;

  if (d.health_distribution) {
    const dist = d.health_distribution;
    document.getElementById('healthDistribution').innerHTML = Object.entries(dist).map(([label, pct]) => `
      <div class="bar-row">
        <div class="bar-label"><span>${label}</span><span>${pct}%</span></div>
        <div class="bar-track"><div class="bar-fill" style="width:${pct}%; background:${colorFor(label)};"></div></div>
      </div>`).join('');

    const ctx = document.getElementById('healthDonut');
    if (!chartJsReady()) return;
    if (healthDonut) healthDonut.destroy();
    healthDonut = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: Object.keys(dist),
        datasets: [{
          data: Object.values(dist),
          backgroundColor: ['#1F9D6B', '#2E86C1', '#D9720C', '#D64545'],
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
}

function colorFor(label) {
  return { Excellent: '#1F9D6B', Good: '#2E86C1', Warning: '#D9720C', Critical: '#D64545' }[label] || '#2E86C1';
}

async function loadAssets() {
  const res = await fetch(`/api/maintenance/assets?${qs()}`);
  const d = await res.json();
  document.getElementById('assetCountTag').textContent = `${d.length} ASSETS`;
  const body = document.getElementById('assetTable');
  if (!d.length) {
    body.innerHTML = '<tr><td colspan="6" class="loading-note">No assets found.</td></tr>';
  } else {
    body.innerHTML = d.map(a => `
      <tr>
        <td>${a.name}</td>
        <td>${a.type}</td>
        <td>${a.health_score ?? '—'}</td>
        <td>${trendIcon(a.trend)} ${a.trend}</td>
        <td><span class="badge ${a.risk_band}">${a.risk_band}</span></td>
        <td>${a.days_to_critical ? a.days_to_critical + ' days' : '—'}</td>
      </tr>`).join('');
  }

  const sorted = [...d].sort((a, b) => (a.health_score ?? 0) - (b.health_score ?? 0));
  const ctx = document.getElementById('assetHealthChart');
  if (!chartJsReady()) return;
  if (assetHealthChart) assetHealthChart.destroy();
  assetHealthChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(a => a.name),
      datasets: [{
        label: 'Health Score',
        data: sorted.map(a => a.health_score ?? 0),
        backgroundColor: sorted.map(a => colorFor(a.risk_band)),
        borderRadius: 3,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { min: 0, max: 100, ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
        y: { ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { display: false } },
      },
    },
  });

  // Assets by type — fleet composition doughnut
  const typeCounts = {};
  d.forEach(a => { typeCounts[a.type] = (typeCounts[a.type] || 0) + 1; });
  const typeCtx = document.getElementById('assetTypeChart');
  if (chartJsReady() && Object.keys(typeCounts).length) {
    if (assetTypeChart) assetTypeChart.destroy();
    assetTypeChart = new Chart(typeCtx, {
      type: 'doughnut',
      data: {
        labels: Object.keys(typeCounts),
        datasets: [{
          data: Object.values(typeCounts),
          backgroundColor: ['#2E86C1', '#1F9D6B', '#D9720C', '#D64545', '#8E44AD', '#16A085', '#F1C40F'],
          borderWidth: 0,
        }],
      },
      options: {
        cutout: '58%',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { color: CHART_TEXT, font: { size: 10.5 }, boxWidth: 10 } } },
      },
    });
  }
}

async function loadFleetTrend() {
  const res = await fetch(`/api/maintenance/fleet-trend?${qs()}`);
  const d = await res.json();
  const ctx = document.getElementById('fleetTrendChart');
  if (!chartJsReady() || !d.labels || !d.labels.length) return;
  if (fleetTrendChart) fleetTrendChart.destroy();
  fleetTrendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: d.labels,
      datasets: [
        { label: 'Avg Vibration', data: d.avg_vibration, borderColor: '#D64545', backgroundColor: 'rgba(214,69,69,0.08)', tension: 0.3, fill: true, yAxisID: 'y' },
        { label: 'Avg Temperature (°C)', data: d.avg_temperature, borderColor: '#D9720C', backgroundColor: 'rgba(217,114,12,0.06)', tension: 0.3, fill: false, yAxisID: 'y1' },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { labels: { color: CHART_TEXT, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: CHART_TEXT, font: { size: 9.5 } }, grid: { color: CHART_GRID } },
        y: { position: 'left', ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
        y1: { position: 'right', ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { display: false } },
      },
    },
  });
}

function trendIcon(trend) {
  if (trend === 'worsening') return '↗';
  if (trend === 'improving') return '↘';
  return '→';
}

async function loadWorkOrders() {
  const res = await fetch(`/api/maintenance/work-orders?${qs()}`);
  const d = await res.json();
  document.getElementById('workOrderCountTag').textContent = `${d.length} OPEN WORK ORDERS`;
  const body = document.getElementById('workOrderTable');
  if (!d.length) {
    body.innerHTML = '<tr><td colspan="5" class="loading-note">No open work orders — all assets healthy.</td></tr>';
    return;
  }
  body.innerHTML = d.map(o => `
    <tr>
      <td><span class="badge ${o.priority}">${o.priority}</span></td>
      <td>${o.asset_name}</td>
      <td>${o.asset_type}</td>
      <td>${o.reason}</td>
      <td>${o.due}</td>
    </tr>`).join('');
}

function refreshAll() {
  loadSummary();
  loadAssets();
  loadFleetTrend();
  loadWorkOrders();
}

facilitySelect.addEventListener('change', refreshAll);
refreshAll();
setInterval(refreshAll, 60000);
