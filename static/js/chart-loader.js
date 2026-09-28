/**
 * Resilient Chart.js loader.
 *
 * Some networks (corporate/school firewalls, certain antivirus products,
 * some ad/asset blockers) block individual CDN domains. If Chart.js fails
 * to load, every canvas on the page silently stays blank while the rest of
 * the dashboard (which doesn't depend on Chart.js) keeps working — which
 * is a confusing failure mode. This loader tries several CDNs in sequence
 * and only starts the page's own chart-drawing script once Chart.js has
 * actually loaded, or shows a visible banner if every source fails.
 */
(function () {
  var CDN_SOURCES = [
    '/static/js/vendor/chart.umd.min.js',                                          // bundled locally — no network dependency
    'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js',       // fallback if the local file is ever missing
    'https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js',
    'https://unpkg.com/chart.js@4.4.4/dist/chart.umd.min.js',
  ];

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var el = document.createElement('script');
      el.src = src;
      el.onload = resolve;
      el.onerror = function () {
        reject(new Error('Failed to load ' + src));
      };
      document.head.appendChild(el);
    });
  }

  function tryLoadChart(index) {
    if (index >= CDN_SOURCES.length) {
      return Promise.reject(new Error('All Chart.js sources failed'));
    }
    return loadScript(CDN_SOURCES[index]).catch(function () {
      return tryLoadChart(index + 1);
    });
  }

  function showLoadErrorBanner() {
    var banner = document.createElement('div');
    banner.style.cssText =
      'background:#FDEDEC;border:1px solid #F5B7B1;color:#943126;' +
      'padding:12px 18px;border-radius:8px;margin-bottom:20px;font-family:sans-serif;font-size:13.5px;';
    banner.textContent =
      'Charts could not load — every chart library source was blocked by this network. ' +
      'The numbers and tables above are still accurate; only the visual charts are affected. ' +
      'Try a different network, or open your browser console (F12) for details.';
    var main = document.querySelector('main.main');
    if (main) main.insertBefore(banner, main.firstChild);
  }

  window.loadDashboardScriptAfterChart = function (dashboardScriptSrc) {
    tryLoadChart(0)
      .catch(function (err) {
        console.error(err);
        window.__chartJsUnavailable = true;
        showLoadErrorBanner();
      })
      .then(function () {
        // Always load the dashboard script, whether or not Chart.js loaded —
        // KPIs, tables, and bar-percentage displays don't depend on it.
        // The dashboard script checks window.__chartJsUnavailable before
        // calling into Chart.js so it degrades gracefully instead of
        // throwing and aborting everything else.
        return loadScript(dashboardScriptSrc);
      });
  };
})();
