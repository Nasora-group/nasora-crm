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

  document.addEventListener('DOMContentLoaded', enhancePhones);
})();
