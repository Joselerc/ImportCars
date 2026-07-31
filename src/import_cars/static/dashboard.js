(function () {
  const form = document.getElementById("compare-form");
  if (!form) return;

  const modeInput = document.getElementById("mode");
  const modeButtons = [...document.querySelectorAll(".mode-btn")];
  const panes = [...document.querySelectorAll(".mode-pane")];
  const statusEl = document.getElementById("status");
  const exportLink = document.getElementById("export-link");
  const oppsEl = document.getElementById("opps");
  const tableBody = document.querySelector("#results-table tbody");
  const drawer = document.getElementById("drawer");
  const drawerClose = document.getElementById("drawer-close");
  let lastExportUrl = "#";
  let selectedUrl = null;

  const n = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const safe = (value) => (value === null || value === undefined || value === "" ? "--" : value);
  const intFmt = (value) => {
    const parsed = n(value);
    return parsed === null ? "--" : new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 }).format(parsed);
  };
  const eurFmt = (value) => {
    const parsed = n(value);
    return parsed === null ? "--" : new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(parsed);
  };
  const initials = (row) => `${(row.make || "?")[0] || "?"}${(row.model || "?")[0] || "?"}`;
  const badgeKind = (value) => {
    const key = String(value || "broad").toLowerCase();
    return key === "exact" ? "exact" : key === "near" ? "near" : "broad";
  };
  const co2Kind = (value) => {
    const key = String(value || "missing").toLowerCase();
    return key.includes("original") ? "original" : key.includes("inferred") ? "inferred" : "missing";
  };
  const set = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };
  const imageMarkup = (url, alt) => (url ? `<img src="${url}" alt="${alt}" loading="lazy">` : "");

  const switchMode = (mode) => {
    modeInput.value = mode;
    modeButtons.forEach((btn) => btn.classList.toggle("active", btn.dataset.mode === mode));
    panes.forEach((pane) => pane.classList.toggle("hidden", pane.dataset.pane !== mode));
  };

  const serialize = () => {
    const data = {};
    new FormData(form).forEach((value, key) => {
      if (value !== "") data[key] = value;
    });
    ["dealer_only", "private_only", "de_dealer_only", "de_private_only", "es_dealer_only", "es_private_only"].forEach((key) => {
      const input = form.querySelector(`[name="${key}"]`);
      data[key] = input ? input.checked : false;
    });
    [
      "limit", "min_price", "max_price", "min_year", "max_year", "min_mileage", "max_mileage", "min_power", "max_power",
      "de_min_price", "de_max_price", "de_min_year", "de_max_year", "de_min_mileage", "de_max_mileage", "de_min_power", "de_max_power", "de_limit",
      "es_min_price", "es_max_price", "es_min_year", "es_max_year", "es_min_mileage", "es_max_mileage", "es_min_power", "es_max_power", "es_limit"
    ].forEach((key) => {
      if (data[key] !== undefined) data[key] = Number(data[key]);
    });
    data.mode = modeInput.value;
    return data;
  };

  const renderSummary = (summary) => {
    set("last-updated", safe(summary.last_updated));
    set("sum-listings", `${intFmt(summary.de_count)} / ${intFmt(summary.es_count)}`);
    set("sum-listings-sub", `${intFmt(summary.positive_count)} oportunidades positivas`);
    set("sum-prices", `${eurFmt(summary.de_avg_price)} / ${eurFmt(summary.es_avg_price)}`);
    set("sum-prices-sub", `${eurFmt(summary.avg_break_even)} break-even medio`);
    set("sum-margin", eurFmt(summary.avg_margin));
    set("sum-margin-sub", `${eurFmt(summary.best_margin)} mejor margen`);
    set("sum-score", intFmt(summary.top_score));
    set("sum-score-sub", `${intFmt(summary.exact_count)} exact / ${intFmt(summary.near_count)} near / ${intFmt(summary.broad_count)} broad`);
  };

  const renderDrawer = (row) => {
    if (!row) return;
    selectedUrl = row.url;
    drawer.classList.add("open");
    set("detail-title", row.display_title || `${safe(row.make)} ${safe(row.model)}`);
    const confidence = document.getElementById("detail-confidence");
    if (confidence) {
      confidence.className = `badge ${co2Kind(row.co2_source_type)}`;
      confidence.textContent = String(row.co2_source_type || "missing").replaceAll("_", " ");
    }
    set("detail-score-big", intFmt(row.opportunity_score));
    set("spec-year", safe(row.year));
    set("spec-mileage", row.mileage_km ? `${intFmt(row.mileage_km)} km` : "--");
    set("spec-power", row.power_hp ? `${intFmt(row.power_hp)} hp` : "--");
    set("spec-fuel", safe(row.fuel_type));
    document.getElementById("detail-link").href = row.url || "#";
    document.getElementById("detail-export-link").href = lastExportUrl;
    document.getElementById("drawer-image").innerHTML = imageMarkup(row.image_url, row.display_title || "Car image");
    set("detail-margin", eurFmt(row.potential_margin_avg));
    set("detail-market-ref", `${eurFmt(row.es_market_avg)} ES market average`);
    set("detail-match", safe(row.comparable_match_level));
    set("detail-exact", intFmt(row.es_exact_sample_size));
    set("detail-near", intFmt(row.es_near_sample_size));
    set("detail-broad", intFmt(row.es_broad_sample_size));
    set("detail-sample", intFmt(row.es_sample_size));
    set("detail-es-avg", eurFmt(row.es_market_avg));
    set("detail-es-median", eurFmt(row.es_market_median));
    const costs = row.cost_breakdown || {};
    set("cost-price", eurFmt(row.price_eur));
    set("cost-case", safe(costs.tipo_compra));
    set("cost-itp", eurFmt(costs.itp));
    set("cost-iedmt", eurFmt(costs.iedmt));
    set("cost-transport", eurFmt(costs.transporte));
    const paperwork = (n(costs.itv_tasa) || 0) + (n(costs.traducciones) || 0) + (n(costs.ivtm) || 0) + (n(costs.placas) || 0);
    set("cost-paperwork", eurFmt(paperwork || null));
    set("cost-total", eurFmt(costs.coste_total || row.best_break_even));
  };

  const renderOpportunities = (rows) => {
    if (!rows.length) {
      oppsEl.innerHTML = '<div class="empty">No se han encontrado oportunidades con esos filtros.</div>';
      return;
    }
    oppsEl.innerHTML = rows.map((row, index) => `
      <article class="opp ${(selectedUrl === row.url || (!selectedUrl && index === 0)) ? "active" : ""}" data-url="${row.url}">
        <div class="thumb" data-initials="${initials(row)}">
          ${imageMarkup(row.image_url, row.display_title || "Car image")}
          <div class="badge ${badgeKind(row.comparable_match_level)} top-badge">${safe(row.comparable_match_level)}</div>
        </div>
        <div>
          <div class="opp-header">
            <div>
              <h3 class="opp-title">${safe(row.display_title || `${row.make || ""} ${row.model || ""}`)}</h3>
              <div class="opp-meta">
                <span>${safe(row.variant_key)}</span>
                <span>${safe(row.year)}</span>
                <span>${row.mileage_km ? `${intFmt(row.mileage_km)} km` : "--"}</span>
                <span>${row.power_hp ? `${intFmt(row.power_hp)} hp` : "--"}</span>
              </div>
            </div>
            <div class="right-align">
              <div class="metric">CO2 Confidence</div>
              <div class="badge ${co2Kind(row.co2_source_type)}">${safe(row.co2_source_type)}</div>
            </div>
          </div>
          <div class="opp-grid">
            <div><div class="metric">DE Listing Price</div><div class="metric-value">${eurFmt(row.price_eur)}</div></div>
            <div><div class="metric">Best Break-even</div><div class="metric-value">${eurFmt(row.best_break_even)}</div></div>
            <div><div class="metric">ES Market Avg</div><div class="metric-value">${eurFmt(row.es_market_avg)}</div></div>
            <div><div class="metric">Net Margin</div><div class="metric-value good">${eurFmt(row.potential_margin_avg)}</div></div>
          </div>
          <div class="small-actions">
            <div class="micro">${intFmt(row.es_sample_size)} comparables / ${safe(row.source)}</div>
            <div class="micro">${safe(row.seller_type)}</div>
          </div>
        </div>
        <div class="score">
          <div class="metric">Opportunity Score</div>
          <div class="score-number">${intFmt(row.opportunity_score)}</div>
        </div>
      </article>
    `).join("");

    document.querySelectorAll(".opp").forEach((card) => {
      card.addEventListener("click", () => {
        const row = rows.find((item) => item.url === card.dataset.url);
        document.querySelectorAll(".opp").forEach((el) => el.classList.remove("active"));
        card.classList.add("active");
        renderDrawer(row);
      });
    });
    renderDrawer(rows[0]);
  };

  const renderTable = (rows) => {
    if (!rows.length) {
      tableBody.innerHTML = '<tr><td colspan="13" class="muted-cell">Sin resultados.</td></tr>';
      return;
    }
    tableBody.innerHTML = rows.slice(0, 40).map((row) => `
      <tr>
        <td>${safe(row.source)}</td>
        <td>${safe(row.display_title)}</td>
        <td>${safe(row.variant_key)}</td>
        <td>${safe(row.year)}</td>
        <td>${safe(row.fuel_type)}</td>
        <td>${eurFmt(row.price_eur)}</td>
        <td>${safe(row.co2_display)}</td>
        <td>${safe(row.co2_source_type)}</td>
        <td>${safe(row.comparable_match_level)}</td>
        <td>${eurFmt(row.es_market_avg)}</td>
        <td>${eurFmt(row.best_break_even)}</td>
        <td>${eurFmt(row.potential_margin_avg)}</td>
        <td>${intFmt(row.opportunity_score)}</td>
      </tr>
    `).join("");
  };

  const hasSearchSeed = (data) => Boolean(data.make || data.de_make || data.es_make);

  modeButtons.forEach((btn) => btn.addEventListener("click", () => switchMode(btn.dataset.mode)));
  if (drawerClose) drawerClose.addEventListener("click", () => drawer.classList.remove("open"));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = serialize();
    if (!hasSearchSeed(payload)) {
      statusEl.textContent = "Introduce al menos una marca antes de ejecutar la comparacion.";
      return;
    }
    statusEl.textContent = "Ejecutando scraping, enriquecimiento y scoring...";
    const response = await fetch("/api/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      statusEl.textContent = data.detail || "Error ejecutando la comparacion.";
      return;
    }
    selectedUrl = null;
    lastExportUrl = data.export_url || "#";
    if (exportLink) exportLink.href = lastExportUrl;
    statusEl.textContent = `Completado. ${data.summary.de_count} anuncios DE, ${data.summary.es_count} anuncios ES, ${data.summary.positive_count} oportunidades positivas.`;
    renderSummary(data.summary);
    renderOpportunities(data.opportunities || []);
    renderTable(data.rows || []);
  });
})();
