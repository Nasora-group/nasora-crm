/* NASORA CRM encrypted offline form drafts.
 * Drafts stay on this device and are never submitted automatically.
 * Files/photos and CSRF tokens are deliberately excluded.
 */
(function () {
  "use strict";
  if (!("indexedDB" in window) || !window.crypto || !window.crypto.subtle) return;

  const DB_NAME = "nasora-offline-drafts-v1";
  const STORE = "drafts";
  const KEY_ID = "device-key-v1";
  let dbPromise;

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    return dbPromise;
  }

  async function storeGet(key) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const req = tx.objectStore(STORE).get(key);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function storePut(key, value) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).put(value, key);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  }

  async function getDeviceKey() {
    let key = await storeGet(KEY_ID);
    if (key) return key;
    key = await crypto.subtle.generateKey(
      { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]
    );
    await storePut(KEY_ID, key);
    return key;
  }

  function draftKey(form) {
    return [form.dataset.offlineDraft, form.dataset.userId].join(":");
  }

  function queuePrefix(form) {
    return draftKey(form) + ":pending-sync:";
  }

  function collect(form) {
    const values = [];
    for (const element of form.elements) {
      if (!element.name || element.disabled ||
          ["password", "file", "submit", "button"].includes(element.type) ||
          ["csrf_token", "csrfmiddlewaretoken"].includes(element.name)) continue;
      if (element.type === "radio" || element.type === "checkbox") {
        if (element.checked) values.push([element.name, element.value, element.type]);
      } else if (element.tagName === "SELECT" && element.multiple) {
        for (const option of element.selectedOptions) values.push([element.name, option.value, "multi"]);
      } else {
        values.push([element.name, element.value, "value"]);
      }
    }
    return values;
  }

  function apply(form, values) {
    const controls = Array.from(form.elements);
    for (const [name, value, kind] of values) {
      const matching = controls.filter(el => el.name === name);
      if (kind === "multi") {
        const el = matching.find(item => item.tagName === "SELECT" && item.multiple);
        if (el) Array.from(el.options).forEach(option => { option.selected = option.value === value; });
      } else if (kind === "radio" || kind === "checkbox") {
        const el = matching.find(item => item.type === kind && item.value === value);
        if (el) el.checked = true;
      } else {
        const el = matching.find(item => !["file", "submit", "button"].includes(item.type));
        if (el) el.value = value;
      }
    }
    controls.filter(el => el.tagName === "SELECT" && el.multiple).forEach(el => el.dispatchEvent(new Event("change", { bubbles: true })));
  }

  async function save(form) {
    const key = await getDeviceKey();
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const payload = new TextEncoder().encode(JSON.stringify({
      savedAt: new Date().toISOString(), values: collect(form)
    }));
    const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, payload);
    await storePut(draftKey(form), { iv: Array.from(iv), data: Array.from(new Uint8Array(ciphertext)) });
    form.dataset.draftSaved = "true";
    form.dispatchEvent(new CustomEvent("nasora:draft-saved"));
  }

  async function restore(form) {
    const record = await storeGet(draftKey(form));
    if (!record) return;
    const key = await getDeviceKey();
    const clear = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: new Uint8Array(record.iv) },
      key, new Uint8Array(record.data)
    );
    const draft = JSON.parse(new TextDecoder().decode(clear));
    apply(form, draft.values || []);
    form.dataset.draftRestored = "true";
    form.dispatchEvent(new CustomEvent("nasora:draft-restored", { detail: { savedAt: draft.savedAt } }));
  }

  async function remove(form) {
    const db = await openDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      const store = tx.objectStore(STORE);
      store.delete(draftKey(form));
      const keysRequest = store.getAllKeys();
      keysRequest.onsuccess = () => {
        keysRequest.result.forEach(key => {
          if (typeof key === "string" && key.startsWith(queuePrefix(form))) store.delete(key);
        });
      };
      keysRequest.onerror = () => reject(keysRequest.error);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    delete form.dataset.draftSaved;
    delete form.dataset.draftRestored;
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("form[data-offline-draft][data-user-id]").forEach(form => {
      const notice = document.createElement("div");
      notice.className = "nasora-offline-draft-notice";
      notice.setAttribute("role", "status");
      notice.style.cssText = "margin:10px 0;padding:10px 12px;border:1px solid #d5e5db;border-radius:8px;background:#f4faf6;color:#24543a;font-size:.9rem";
      notice.textContent = "Les modifications seront conservées localement sur cet appareil. Les photos ne sont pas sauvegardées et aucun envoi automatique n'est effectué.";
      const clear = document.createElement("button");
      clear.type = "button";
      clear.textContent = "Effacer le brouillon local";
      clear.style.cssText = "margin-left:10px;border:0;background:transparent;color:inherit;text-decoration:underline;cursor:pointer;font:inherit";
      clear.addEventListener("click", () => remove(form).then(() => { notice.textContent = "Brouillon local effacé."; }).catch(() => {}));
      notice.appendChild(clear);
      form.parentNode.insertBefore(notice, form);
      let timer;
      const scheduleSave = () => {
        clearTimeout(timer);
        timer = setTimeout(() => save(form).catch(() => {}), 350);
      };
      form.addEventListener("nasora:draft-saved", () => { notice.firstChild.textContent = "Brouillon chiffré enregistré sur cet appareil. Photos exclues, aucun envoi automatique."; });
      form.addEventListener("nasora:draft-restored", () => { notice.firstChild.textContent = "Brouillon local restauré. Vérifiez les informations avant de soumettre."; });
      form.addEventListener("input", scheduleSave);
      form.addEventListener("change", scheduleSave);
      restore(form).catch(() => {});
      const clearButton = form.querySelector("[data-clear-offline-draft]");
      if (clearButton) clearButton.addEventListener("click", () => remove(form).catch(() => {}));
    });
  });
})();