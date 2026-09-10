/* NASORA - affichage complet des prospections + téléphones cliquables */
(function () {
  'use strict';

  function normalizePhone(value) {
    var raw = (value || '').trim();
    if (!raw) return null;
    var cleaned = raw.replace(/[\u00a0\s().-]/g, '');
    if (cleaned.charAt(0) === '+') {
      return /^\+\d{7,15}$/.test(cleaned) ? cleaned : null;
    }
    if (/^\d{7,15}$/.test(cleaned)) return cleaned;
    return null;
  }

  function normalize(value) {
    return (value || '').toString().trim().toLocaleLowerCase('fr').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function formatDate(value) {
    if (!value) return '—';
    var parts = value.split('-');
    return parts.length === 3 ? parts[2] + '/' + parts[1] + '/' + parts[0] : value;
  }

  function enhancePhones() {
    document.querySelectorAll('table td').forEach(function (cell) {
      if (cell.dataset.phoneCell === 'true') return;
      var label = (cell.getAttribute('data-label') || '').toLowerCase();
      if (!/(téléphone|telephone|tél|tel|mobile|portable)/i.test(label)) return;

      var existingLink = cell.querySelector('a[href^="tel:"]');
      if (existingLink) {
        existingLink.classList.add('phone-link');
        cell.dataset.phoneCell = 'true';
        return;
      }

      var text = cell.textContent.trim();
      var phone = normalizePhone(text);
      if (!phone || text === '—') return;

      cell.textContent = '';
      var link = document.createElement('a');
      link.href = 'tel:' + phone;
      link.className = 'phone-link';
      link.textContent = text;
      link.setAttribute('aria-label', 'Appeler ' + text);
      cell.appendChild(link);
      cell.dataset.phoneCell = 'true';
    });
  }

  function prospectionHeaders() {
    return [
      'Date',
      'Commercial',
      'Division',
      'Nom professionnel',
      'Spécialité',
      'Structure',
      "Nom de l'établissement",
      'Zone',
      'Téléphone',
      'Commentaires / compte-rendu',
      'Produits présentés',
      'Produits prescrits'
    ];
  }

  function setHeaders(table, headers) {
    var thead = table.querySelector('thead');
    var headerRow = thead && thead.querySelector('tr');
    if (!headerRow) return false;
    headerRow.innerHTML = '';
    headers.forEach(function (label) {
      var th = document.createElement('th');
      th.textContent = label;
      headerRow.appendChild(th);
    });
    return true;
  }

  function renderProspections(table, items, headers, limit) {
    var tbody = table.querySelector('tbody');
    if (!tbody) return;
    var rows = (items || []).slice(0, limit || items.length);
    tbody.innerHTML = '';

    if (!rows.length) {
      var emptyRow = document.createElement('tr');
      var emptyCell = document.createElement('td');
      emptyCell.colSpan = headers.length;
      emptyCell.className = 'muted';
      emptyCell.textContent = 'Aucune prospection trouvée.';
      emptyRow.appendChild(emptyCell);
      tbody.appendChild(emptyRow);
      return;
    }

    rows.forEach(function (item) {
      var row = document.createElement('tr');
      var values = [
        formatDate(item.date),
        item.commercial || '—',
        item.division || '—',
        item.nom_client || '—',
        item.specialite || '—',
        item.structure || '—',
        item.establishment || '—',
        item.zone || '—',
        item.telephone || '—',
        item.profils_prospect || '—',
        item.produits_presentes || '—',
        item.produits_prescrits || '—'
      ];

      values.forEach(function (value, index) {
        var cell = document.createElement('td');
        cell.setAttribute('data-label', headers[index]);
        cell.textContent = value;
        if (index === 0 || index === 1 || index === 3) cell.style.fontWeight = '700';
        if (index === 8) cell.classList.add('nowrap');
        if (index >= 9) cell.style.whiteSpace = 'pre-wrap';
        row.appendChild(cell);
      });
      tbody.appendChild(row);
    });
  }

  function fetchProspections(table, limit, markComplete) {
    var params = new URLSearchParams(window.location.search);
    params.delete('page');
    var url = '/admin/prospections/data' + (params.toString() ? '?' + params.toString() : '');

    return fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) throw new Error('Impossible de charger les détails des prospections.');
        return response.json();
      })
      .then(function (payload) {
        var items = Array.isArray(payload.items) ? payload.items : [];
        var headers = prospectionHeaders();
        if (!setHeaders(table, headers)) return;
        renderProspections(table, items, headers, limit);
        table.classList.add('prospection-complete-table');
        table.style.minWidth = '1700px';
        if (markComplete) table.dataset.completeProspectionTable = 'true';
        enhancePhones();
      });
  }

  function completeDashboardProspectionTable() {
    var page = document.querySelector('.direction-dashboard-page');
    if (!page) return;

    var tables = Array.from(page.querySelectorAll('table.responsive-table'));
    var table = tables.find(function (candidate) {
      var headers = Array.from(candidate.querySelectorAll('thead th')).map(function (th) { return normalize(th.textContent); });
      return headers.indexOf('date') !== -1 && headers.indexOf('commercial') !== -1 && headers.indexOf('produits prescrits') !== -1;
    });
    if (!table || table.dataset.completeProspectionTable === 'true') return;

    fetchProspections(table, 100, true).catch(function (error) {
      console.warn('[NASORA] ' + error.message);
    });
  }

  function completeExportProspectionTable() {
    var table = document.querySelector('table.sales-export-table');
    if (!table || table.dataset.completeProspectionTable === 'true') return;

    fetchProspections(table, 100, true).catch(function (error) {
      console.warn('[NASORA] ' + error.message);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    enhancePhones();
    completeDashboardProspectionTable();
    completeExportProspectionTable();
  });
})();
