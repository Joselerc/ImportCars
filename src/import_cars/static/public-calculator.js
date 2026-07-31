(function () {
  "use strict";

  const config = window.PUBLIC_CALCULATOR_CONFIG || {};
  const byId = (id) => document.getElementById(id);
  const money = (value) => {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
    return new Intl.NumberFormat("es-ES", {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(Number(value));
  };
  const numeric = (id) => {
    const value = byId(id).value.trim();
    return value === "" ? null : Number(value);
  };
  const setStatus = (id, message, kind = "") => {
    const element = byId(id);
    element.textContent = message;
    element.className = `calc-status ${kind}`.trim();
  };
  const detailMessage = (data, fallback) => {
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) return data.detail.map((item) => item.msg).join(" · ");
    return fallback;
  };

  let latestCalculation = null;
  let latestSourceUrl = null;

  const switchPane = (name) => {
    document.querySelectorAll(".calc-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.pane === name);
    });
    document.querySelectorAll(".pane").forEach((pane) => {
      pane.classList.toggle("active", pane.dataset.pane === name);
    });
  };

  document.querySelectorAll(".calc-tab").forEach((tab) => {
    tab.addEventListener("click", () => switchPane(tab.dataset.pane));
  });

  const province = (id) => {
    const [autonomousCommunity, municipality] = byId(id).value.split("|");
    return { autonomousCommunity, municipality };
  };

  const manualPayload = () => {
    const location = province("m_prov");
    return {
      make: byId("m_make").value.trim(),
      model: byId("m_model").value.trim(),
      version: byId("m_version").value.trim() || null,
      first_registration: byId("m_date").value,
      purchase_price: numeric("m_price"),
      fuel: byId("m_fuel").value,
      displacement_cc: numeric("m_cc"),
      co2_gkm: numeric("m_co2"),
      mileage_km: numeric("m_km"),
      power_kw: numeric("m_kw"),
      seller_type: byId("m_seller").value,
      autonomous_community: location.autonomousCommunity,
      municipality: location.municipality,
      co2_confirmed: byId("m_co2_confirmed").checked,
    };
  };

  const fillManual = (listing) => {
    const values = {
      m_make: listing.make,
      m_model: listing.model,
      m_version: listing.version,
      m_date: listing.first_registration,
      m_price: listing.purchase_price,
      m_fuel: listing.fuel,
      m_cc: listing.displacement_cc,
      m_co2: listing.co2_gkm,
      m_km: listing.mileage_km,
      m_kw: listing.power_kw,
      m_seller: listing.seller_type,
    };
    Object.entries(values).forEach(([id, value]) => {
      if (value !== null && value !== undefined && byId(id)) byId(id).value = value;
    });
    byId("m_co2_confirmed").checked = Boolean(listing.co2_confirmed);
    byId("m_prov").value = byId("u_prov").value;
  };

  const addBreakdownRow = (container, row, extraClass = "") => {
    const element = document.createElement("div");
    element.className = `bd-row ${extraClass}`.trim();
    const label = document.createElement("div");
    label.className = "bd-label";
    const labelBlock = document.createElement("div");
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = row.label;
    labelBlock.appendChild(name);
    if (row.note) {
      const note = document.createElement("div");
      note.className = "note";
      note.textContent = row.note;
      labelBlock.appendChild(note);
    }
    label.appendChild(labelBlock);
    const value = document.createElement("div");
    value.className = "bd-val";
    value.textContent = money(row.amount_eur);
    element.append(label, value);
    container.appendChild(element);
  };

  const render = (data) => {
    latestCalculation = data;
    byId("r_car").textContent = data.vehicle_label;
    byId("r_total").textContent = money(data.final_price_eur).replace("€", "").trim();
    byId("r_save").textContent = data.savings_eur === null
      ? "—"
      : new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 }).format(data.savings_eur);
    byId("r_es").textContent = data.spanish_market_price_eur === null
      ? "no disponible ahora"
      : `${money(data.spanish_market_price_eur)} · ${data.market_sample_size} comparables`;
    document.querySelector(".savings .lbl").textContent =
      data.savings_eur !== null && data.savings_eur >= 0 ? "Te ahorras" : "Diferencia frente a España";

    const breakdown = byId("breakdown");
    breakdown.querySelectorAll(".bd-row").forEach((row) => row.remove());
    const disclaimer = breakdown.querySelector(".bd-sub");
    const rows = document.createElement("div");
    data.breakdown.forEach((row) => addBreakdownRow(rows, row, row.key === "honorarios" ? "fee" : ""));
    addBreakdownRow(rows, {
      label: "Precio final, todo incluido",
      amount_eur: data.final_price_eur,
      note: "",
    }, "total");
    breakdown.insertBefore(rows, disclaimer);
    byId("b_disclaimer").textContent =
      `Cálculo orientativo según ${data.fiscal_version}. ` +
      (data.boe_model_match
        ? `Versión BOE encontrada: ${data.boe_model_match}.`
        : "La versión exacta no se ha podido confirmar en la tabla del BOE.");

    const riskBox = byId("risk-box");
    const riskList = byId("risk-list");
    riskList.replaceChildren();
    data.warnings.forEach((warning) => {
      const item = document.createElement("li");
      item.textContent = warning;
      riskList.appendChild(item);
    });
    riskBox.hidden = data.warnings.length === 0;

    const whatsapp = byId("whatsapp-link");
    const message = encodeURIComponent(
      `Hola, quiero revisar la importación de ${data.vehicle_label}. El cálculo orientativo es ${money(data.final_price_eur)}.`
    );
    whatsapp.href = config.whatsappNumber ? `https://wa.me/${config.whatsappNumber}?text=${message}` : `https://wa.me/?text=${message}`;

    const results = byId("results");
    results.classList.add("show");
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const calculate = async () => {
    setStatus("manual-status", "Consultando Hacienda y comparables de coches.net…");
    try {
      const response = await fetch("/api/public/calculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(manualPayload()),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(detailMessage(data, "No se pudo calcular."));
      render(data);
      setStatus("manual-status", "Cálculo completado con el motor fiscal oficial.", "ok");
    } catch (error) {
      setStatus("manual-status", error.message || "No se pudo calcular.", "error");
    }
  };

  byId("manual-submit").addEventListener("click", (event) => {
    event.preventDefault();
    calculate();
  });

  byId("url-submit").addEventListener("click", async (event) => {
    event.preventDefault();
    const url = byId("urlInput").value.trim();
    if (!url) {
      setStatus("url-status", "Pega primero el enlace del anuncio.", "error");
      return;
    }
    setStatus("url-status", "Leyendo el anuncio…");
    try {
      const response = await fetch("/api/public/parse-listing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const listing = await response.json();
      if (!response.ok) throw new Error(detailMessage(listing, "No se pudo leer el anuncio."));
      latestSourceUrl = listing.source_url;
      fillManual(listing);
      switchPane("manual");
      if (listing.missing_fields.length) {
        setStatus(
          "manual-status",
          `Revisa los datos: el anuncio no aporta ${listing.missing_fields.join(", ")}.`,
          "error"
        );
      } else {
        setStatus("manual-status", "Anuncio leído. Revisa los datos y calculamos ahora.", "ok");
        await calculate();
      }
    } catch (error) {
      setStatus("url-status", `${error.message} Puedes continuar con los datos a mano.`, "error");
    }
  });

  byId("lead-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!latestCalculation) {
      setStatus("lead-status", "Haz primero un cálculo para preparar el presupuesto.", "error");
      return;
    }
    setStatus("lead-status", "Guardando tu solicitud…");
    try {
      const response = await fetch("/api/public/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: byId("lead-email").value,
          phone: byId("lead-phone").value || null,
          vehicle_label: latestCalculation.vehicle_label,
          final_price_eur: latestCalculation.final_price_eur,
          source_url: latestSourceUrl,
          consent: byId("lead-consent").checked,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(detailMessage(data, "No se pudo guardar la solicitud."));
      setStatus("lead-status", "Solicitud recibida. Te contactaremos para confirmar el presupuesto.", "ok");
      event.target.reset();
    } catch (error) {
      setStatus("lead-status", error.message || "No se pudo guardar la solicitud.", "error");
    }
  });
})();
