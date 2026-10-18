(function () {
  'use strict';

  function applyNasoraChartTheme() {
    if (!window.Chart) return;

    var C = {
      primary: '#167a56',
      primarySoft: 'rgba(22,122,86,0.14)',
      secondary: '#356f8a',
      secondarySoft: 'rgba(53,111,138,0.14)',
      accent: '#806548',
      warning: '#b87916',
      danger: '#b34d4b',
      neutral: '#87958f',
      grid: 'rgba(31,51,44,0.08)',
      text: '#53645e'
    };

    Chart.defaults.color = C.text;
    Chart.defaults.font.family = "Inter, Poppins, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.legend.labels.padding = 16;
    Chart.defaults.plugins.tooltip.backgroundColor = '#20352d';
    Chart.defaults.plugins.tooltip.titleColor = '#ffffff';
    Chart.defaults.plugins.tooltip.bodyColor = '#eef5f1';
    Chart.defaults.plugins.tooltip.borderColor = 'rgba(255,255,255,0.12)';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.displayColors = true;
    Chart.defaults.animation.duration = 0;
    Chart.defaults.animation.animateRotate = false;
    Chart.defaults.animation.animateScale = false;

    if (Chart.defaults.scale) {
      Chart.defaults.scale.grid.color = C.grid;
      Chart.defaults.scale.grid.drawBorder = false;
      Chart.defaults.scale.ticks.color = C.text;
      Chart.defaults.scale.ticks.padding = 6;
    }

    var palette = [C.primary, C.secondary, C.accent, C.warning, '#657d75', '#9b8a70', '#4e9a80', '#718b84'];

    Chart.register({
      id: 'nasoraProfessionalPalette',
      beforeUpdate: function (chart) {
        var datasets = chart.data && chart.data.datasets ? chart.data.datasets : [];
        datasets.forEach(function (dataset, index) {
          var color = palette[index % palette.length];
          var type = chart.config.type;

          if (type === 'doughnut' || type === 'pie' || type === 'polarArea') {
            if (!dataset.backgroundColor) {
              dataset.backgroundColor = palette.slice(0, Math.max(2, chart.data.labels ? chart.data.labels.length : 2));
            }
            if (!dataset.borderColor) dataset.borderColor = '#ffffff';
            if (dataset.borderWidth == null) dataset.borderWidth = 2;
          } else if (type === 'line') {
            if (!dataset.borderColor) dataset.borderColor = color;
            if (!dataset.backgroundColor) dataset.backgroundColor = index === 0 ? C.primarySoft : C.secondarySoft;
            if (!dataset.pointBackgroundColor) dataset.pointBackgroundColor = dataset.borderColor;
            if (!dataset.pointBorderColor) dataset.pointBorderColor = '#ffffff';
            if (dataset.pointBorderWidth == null) dataset.pointBorderWidth = 2;
            if (dataset.pointRadius == null) dataset.pointRadius = 3;
            if (dataset.pointHoverRadius == null) dataset.pointHoverRadius = 5;
            if (dataset.borderWidth == null) dataset.borderWidth = 2.5;
            if (dataset.tension == null) dataset.tension = 0.28;
            if (dataset.fill == null) dataset.fill = index === 0;
          } else {
            if (!dataset.backgroundColor) dataset.backgroundColor = color;
            if (!dataset.borderColor) dataset.borderColor = color;
            if (dataset.borderWidth == null) dataset.borderWidth = 0;
            if (dataset.borderRadius == null) dataset.borderRadius = 5;
            if (dataset.borderSkipped == null) dataset.borderSkipped = false;
          }
        });
      }
    });
  }

  function initAdminDashboardCharts() {
    if (!window.Chart) return;
    var lineCanvas = document.getElementById('globalSalesChart');
    var divisionCanvas = document.getElementById('divisionChart');
    if (!lineCanvas && !divisionCanvas) return;

    fetch('/admin_dashboard_chart_data', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) throw new Error('Chart data unavailable');
        return response.json();
      })
      .then(function (data) {
        var labels = Array.isArray(data.labels) ? data.labels : [];
        var totals = Array.isArray(data.totals) ? data.totals.map(Number) : [];
        var divisions = data.divisions || {};

        if (lineCanvas && labels.length && totals.length) {
          new Chart(lineCanvas.getContext('2d'), {
            type: 'line',
            data: {
              labels: labels.map(function (label) { return String(label).slice(0, 7); }),
              datasets: [{ label: 'CA total', data: totals, fill: true }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              interaction: { mode: 'index', intersect: false },
              plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (ctx) { return ' ' + Number(ctx.parsed.y || 0).toLocaleString('fr-FR', { maximumFractionDigits: 2 }) + ' €'; } } } },
              scales: { y: { beginAtZero: true, ticks: { callback: function (value) { return Number(value).toLocaleString('fr-FR') + ' €'; } } }, x: { grid: { display: false } } }
            }
          });
        }

        if (divisionCanvas && (Number(divisions.nasmedic || 0) || Number(divisions.nasderm || 0))) {
          new Chart(divisionCanvas.getContext('2d'), {
            type: 'doughnut',
            data: { labels: ['NASMEDIC', 'NASDERM'], datasets: [{ data: [Number(divisions.nasmedic || 0), Number(divisions.nasderm || 0)] }] },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              cutout: '64%',
              plugins: {
                legend: { position: 'bottom' },
                tooltip: { callbacks: { label: function (ctx) { return ' ' + ctx.label + ' : ' + Number(ctx.parsed || 0).toLocaleString('fr-FR', { maximumFractionDigits: 2 }) + ' €'; } } }
              }
            }
          });
        }
      })
      .catch(function (error) {
        console.warn('NASORA charts:', error.message);
      });
  }


  function syncChartsWithTheme() {
    if (!window.Chart) return;
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    var text = dark ? '#edf5ef' : '#53645e';
    var grid = dark ? 'rgba(220,239,226,0.18)' : 'rgba(31,51,44,0.08)';
    var tooltipBg = dark ? '#101812' : '#20352d';
    var border = dark ? '#202a24' : '#ffffff';
    Chart.defaults.color = text;
    Chart.defaults.scale.grid.color = grid;
    Chart.defaults.scale.ticks.color = text;
    Chart.defaults.plugins.legend.labels.color = text;
    Chart.defaults.plugins.tooltip.backgroundColor = tooltipBg;
    Chart.defaults.plugins.tooltip.titleColor = '#ffffff';
    Chart.defaults.plugins.tooltip.bodyColor = '#ffffff';
    Chart.defaults.plugins.tooltip.borderColor = dark ? '#52675a' : 'rgba(255,255,255,0.12)';
    Object.keys(Chart.instances || {}).forEach(function (key) {
      var chart = Chart.instances[key];
      if (!chart || !chart.options) return;
      chart.options.color = text;
      if (chart.options.scales) {
        Object.keys(chart.options.scales).forEach(function (axis) {
          var scale = chart.options.scales[axis];
          if (scale.ticks) scale.ticks.color = text;
          if (scale.grid) scale.grid.color = grid;
        });
      }
      if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
        chart.options.plugins.legend.labels.color = text;
      }
      if (chart.options.plugins && chart.options.plugins.tooltip) {
        chart.options.plugins.tooltip.backgroundColor = tooltipBg;
        chart.options.plugins.tooltip.titleColor = '#ffffff';
        chart.options.plugins.tooltip.bodyColor = '#ffffff';
        chart.options.plugins.tooltip.borderColor = dark ? '#52675a' : 'rgba(255,255,255,0.12)';
      }
      (chart.data.datasets || []).forEach(function (dataset) {
        if (dataset.pointBorderColor === '#ffffff' || dataset.pointBorderColor == null) dataset.pointBorderColor = border;
        if (dataset.borderColor === '#ffffff' && dark) dataset.borderColor = '#202a24';
      });
      chart.update('none');
    });
  }

  window.addEventListener('nasora:themechange', syncChartsWithTheme);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncChartsWithTheme);
  } else {
    syncChartsWithTheme();
  }

  function boot() {
    var lineCanvas = document.getElementById('globalSalesChart');
    var divisionCanvas = document.getElementById('divisionChart');
    if (!lineCanvas && !divisionCanvas) return;

    var start = window.requestIdleCallback || function (callback) { window.setTimeout(callback, 0); };
    var schedule = function () {
      start(function () {
        applyNasoraChartTheme();
        initAdminDashboardCharts();
      }, { timeout: 1200 });
    };

    if (!('IntersectionObserver' in window)) {
      schedule();
      return;
    }

    var observed = lineCanvas || divisionCanvas;
    var observer = new IntersectionObserver(function (entries) {
      if (entries.some(function (entry) { return entry.isIntersecting; })) {
        observer.disconnect();
        schedule();
      }
    }, { rootMargin: '240px' });

    observer.observe(observed);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
