/* NASORA CRM — bascule clair/sombre, préférence locale au navigateur */
(function () {
  'use strict';
  function initThemeToggle() {
    var button = document.getElementById('nasora-theme-toggle');
    if (!button) return;
    var root = document.documentElement;
    var icon = button.querySelector('.nasora-theme-icon');
    var label = button.querySelector('.nasora-theme-label');
    function isDark() { return root.getAttribute('data-theme') === 'dark'; }
    function render() {
      var dark = isDark();
      button.setAttribute('aria-pressed', dark ? 'true' : 'false');
      button.setAttribute('aria-label', dark ? 'Activer le mode clair' : 'Activer le mode sombre');
      button.setAttribute('title', dark ? 'Activer le mode clair' : 'Activer le mode sombre');
      if (icon) icon.textContent = dark ? '☀' : '☾';
      if (label) label.textContent = dark ? 'Mode clair' : 'Mode sombre';
    }
    button.addEventListener('click', function () {
      var dark = !isDark();
      if (dark) root.setAttribute('data-theme', 'dark');
      else root.removeAttribute('data-theme');
      try { localStorage.setItem('nasora_theme', dark ? 'dark' : 'light'); } catch (e) {}
      render();
      try { window.dispatchEvent(new CustomEvent('nasora:themechange', { detail: { theme: dark ? 'dark' : 'light' } })); } catch (e) {}
    });
    render();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initThemeToggle);
  else initThemeToggle();
}());
