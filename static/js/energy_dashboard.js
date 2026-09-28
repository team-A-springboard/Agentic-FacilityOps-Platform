const facilitySelect = document.getElementById('facilitySelect');
const daysSelect = document.getElementById('daysSelect');

let consumptionChart, forecastChart, loadDistChart, anomalyChart, loadCompositionChart;

const CHART_TEXT = '#7A8494';
const CHART_GRID = 'rgba(20,30,45,0.06)';

// If every Chart.js CDN source failed (see chart-loader.js), skip chart
// rendering gracefully instead of throwing — KPIs, tables and bar-percentage
// rows above don't depend on Chart.js and should keep working regardless.
function chartJsReady() {
  return typeof Chart !== 'undefined';
}

function qs() {
  const fid = facilitySelect.value;
  const days = daysSelect.value;
  return `facility_id=${fid}&days=${days}`;
}

async function loadSummary() {
  const res = await fetch(`/api/energy/summary?${qs()}`);
  const d = await res.json();
  document.getElementById('kpiTotalEnergy').innerHTML = `${d.total_kwh.toLocaleString()} <span class="unit">kWh</span>`;
  document.getElementById('kpiCost').innerHTML = `₹${d.estimated_cost.toLocaleString()}`;
  document.getElementById('kpiEfficiency').innerHTML = `${d.efficiency_score}<span class="unit">%</span>`;
  document.getElementById('kpiCarbon').innerHTML = `${d.carbon_kg_est.toLocaleString()} <span class="unit">kg CO2</span>`;
}

async function loadConsumption() {
  const res = await fetch(`/api/energy/timeseries?${qs()}`);
  const d = await res.json();
  const ctx = document.getElementById('consumptionChart');
  if (!chartJsReady()) return;
  if (consumptionChart) consumptionChart.destroy();
  consumptionChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: d.labels,
      datasets: [
        { label: 'Electricity (kWh)', data: d.electricity_kwh, borderColor: '#3FA7D6', backgroundColor: 'rgba(63,167,214,0.12)', tension: 0.3, fill: true, yAxisID: 'y' },
        { label: 'Water (L)', data: d.water_liters, borderColor: '#8B7CD6', backgroundColor: 'rgba(139,124,214,0.08)', tension: 0.3, fill: true, yAxisID: 'y1' },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { labels: { color: CHART_TEXT, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
        y: { position: 'left', ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
        y1: { position: 'right', ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { display: false } },
      },
    },
  });
}

async function loadLoadDistribution() {
  const res = await fetch(`/api/energy/load-distribution?${qs()}`);
  const d = await res.json();
  const container = document.getElementById('loadDistribution');
  if (!d.hvac_pct && d.hvac_pct !== 0) { container.innerHTML = '<p class="loading-note">No data.</p>'; return; }
  const rows = [
    ['HVAC Systems', d.hvac_pct],
    ['Lighting', d.lighting_pct],
    ['Equipment', d.equipment_pct],
    ['Other Systems', d.other_pct],
  ];
  container.innerHTML = rows.map(([label, pct]) => `
    <div class="bar-row">
      <div class="bar-label"><span>${label}</span><span>${pct}%</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%;"></div></div>
    </div>`).join('');

  const ctx = document.getElementById('loadDistChart');
  if (!chartJsReady()) return;
  if (loadDistChart) loadDistChart.destroy();
  loadDistChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: rows.map(r => r[0]),
      datasets: [{
        data: rows.map(r => r[1]),
        backgroundColor: ['#2E86C1', '#1F9D6B', '#D9720C', '#8E7CC3'],
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

async function loadAnomalies() {
  const [tsRes, res] = await Promise.all([
    fetch(`/api/energy/timeseries?${qs()}`),
    fetch(`/api/energy/anomalies?${qs()}`),
  ]);
  const ts = await tsRes.json();
  const d = await res.json();

  document.getElementById('anomalyAccuracyTag').textContent = `${d.accuracy_estimate}% DETECTION ACCURACY`;

  const body = document.getElementById('anomalyTable');
  if (!d.anomalies.length) {
    body.innerHTML = '<tr><td colspan="4" class="loading-note">No anomalies in this window.</td></tr>';
  } else {
    body.innerHTML = d.anomalies.map(a => `
      <tr>
        <td>${a.timestamp}</td>
        <td>#${a.facility_id}</td>
        <td>${a.electricity_usage.toFixed(1)}</td>
        <td><span class="badge ${Math.abs(a.z_score) > 3 ? 'Critical' : 'High'}">${a.z_score}</span></td>
      </tr>`).join('');
  }

  // Overlay anomaly points on the daily usage series
  const anomalyByDay = {};
  d.anomalies.forEach(a => {
    const day = a.timestamp.slice(0, 10);
    anomalyByDay[day] = Math.max(anomalyByDay[day] || 0, a.electricity_usage);
  });

  const pointColors = ts.labels.map(day => anomalyByDay[day] ? '#D64545' : '#2E86C1');
  const pointRadii = ts.labels.map(day => anomalyByDay[day] ? 6 : 2);

  const ctx = document.getElementById('anomalyChart');
  if (!chartJsReady()) return;
  if (anomalyChart) anomalyChart.destroy();
  anomalyChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: ts.labels,
      datasets: [{
        label: 'Daily Usage (kWh) — red points are flagged anomalies',
        data: ts.electricity_kwh,
        borderColor: '#2E86C1',
        backgroundColor: 'rgba(46,134,193,0.08)',
        tension: 0.3,
        fill: true,
        pointBackgroundColor: pointColors,
        pointBorderColor: pointColors,
        pointRadius: pointRadii,
        pointHoverRadius: pointRadii.map(r => r + 2),
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: CHART_TEXT, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
        y: { ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
      },
    },
  });
}

async function loadForecast() {
  const res = await fetch(`/api/energy/forecast?facility_id=${facilitySelect.value}`);
  const d = await res.json();
  const ctx = document.getElementById('forecastChart');
  if (!chartJsReady()) return;
  if (forecastChart) forecastChart.destroy();
  forecastChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: d.map(r => r.date),
      datasets: [{ label: 'Forecast kWh', data: d.map(r => r.forecast_kwh), backgroundColor: '#D9720C', borderRadius: 4 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
      },
    },
  });
}

async function loadRecommendations() {
  const res = await fetch(`/api/energy/recommendations?${qs()}`);
  const d = await res.json();
  document.getElementById('recommendations').innerHTML = d.map(r => `
    <div class="rec">
      <div class="rec-head">
        <span class="rec-title">${r.title}</span>
        <span class="badge ${r.priority}">${r.priority}</span>
      </div>
      <div class="rec-detail">${r.detail}</div>
      ${r.est_savings_pct > 0 ? `<div class="rec-savings">Estimated savings: ${r.est_savings_pct}%</div>` : ''}
    </div>`).join('');
}

async function loadLoadComposition() {
  const res = await fetch(`/api/energy/load-timeseries?${qs()}`);
  const d = await res.json();
  const ctx = document.getElementById('loadCompositionChart');
  if (!chartJsReady() || !d.labels || !d.labels.length) return;
  if (loadCompositionChart) loadCompositionChart.destroy();
  loadCompositionChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: d.labels,
      datasets: [
        { label: 'HVAC', data: d.hvac_pct, borderColor: '#2E86C1', backgroundColor: 'rgba(46,134,193,0.35)', fill: true, stack: 'load', tension: 0.25, pointRadius: 0 },
        { label: 'Lighting', data: d.lighting_pct, borderColor: '#1F9D6B', backgroundColor: 'rgba(31,157,107,0.35)', fill: true, stack: 'load', tension: 0.25, pointRadius: 0 },
        { label: 'Equipment', data: d.equipment_pct, borderColor: '#D9720C', backgroundColor: 'rgba(217,114,12,0.35)', fill: true, stack: 'load', tension: 0.25, pointRadius: 0 },
        { label: 'Other', data: d.other_pct, borderColor: '#8E7CC3', backgroundColor: 'rgba(142,124,195,0.35)', fill: true, stack: 'load', tension: 0.25, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { labels: { color: CHART_TEXT, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
        y: { stacked: true, max: 100, ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
      },
    },
  });
}

function refreshAll() {
  loadSummary();
  loadConsumption();
  loadLoadDistribution();
  loadLoadComposition();
  loadAnomalies();
  loadForecast();
  loadRecommendations();
}

facilitySelect.addEventListener('change', refreshAll);
daysSelect.addEventListener('change', refreshAll);
refreshAll();
setInterval(refreshAll, 60000);
