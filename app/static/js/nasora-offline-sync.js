/* NASORA CRM: encrypted queue and idempotent reconnection sync. */
(function () {
  "use strict";
  if (!("indexedDB" in window) || !window.crypto || !window.crypto.subtle || !window.fetch) return;

  const DB_NAME = "nasora-offline-drafts-v1";
  const STORE = "drafts";
  const KEY_ID = "device-key-v1";
  let dbPromise;

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        if (!req.result.objectStoreNames.contains(STORE)) req.result.createObjectStore(STORE);
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return dbPromise;
  }

  async function get(key) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const req = tx.objectStore(STORE).get(key);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function removeKeys(keys) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      keys.forEach(key => tx.objectStore(STORE).delete(key));
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  }

  async function deviceKey() {
    let key = await get(KEY_ID);
    if (key) return key;
    key = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
    const db = await openDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).put(key, KEY_ID);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    return key;
  }

  async function encrypt(value) {
    const key = await deviceKey();
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const clear = new TextEncoder().encode(JSON.stringify(value));
    const cipher = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, clear);
    return { iv: Array.from(iv), data: Array.from(new Uint8Array(cipher)) };
  }

  async function decrypt(record) {
    const key = await deviceKey();
    const clear = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: new Uint8Array(record.iv) },
      key,
      new Uint8Array(record.data)
    );
    return JSON.parse(new TextDecoder().decode(clear));
  }

  function draftKey(form) {
    return form.dataset.offlineDraft + ":" + form.dataset.userId;
  }

  function queueKey(form) {
    return draftKey(form) + ":pending-sync";
  }

  function setNotice(notice, message) {
    if (notice.firstChild && notice.firstChild.nodeType === 3) notice.firstChild.textContent = message;
    else notice.textContent = message;
  }

  function field(form, name) {
    const item = form.elements.namedItem(name);
    return item ? item.value : "";
  }

  function selected(form, name) {
    const item = form.elements.namedItem(name);
    if (!item) return [];
    return item.tagName === "SELECT" && item.multiple
      ? Array.from(item.selectedOptions).map(option => option.value)
      : (item.value ? [item.value] : []);
  }

  function submission(form) {
    const kind = form.dataset.offlineDraft;
    if (kind === "planning-week") {
      const slots = {};
      ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"].forEach(day => {
        const select = form.querySelector('select[name="' + day + '"]');
        slots[day] = select ? Array.from(select.selectedOptions).map(option => {
          const slug = option.value.replace(/ /g, "_");
          return { structure: option.value, name: field(form, day + "_nom__" + slug).trim() };
        }) : [];
      });
      return { url: "/api/offline-sync/planning", redirect: "/visualiser_planning", payload: { date: field(form, "date"), slots } };
    }
    if (kind === "prospection-create") {
      const hors = form.elements.namedItem("hors_planning");
      return {
        url: "/api/offline-sync/prospection",
        redirect: "/dashboard/prospections",
        payload: {
          date: field(form, "date"),
          nom_client: field(form, "nom_client"),
          specialite: field(form, "specialite"),
          structure: field(form, "structure"),
          establishment: field(form, "nom_structure"),
          telephone: field(form, "telephone"),
          zone: field(form, "zone"),
          region: field(form, "region"),
          address: field(form, "address"),
          profils_prospect: field(form, "profils_prospect"),
          produits_presentes: selected(form, "produits_presentes"),
          produits_prescrits: selected(form, "produits_prescrits"),
          hors_planning: !!(hors && hors.checked)
        }
      };
    }
    if (kind === "animation-sales") {
      const items = [];
      form.querySelectorAll('input[name^="quantity__"]').forEach(input => {
        const quantity = Number(input.value);
        if (!Number.isFinite(quantity) || quantity <= 0) return;
        const product = input.name.slice("quantity__".length);
        items.push({ product_name: product, quantity: input.value, unit_price: field(form, "unit_price__" + product) });
      });
      return {
        url: "/animations/ventes/api/offline-sync",
        redirect: "/animations/ventes/historique",
        payload: { pharmacy_name: field(form, "pharmacy_name"), animation_date: field(form, "animation_date"), items }
      };
    }
    return null;
  }

  function uuid() {
    if (crypto.randomUUID) return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const hex = Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
    return hex.slice(0, 8) + "-" + hex.slice(8, 12) + "-" + hex.slice(12, 16) + "-" + hex.slice(16, 20) + "-" + hex.slice(20);
  }

  async function pendingFor(form, requestData) {
    const stored = await get(queueKey(form));
    if (stored) return decrypt(stored);
    const pending = {
      url: requestData.url,
      redirect: requestData.redirect,
      payload: Object.assign({}, requestData.payload, { submission_id: uuid() }),
      queuedAt: new Date().toISOString()
    };
    const db = await openDb();
    const encrypted = await encrypt(pending);
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).put(encrypted, queueKey(form));
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    return pending;
  }

  async function send(form, notice, pending) {
    if (!navigator.onLine) {
      setNotice(notice, "Saisie enregistrée en attente. Elle sera synchronisée automatiquement au retour du réseau.");
      return;
    }
    const csrf = form.querySelector('input[name="csrf_token"]');
    try {
      const response = await fetch(pending.url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf ? csrf.value : "" },
        body: JSON.stringify(pending.payload)
      });
      const contentType = response.headers.get("content-type") || "";
      if (response.redirected || !contentType.includes("application/json")) {
        setNotice(notice, "Votre session a peut-être expiré. Reconnectez-vous pour reprendre la synchronisation.");
        return;
      }
      const result = await response.json();
      if (response.ok && result.status === "synced") {
        await removeKeys([draftKey(form), queueKey(form)]);
        setNotice(notice, "Synchronisation terminée. Vos données sont enregistrées dans NASORA CRM.");
        window.location.assign(pending.redirect);
        return;
      }
      if (response.status >= 400 && response.status < 500) await removeKeys([queueKey(form)]);
      setNotice(notice, result.message || "Synchronisation impossible. Votre brouillon reste conservé sur cet appareil.");
    } catch (_) {
      setNotice(notice, "Connexion interrompue. La saisie reste chiffrée sur cet appareil et sera réessayée.");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("form[data-offline-draft][data-user-id]").forEach(form => {
      const requestData = submission(form);
      if (!requestData) return;
      let notice = form.previousElementSibling;
      if (!notice || !notice.classList.contains("nasora-offline-draft-notice")) {
        notice = document.createElement("div");
        notice.className = "nasora-offline-draft-notice";
        notice.setAttribute("role", "status");
        form.parentNode.insertBefore(notice, form);
      }
      form.addEventListener("submit", async event => {
        if (form.dataset.offlineDraft === "animation-sales") {
          const photo = form.querySelector('input[type="file"][name="animation_evidence"]');
          if (photo && photo.files && photo.files.length && navigator.onLine) return;
          if (photo && photo.files && photo.files.length && !navigator.onLine) {
            event.preventDefault();
            setNotice(notice, "La photo justificative nécessite une connexion. Retirez la photo pour mettre les ventes en attente, puis ajoutez-la depuis l’historique après reconnexion.");
            return;
          }
        }
        event.preventDefault();
        setNotice(notice, "Préparation de la synchronisation sécurisée…");
        try {
          const pending = await pendingFor(form, submission(form));
          await send(form, notice, pending);
        } catch (_) {
          setNotice(notice, "Impossible de préparer la synchronisation. Le brouillon local reste disponible.");
        }
      });
      window.addEventListener("online", async () => {
        try {
          const stored = await get(queueKey(form));
          if (stored) await send(form, notice, await decrypt(stored));
        } catch (_) {
          setNotice(notice, "La synchronisation sera réessayée. Votre saisie locale est conservée.");
        }
      });
      get(queueKey(form)).then(async stored => {
        if (stored && navigator.onLine) await send(form, notice, await decrypt(stored));
      }).catch(() => {});
    });
  });
})();
