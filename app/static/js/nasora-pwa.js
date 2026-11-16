(function () {
  "use strict";
  var indicator = document.getElementById("nasora-connectivity");
  function updateConnectivity() {
    if (!indicator) return;
    if (navigator.onLine) {
      indicator.hidden = true;
      indicator.textContent = "";
      indicator.classList.remove("is-offline");
    } else {
      indicator.hidden = false;
      indicator.classList.add("is-offline");
      indicator.textContent = "Hors connexion. Le mode de saisie et de synchronisation hors ligne sera activé progressivement. N'effectuez pas de nouvelle saisie tant que cette fonction n'est pas disponible.";
    }
  }
  window.addEventListener("online", updateConnectivity);
  window.addEventListener("offline", updateConnectivity);
  updateConnectivity();
  if ("serviceWorker" in navigator && window.location.protocol === "https:") {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function (error) {
        console.error("NASORA PWA: enregistrement du service worker impossible", error);
      });
    });
  }
}());
