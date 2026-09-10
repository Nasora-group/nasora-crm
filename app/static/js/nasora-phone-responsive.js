/* NASORA - transforme les numéros de téléphone affichés dans les tableaux en liens d'appel */
(function () {
  'use strict';

  function normalizePhone(value) {
    var raw = (value || '').trim();
    if (!raw) return null;
    var cleaned = raw.replace(/[\u00a0\s().-]/g, '');
    if (cleaned.charAt(0) === '+') {
      return /^\+\d{7,15}$/.test(cleaned) ? cleaned : null;
    }
    if (/^\d{7,15}$/.test(cleaned)) {
      return cleaned;
    }
    return null;
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
      if (!phone) return;

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

  function normalize(value) {
    return (value || '').toString().trim().toLocaleLowerCase('fr').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function completeProspectionTable() {
    var page = document.querySelector('.direction-dashboard-page');
    if (!page) return;

    var tables = Array.from(page.querySelectorAll('table.responsive-table'));
    var table = tables.find(function (candidate) {
      var headers = Array.from(candidate.querySelectorAll('thead th')).map(function (th) { return normalize(th.textContent); });
      return headers.indexOf('date') !== -1 && headers.indexOf('commercial') !== -1 && headers.indexOf('produits prescrits') !== -1;
    });
    if (!table || table.dataset.completeProspectionTable === 'true') return;

    var params = new URLSearchParams(window.location.search);
    params.delete('page');
    var url = '/admin/prospections/data' + (params.toString() ? '?' + params.toString() : '');

    fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) throw new Error('Impossible de charger les détails des prospections.');
        return response.json();
      })
      .then(function (payload) {
        var items = Array.isArray(payload.items) ? payload.items : [];
        var pageNumber = parseInt(new URLSearchParams(window.location.search).get('page') || '1', 10);
        if (!Number.isFinite(pageNumber) || pageNumber < 1) pageNumber = 1;
        var pageSize = table.querySelectorAll('tbody tr').length || 25;
        if (pageSize > 25) pageSize = 25;
        var start = (pageNumber - 1) * pageSize;
        var pageItems = items.slice(start, start + pageSize);

        var headers = [
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

        var thead = table.querySelector('thead');
        var tbody = table.querySelector('tbody');
        if (!thead || !tbody) return;

        var headerRow = thead.querySelector('tr');
        if (!headerRow) return;
        headerRow.innerHTML = '';
        headers.forEach(function (label) {
          var th = document.createElement('th');
          th.textContent = label;
          headerRow.appendChild(th);
        });

        tbody.innerHTML = '';
        if (!pageItems.length) {
          var emptyRow = document.createElement('tr');
          var emptyCell = document.createElement('td');
          emptyCell.colSpan = headers.length;
          emptyCell.className = 'muted';
          emptyCell.textContent = 'Aucune prospection trouvée.';
          emptyRow.appendChild(emptyCell);
          tbody.appendChild(emptyRow);
        } else {
          pageItems.forEach(function (item) {
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
              if (index === 0) {
                var strong = document.createElement('strong');
                strong.textContent = value;
                cell.appendChild(strong);
              } else if (index === 1 || index === 3) {
                var strongName = document.createElement('strong');
                strongName.textContent = value;
                cell.appendChild(strongName);
              } else {
                cell.textContent = value;
              }
              if (index === 8) cell.className = 'nowrap';
              if (index >= 9) cell.style.whiteSpace = 'pre-wrap';
              row.appendChild(cell);
            });
            tbody.appendChild(row);
          });
        }

        table.classList.add('prospection-complete-table');
        table.style.minWidth = '1500px';
        table.dataset.completeProspectionTable = 'true';
        enhancePhones();
      })
      .catch(function (error) {
        console.warn('[NASORA] ' + error.message);
      });
  }

  function formatDate(value) {
    if (!value) return '—';
    var parts = value.split('-');
    return parts.length === 3 ? parts[2] + '/' + parts[1] + '/' + parts[0] : value;
  }

  document.addEventListener('DOMContentLoaded', function () {
    enhancePhones();
    completeProspectionTable();
  });
})();
