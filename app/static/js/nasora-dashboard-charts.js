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

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyNasoraChartTheme);
  } else {
    applyNasoraChartTheme();
  }
})();
