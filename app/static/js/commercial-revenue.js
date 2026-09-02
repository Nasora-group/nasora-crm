document.addEventListener("DOMContentLoaded", async function () {
  const match = window.location.pathname.match(/^\/commercial_dashboard\/([^/]+)\/?$/);
  if (!match) return;

  const username = decodeURIComponent(match[1]);
  const sectionTitle = Array.from(document.querySelectorAll("h2")).find(function (el) {
    return (el.textContent || "").trim().toUpperCase().includes("TOUTES LES PROSPECTIONS");
  });
  if (!sectionTitle) return;

  const anchor = sectionTitle.closest(".section-heading") || sectionTitle;
  const card = document.createElement("section");
  card.className = "summary-card commercial-revenue-card";
  card.style.marginTop = "18px";
  card.innerHTML = `
    <div class="section-heading">
      <div>
        <span class="crm-overline">CHIFFRE D’AFFAIRES</span>
        <h2>CA ${"<span class=\"commercial-revenue-division\">" + "" + "</span>"}</h2>
        <p class="crm-subtitle">CA réalisé par ce commercial, uniquement sur sa division NASMEDIC ou NASDERM.</p>
      </div>
      <strong class="commercial-revenue-total">—</strong>
    </div>
    <div class="commercial-revenue-chart" style="height:280px;position:relative;margin-bottom:18px">
      <canvas aria-label="Évolution mensuelle du chiffre d’affaires"></canvas>
    </div>
    <div class="table-responsive table-scroll">
      <table class="responsive-table commercial-revenue-table" style="min-width:650px">
        <thead><tr><th>Mois</th><th>CA réalisé</th><th>Action</th></tr></thead>
        <tbody><tr><td colspan="3">Chargement…</td></tr></tbody>
      </table>
    </div>
  `;
  anchor.parentNode.insertBefore(card, anchor);

  const divisionEl = card.querySelector(".commercial-revenue-division");
  const totalEl = card.querySelector(".commercial-revenue-total");
  const tbody = card.querySelector("tbody");
  const canvas = card.querySelector("canvas");

  function money(value) {
    return new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value || 0) + " FCFA";
  }

  function monthLabel(value) {
    const parts = value.split("-");
    if (parts.length !== 2) return value;
    const d = new Date(Number(parts[0]), Number(parts[1]) - 1, 1);
    return d.toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
  }

  try {
    const response = await fetch("/commercial_dashboard/" + encodeURIComponent(username) + "/revenue-data", {
      headers: { "X-Requested-With": "XMLHttpRequest" }
    });
    if (!response.ok) throw new Error("CA indisponible");
    const data = await response.json();
    divisionEl.textContent = data.division_label || data.division || "";
    totalEl.textContent = "Total : " + money(data.total);

    tbody.innerHTML = "";
    if (!data.months || !data.months.length) {
      tbody.innerHTML = '<tr><td colspan="3">Aucun CA enregistré pour ce commercial.</td></tr>';
      return;
    }

    data.months.forEach(function (row) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td data-label="Mois"><strong>${monthLabel(row.month)}</strong></td>
        <td data-label="CA réalisé"><strong>${money(row.revenue)}</strong></td>
        <td data-label="Action"><button type="button" class="btn btn-outline commercial-revenue-detail" data-month="${row.month}">Voir le détail</button></td>
      `;
      tbody.appendChild(tr);
    });

    if (typeof Chart !== "undefined" && canvas) {
      new Chart(canvas, {
        type: "bar",
        data: {
          labels: data.months.map(function (row) { return monthLabel(row.month); }),
          datasets: [{ label: "CA", data: data.months.map(function (row) { return row.revenue; }), borderWidth: 1, borderRadius: 6 }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, ticks: { callback: function (value) { return money(value); } } }, x: { ticks: { autoSkip: false, maxRotation: 45, minRotation: 0 } } }
        }
      });
    }

    tbody.addEventListener("click", async function (event) {
      const button = event.target.closest(".commercial-revenue-detail");
      if (!button) return;
      const month = button.dataset.month;
      const oldDetail = tbody.querySelector(".commercial-revenue-detail-row");
      if (oldDetail) oldDetail.remove();
      button.disabled = true;
      button.textContent = "Chargement…";
      try {
        const detailResponse = await fetch("/commercial_dashboard/" + encodeURIComponent(username) + "/revenue-detail/" + encodeURIComponent(month), {
          headers: { "X-Requested-With": "XMLHttpRequest" }
        });
        if (!detailResponse.ok) throw new Error("Détail indisponible");
        const detail = await detailResponse.json();
        const detailRow = document.createElement("tr");
        detailRow.className = "commercial-revenue-detail-row";
        const rows = detail.rows || [];
        const body = rows.length ? rows.map(function (item) {
          return `<tr><td>${item.supplier}</td><td>${item.product}</td><td>${item.quantity}</td><td><strong>${money(item.revenue)}</strong></td></tr>`;
        }).join("") : '<tr><td colspan="4">Aucun détail produit pour ce mois.</td></tr>';
        detailRow.innerHTML = `<td colspan="3"><div class="crm-surface" style="padding:14px;margin:4px 0"><div class="section-heading"><strong>Détail — ${monthLabel(detail.month)}</strong><strong>${money(detail.total)}</strong></div><div class="table-responsive"><table class="responsive-table" style="min-width:560px"><thead><tr><th>Laboratoire</th><th>Produit</th><th>Qté</th><th>CA</th></tr></thead><tbody>${body}</tbody></table></div></div></td>`;
        button.closest("tr").after(detailRow);
      } catch (error) {
        const errorRow = document.createElement("tr");
        errorRow.className = "commercial-revenue-detail-row";
        errorRow.innerHTML = '<td colspan="3"><div class="flash flash-error">Impossible de charger le détail du CA.</div></td>';
        button.closest("tr").after(errorRow);
      } finally {
        button.disabled = false;
        button.textContent = "Voir le détail";
      }
    });
  } catch (error) {
    card.innerHTML = '<div class="section-heading"><div><span class="crm-overline">CHIFFRE D’AFFAIRES</span><h2>CA commercial</h2><p class="crm-subtitle">Le CA de la division du commercial est momentanément indisponible.</p></div></div>';
  }
});
