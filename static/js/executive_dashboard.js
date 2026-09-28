const facilitySelect = document.getElementById('facilitySelect');
const downloadReportBtn = document.getElementById('downloadReportBtn');
const CHART_TEXT = '#7A8494';
const CHART_GRID = 'rgba(20,30,45,0.06)';
const BREAKDOWN_COLORS = ['#2E86C1', '#1F9D6B', '#D9720C', '#D64545', '#8E44AD', '#16A085', '#F1C40F', '#7A8494'];

let healthGauge, domainRadarChart, costDistChart, costTrendChart, rankingChart, complianceChart;

function chartJsReady() {
  return typeof Chart !== 'undefined';
}

function qs() {
  return facilitySelect.value ? `facility_id=${facilitySelect.value}` : '';
}

function fmtMoney(n) {
  if (n === undefined || n === null) return '—';
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  if (abs >= 1e7) return sign + '₹' + (abs / 1e7).toFixed(2) + 'Cr';
  if (abs >= 1e5) return sign + '₹' + (abs / 1e5).toFixed(2) + 'L';
  if (abs >= 1e3) return sign + '₹' + (abs / 1e3).toFixed(1) + 'K';
  return sign + '₹' + abs.toLocaleString();
}

function healthColor(score) {
  if (score >= 80) return '#1F9D6B';
  if (score >= 60) return '#D9720C';
  return '#D64545';
}

async function loadSummary() {
  const res = await fetch(`/api/executive/summary?${qs()}`);
  const d = await res.json();

  document.getElementById('kpiCostReduction').innerHTML = `${d.cost_reduction_pct ?? 0}<span class="unit">%</span>`;
  document.getElementById('kpiRoi').innerHTML = `${d.roi_generated_pct ?? 0}<span class="unit">%</span>`;
  document.getElementById('kpiSavings').innerHTML = fmtMoney(d.potential_savings);
  document.getElementById('kpiOptimizations').textContent = d.optimizations_identified ?? 0;

  const health = d.facility_health_score ?? 0;
  document.getElementById('gaugeValue').textContent = `${health}`;

  // Half-donut gauge: value slice + remainder, transparent bottom half via rotation/circumference
  const ctx = document.getElementById('healthGauge');
  if (chartJsReady()) {
    if (healthGauge) healthGauge.destroy();
    healthGauge = new Chart(ctx, {
      type: 'doughnut',
      data: {
        datasets: [{
          data: [health, 100 - health],
          backgroundColor: [healthColor(health), 'rgba(255,255,255,0.12)'],
          borderWidth: 0,
        }],
      },
      options: {
        circumference: 180,
        rotation: 270,
        cutout: '75%',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
      },
    });
  }

  // Cross-agent domain radar
  const radarCtx = document.getElementById('domainRadarChart');
  if (chartJsReady()) {
    if (domainRadarChart) domainRadarChart.destroy();
    domainRadarChart = new Chart(radarCtx, {
      type: 'radar',
      data: {
        labels: ['Energy Efficiency', 'Asset Health', 'Security', 'Occupancy'],
        datasets: [{
          label: 'Domain Score (0-100)',
          data: [d.energy_efficiency_score ?? 0, d.avg_asset_health ?? 0, d.security_score ?? 0, d.occupancy_score ?? 0],
          backgroundColor: 'rgba(46,134,193,0.18)',
          borderColor: '#2E86C1',
          pointBackgroundColor: '#2E86C1',
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          r: {
            min: 0, max: 100,
            angleLines: { color: CHART_GRID },
            grid: { color: CHART_GRID },
            pointLabels: { color: CHART_TEXT, font: { size: 11.5 } },
            ticks: { color: CHART_TEXT, backdropColor: 'transparent', font: { size: 9 } },
          },
        },
      },
    });
  }
}

async function loadCostDistribution() {
  const res = await fetch('/api/executive/cost-distribution');
  const d = await res.json();
  const entries = Object.entries(d).sort((a, b) => b[1] - a[1]);

  const ctx = document.getElementById('costDistChart');
  if (!entries.length) return;
  if (chartJsReady()) {
    if (costDistChart) costDistChart.destroy();
    costDistChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: entries.map(e => e[0]),
        datasets: [{
          data: entries.map(e => e[1]),
          backgroundColor: BREAKDOWN_COLORS,
          borderWidth: 0,
        }],
      },
      options: {
        cutout: '58%',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { color: CHART_TEXT, font: { size: 10.5 }, boxWidth: 10 } },
        },
      },
    });
  }
}

async function loadCostTrend() {
  const res = await fetch('/api/cost/trend?months=12');
  const d = await res.json();
  const ctx = document.getElementById('costTrendChart');
  if (!d.labels || !d.labels.length) return;
  if (chartJsReady()) {
    if (costTrendChart) costTrendChart.destroy();
    costTrendChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: d.labels,
        datasets: [
          { label: 'Operational Cost', data: d.operational_cost, borderColor: '#D64545', backgroundColor: 'rgba(214,69,69,0.08)', tension: 0.3, fill: true },
          { label: 'Budget Allocated', data: d.budget_allocated, borderColor: '#2E86C1', backgroundColor: 'rgba(46,134,193,0.06)', tension: 0.3, borderDash: [5, 4], fill: false },
          { label: 'Potential Savings', data: d.potential_savings, borderColor: '#1F9D6B', backgroundColor: 'rgba(31,157,107,0.08)', tension: 0.3, fill: true },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { color: CHART_TEXT, font: { size: 10.5 } } } },
        scales: {
          x: { ticks: { color: CHART_TEXT, font: { size: 9.5 } }, grid: { display: false } },
          y: { ticks: { color: CHART_TEXT, font: { size: 9.5 }, callback: v => fmtMoney(v) }, grid: { color: CHART_GRID } },
        },
      },
    });
  }
}

async function loadRanking() {
  const res = await fetch('/api/executive/ranking');
  const d = await res.json();

  const body = document.getElementById('rankingTable');
  if (!d.length) {
    body.innerHTML = '<tr><td colspan="4" class="loading-note">No data.</td></tr>';
    return;
  }
  body.innerHTML = d.slice(0, 8).map(r => `
    <tr>
      <td>${r.facility_id}</td>
      <td>${r.facility_type}</td>
      <td>${fmtMoney(r.potential_savings)}</td>
      <td>${r.avg_roi_pct}%</td>
    </tr>`).join('');

  const top8 = d.slice(0, 8);
  const ctx = document.getElementById('rankingChart');
  if (chartJsReady()) {
    if (rankingChart) rankingChart.destroy();
    rankingChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: top8.map(r => r.facility_id),
        datasets: [{
          label: 'Potential Savings',
          data: top8.map(r => r.potential_savings),
          backgroundColor: top8.map(r => r.over_budget ? '#D64545' : '#D9720C'),
          borderRadius: 4,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: CHART_TEXT, font: { size: 9.5 }, callback: v => fmtMoney(v) }, grid: { color: CHART_GRID } },
          y: { ticks: { color: CHART_TEXT, font: { size: 10.5 } }, grid: { display: false } },
        },
      },
    });
  }
}

async function loadBudgetCompliance() {
  const res = await fetch('/api/cost/budget-compliance?months=12');
  const d = await res.json();
  if (!d.periods_within_budget && d.periods_within_budget !== 0) return;

  document.getElementById('complianceTag').textContent = `${d.compliance_pct}% COMPLIANT`;
  const ctx = document.getElementById('complianceChart');
  if (chartJsReady()) {
    if (complianceChart) complianceChart.destroy();
    complianceChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Within Budget', 'Over Budget'],
        datasets: [{
          data: [d.periods_within_budget, d.periods_over_budget],
          backgroundColor: ['#1F9D6B', '#D64545'],
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

async function loadRecommendations() {
  const res = await fetch(`/api/executive/recommendations?${qs()}`);
  const d = await res.json();
  document.getElementById('recCountTag').textContent = `${d.length} RECOMMENDATIONS`;
  document.getElementById('recommendations').innerHTML = d.map(r => `
    <div class="rec">
      <div class="rec-head">
        <span class="rec-title">${r.title}</span>
        <span class="badge ${r.priority}">${r.priority}</span>
      </div>
      <div class="rec-detail"><strong>${r.agent}:</strong> ${r.detail}</div>
    </div>`).join('') || '<p class="loading-note">No recommendations right now.</p>';
}

function refreshAll() {
  loadSummary();
  loadCostDistribution();
  loadCostTrend();
  loadRanking();
  loadBudgetCompliance();
  loadRecommendations();
}

downloadReportBtn.addEventListener('click', () => {
  const url = `/api/executive/report${qs() ? '?' + qs() : ''}`;
  window.location.href = url;
});

facilitySelect.addEventListener('change', refreshAll);
refreshAll();
setInterval(refreshAll, 60000);
