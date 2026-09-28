const facilitySelect = document.getElementById('facilitySelect');
const monthsSelect = document.getElementById('monthsSelect');
let trendChart, breakdownChart, rankingChart, complianceChart;

const CHART_TEXT = '#7A8494';
const CHART_GRID = 'rgba(20,30,45,0.06)';
const BREAKDOWN_COLORS = ['#2E86C1', '#1F9D6B', '#D9720C', '#D64545', '#8E44AD', '#16A085', '#F1C40F', '#7A8494'];

function chartJsReady() {
  return typeof Chart !== 'undefined' && !window.__chartJsUnavailable;
}

function qs() {
  const params = new URLSearchParams();
  if (facilitySelect.value) params.set('facility_id', facilitySelect.value);
  params.set('months', monthsSelect.value);
  return params.toString();
}

function fmtMoney(n) {
  if (n === undefined || n === null) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e7) return (n / 1e7).toFixed(2) + 'Cr';
  if (abs >= 1e5) return (n / 1e5).toFixed(2) + 'L';
  if (abs >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toLocaleString();
}

async function loadSummary() {
  const res = await fetch(`/api/cost/summary?${qs()}`);
  const d = await res.json();
  document.getElementById('kpiCost').textContent = fmtMoney(d.total_operational_cost);
  document.getElementById('kpiSavings').textContent = fmtMoney(d.potential_savings);
  document.getElementById('kpiReduction').innerHTML = `${d.cost_reduction_pct ?? 0}<span class="unit">%</span>`;
  document.getElementById('kpiRoi').innerHTML = `${d.roi_generated_pct ?? 0}<span class="unit">%</span>`;
}

async function loadTrend() {
  const res = await fetch(`/api/cost/trend?${qs()}`);
  const d = await res.json();
  const ctx = document.getElementById('trendChart');
  if (!chartJsReady()) return;
  if (trendChart) trendChart.destroy();
  trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: d.labels || [],
      datasets: [
        { label: 'Operational Cost', data: d.operational_cost || [], borderColor: '#D9720C', backgroundColor: 'rgba(217,114,12,0.08)', tension: 0.3, fill: true },
        { label: 'Budget Allocated', data: d.budget_allocated || [], borderColor: '#2E86C1', backgroundColor: 'rgba(46,134,193,0.06)', tension: 0.3, fill: true },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { color: CHART_TEXT, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: CHART_TEXT, font: { size: 10 } }, grid: { color: CHART_GRID } },
      },
    },
  });
}

async function loadBreakdown() {
  const res = await fetch(`/api/cost/breakdown?${qs()}`);
  const d = await res.json();
  const entries = Object.entries(d).sort((a, b) => b[1] - a[1]);
  document.getElementById('costBreakdown').innerHTML = entries.map(([label, pct], i) => `
    <div class="bar-row">
      <div class="bar-label"><span>${label}</span><span>${pct}%</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%; background:${BREAKDOWN_COLORS[i % BREAKDOWN_COLORS.length]};"></div></div>
    </div>`).join('') || '<p class="loading-note">No data.</p>';

  const ctx = document.getElementById('breakdownChart');
  if (!chartJsReady() || !entries.length) return;
  if (breakdownChart) breakdownChart.destroy();
  breakdownChart = new Chart(ctx, {
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
      plugins: { legend: { position: 'bottom', labels: { color: CHART_TEXT, font: { size: 10.5 }, boxWidth: 10 } } },
    },
  });
}

async function loadRanking() {
  const res = await fetch(`/api/cost/ranking?months=${monthsSelect.value}`);
  const d = await res.json();
  const body = document.getElementById('rankingTable');
  if (!d.length) {
    body.innerHTML = '<tr><td colspan="5" class="loading-note">No data.</td></tr>';
    return;
  }
  body.innerHTML = d.map(r => `
    <tr>
      <td>${r.facility_id}</td>
      <td>${r.facility_type}</td>
      <td>${fmtMoney(r.potential_savings)}</td>
      <td><span class="badge ${r.over_budget ? 'High' : 'Low'}">${fmtMoney(r.cost_variance)}</span></td>
      <td>${r.avg_roi_pct}%</td>
    </tr>`).join('');

  const top8 = d.slice(0, 8);
  const ctx = document.getElementById('rankingChart');
  if (!chartJsReady() || !top8.length) return;
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

async function loadVendor() {
  const res = await fetch(`/api/cost/vendor?${qs()}`);
  const d = await res.json();
  if (!d || Object.keys(d).length === 0) {
    document.getElementById('vendorPanel').innerHTML = '<p class="loading-note">No data.</p>';
    return;
  }
  document.getElementById('vendorPanel').innerHTML = `
    <div class="bar-row"><div class="bar-label"><span>Total Vendor Spend</span><span>${fmtMoney(d.total_vendor_cost)}</span></div></div>
    <div class="bar-row"><div class="bar-label"><span>Avg Active Vendors / Period</span><span>${d.avg_active_vendors}</span></div></div>
    <div class="bar-row"><div class="bar-label"><span>Avg Cost per Vendor</span><span>${fmtMoney(d.avg_cost_per_vendor)}</span></div></div>
    <div class="bar-row"><div class="bar-label"><span>Consolidation Opportunities</span><span>${d.consolidation_opportunities}</span></div></div>
  `;
}

async function loadBudgetCompliance() {
  const res = await fetch(`/api/cost/budget-compliance?${qs()}`);
  const d = await res.json();
  document.getElementById('complianceTag').textContent = `${d.compliance_pct ?? 0}% COMPLIANT`;
  const body = document.getElementById('varianceTable');
  if (!d.worst_variance_periods || !d.worst_variance_periods.length) {
    body.innerHTML = '<tr><td colspan="3" class="loading-note">No over-budget periods found.</td></tr>';
  } else {
    body.innerHTML = d.worst_variance_periods.map(v => `
      <tr>
        <td>${v.facility_id}</td>
        <td>${v.month}</td>
        <td><span class="badge ${v.variance < 0 ? 'Critical' : 'Low'}">${fmtMoney(v.variance)}</span></td>
      </tr>`).join('');
  }

  const ctx = document.getElementById('complianceChart');
  if (!chartJsReady() || d.periods_within_budget === undefined) return;
  if (complianceChart) complianceChart.destroy();
  complianceChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Within Budget', 'Over Budget'],
      datasets: [{
        data: [d.periods_within_budget ?? 0, d.periods_over_budget ?? 0],
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

async function loadRecommendations() {
  const res = await fetch(`/api/cost/recommendations?${qs()}`);
  const d = await res.json();
  document.getElementById('recCountTag').textContent = `${d.length} RECOMMENDATIONS`;
  document.getElementById('recommendations').innerHTML = d.map(r => `
    <div class="rec">
      <div class="rec-head">
        <span class="rec-title">${r.title}</span>
        <span class="badge ${r.priority}">${r.priority}</span>
      </div>
      <div class="rec-detail">${r.detail}</div>
      <div class="rec-savings">Flagged ${r.occurrences}x · Est. savings: ${fmtMoney(r.est_savings)}</div>
    </div>`).join('') || '<p class="loading-note">No recommendations for this selection.</p>';
}

function refreshAll() {
  loadSummary();
  loadTrend();
  loadBreakdown();
  loadRanking();
  loadVendor();
  loadBudgetCompliance();
  loadRecommendations();
}

facilitySelect.addEventListener('change', refreshAll);
monthsSelect.addEventListener('change', refreshAll);
refreshAll();
setInterval(refreshAll, 60000);
