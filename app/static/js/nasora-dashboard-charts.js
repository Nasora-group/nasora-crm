(function () {
  'use strict';

  function applyNasoraChartTheme() {
    if (!window.Chart) return;

    var C = {
      primary: '#167a56',
      primarySoft: 'rgba(22,122,86,0.16)',
      secondary: '#3b7f72',
      secondarySoft: 'rgba(59,127,114,0.16)',
      accent: '#8b6f47',
      warning: '#c98518',
      danger: '#b94a48',
      neutral: '#87958f',
      grid: 'rgba(31,51,44,0.09)',
      text: '#53645e'
    };

    Chart.defaults.color = C.text;
    Chart.defaults.font.family = "Inter, Poppins, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.legend.labels.padding = 18;
    Chart.defaults.plugins.tooltip.backgroundColor = '#20352d';
    Chart.defaults.plugins.tooltip.titleColor = '#ffffff';
    Chart.defaults.plugins.tooltip.bodyColor = '#eef5f1';
    Chart.defaults.plugins.tooltip.borderColor = 'rgba(255,255,255,0.12)';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.animation.duration = 0;

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
          if (chart.config.type === 'doughnut' || chart.config.type === 'pie' || chart.config.type === 'polarArea') {
            if (!Array.isArray(dataset.backgroundColor)) {
              dataset.backgroundColor = palette.slice(0, Math.max(2, chart.data.labels ? chart.data.labels.length : 2));
            }
            dataset.borderColor = '#ffffff';
            dataset.borderWidth = 2;
          } else if (chart.config.type === 'line') {
            dataset.borderColor = color;
            dataset.backgroundColor = index === 0 ? C.primarySoft : C.secondarySoft;
            dataset.pointBackgroundColor = color;
            dataset.pointBorderColor = '#ffffff';
            dataset.pointBorderWidth = 2;
            dataset.pointRadius = 3;
            dataset.pointHoverRadius = 5;
            dataset.borderWidth = 2.5;
            dataset.tension = 0.28;
            dataset.fill = index === 0;
          } else {
            dataset.backgroundColor = color;
            dataset.borderColor = color;
            dataset.borderWidth = 0;
            dataset.borderRadius = 5;
            dataset.borderSkipped = false;
          }
        });
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyNasoraChartTheme);
  } else {
    applyNasoraChartTheme();
  }
})();
