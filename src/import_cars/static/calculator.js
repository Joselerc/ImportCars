(function () {
  const form = document.getElementById("calculator-form");
  if (!form) return;

  const statusEl = document.getElementById("calc-status");
  const sellerTypeEl = document.getElementById("calc-selected-type");
  const scenarioList = document.getElementById("scenario-list");

  const num = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const eurFmt = (value) => {
    const parsed = num(value);
    return parsed === null ? "--" : new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(parsed);
  };
  const pctFmt = (value) => {
    const parsed = num(value);
    return parsed === null ? "--" : `${parsed.toFixed(2)}%`;
  };
  const set = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };
  const serialize = () => {
    const raw = Object.fromEntries(new FormData(form).entries());
    return {
      purchase_price: Number(raw.purchase_price),
      sale_price: raw.sale_price ? Number(raw.sale_price) : null,
      co2: raw.co2 ? Number(raw.co2) : null,
      seller_type: raw.seller_type,
    };
  };

  const renderSelected = (data) => {
    set("calc-selected-type", data.tipo);
    set("calc-break-even", eurFmt(data.break_even));
    set("calc-profitability", data.beneficio_neto !== undefined ? `${eurFmt(data.beneficio_neto)} net / ${pctFmt(data.rentabilidad_porcentaje)}` : "Sin precio de venta");
    set("calc-itp", eurFmt(data.itp));
    set("calc-iedmt", eurFmt(data.iedmt));
    set("calc-transport", eurFmt(data.transporte));
    const paperwork = (num(data.itv_tasa) || 0) + (num(data.traducciones) || 0) + (num(data.ivtm) || 0) + (num(data.placas) || 0);
    set("calc-paperwork", eurFmt(paperwork || null));
    set("calc-benefit", eurFmt(data.beneficio_neto));
  };

  const renderScenarios = (scenarios, best) => {
    if (!scenarios.length) {
      scenarioList.innerHTML = '<div class="empty">Sin escenarios.</div>';
      return;
    }
    scenarioList.innerHTML = scenarios.map((scenario) => `
      <article class="scenario-card ${best && best.tipo === scenario.tipo ? "scenario-best" : ""}">
        <div>
          <div class="label">${best && best.tipo === scenario.tipo ? "Best Case" : "Scenario"}</div>
          <h3>${scenario.tipo}</h3>
          <div class="report-meta">Break-even ${eurFmt(scenario.break_even)} · IEDMT ${eurFmt(scenario.iedmt)}</div>
        </div>
        <div class="right-align">
          <div class="metric">Net benefit</div>
          <div class="metric-value ${num(scenario.beneficio_neto) > 0 ? "good" : ""}">${eurFmt(scenario.beneficio_neto)}</div>
        </div>
      </article>
    `).join("");
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    statusEl.textContent = "Calculando costes de importacion...";
    const response = await fetch("/api/import-calculator", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(serialize()),
    });
    const data = await response.json();
    if (!response.ok) {
      statusEl.textContent = data.detail || "Error calculando.";
      return;
    }
    renderSelected(data.selected);
    renderScenarios(data.scenarios || [], data.best);
    sellerTypeEl.textContent = data.selected.tipo;
    statusEl.textContent = "Simulacion completada.";
  });

  form.requestSubmit();
})();
