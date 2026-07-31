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
    element.setAttribute("role", kind === "error" ? "alert" : "status");
  };
  const detailMessage = (data, fallback) => {
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) return data.detail.map((item) => item.msg).join(" · ");
    return fallback;
  };

  let latestCalculation = null;
  let latestSourceUrl = null;

  const breakdownHelp = {
    precio: "Es el precio publicado por el vendedor en Alemania, antes de transporte e impuestos españoles.",
    transporte: "Traslado asegurado del vehículo desde Alemania hasta España.",
    iedmt: "Depende de las emisiones de CO₂ y del valor fiscal oficial del vehículo, no solo del precio del anuncio.",
    itp: "Se aplica al comprar a un particular. El tipo depende de la comunidad autónoma donde se matricula.",
    iva: "Se aplica cuando el vehículo cumple fiscalmente la condición de nuevo y debe liquidar IVA en España.",
    admin: "Incluye la ITV de importación, la tasa de matriculación de la DGT y las placas.",
    ivtm: "Es el impuesto municipal de circulación correspondiente al primer año, prorrateado cuando procede.",
    otros: "Agrupa conceptos adicionales que solo se aplican cuando hacen falta, como CoC, aduana o traducción.",
    honorarios: "Tarifa fija de gestión: búsqueda, verificación, negociación, coordinación del transporte y trámites.",
    total: "Suma del coche y todas las partidas mostradas para dejarlo matriculado y a tu nombre en España.",
  };
  const fieldNames = {
    make: "la marca",
    model: "el modelo",
    first_registration: "la primera matriculación",
    purchase_price: "el precio",
    fuel: "el combustible",
    displacement_cc: "la cilindrada",
    mileage_km: "los kilómetros",
    power_kw: "la potencia",
    seller_type: "el tipo de vendedor",
  };

  const setButtonLoading = (button, loading, message = "Calculando…") => {
    if (!button) return;
    if (loading) {
      if (!button.dataset.idleHtml) button.dataset.idleHtml = button.innerHTML;
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      button.classList.add("is-loading");
      button.textContent = message;
      return;
    }
    button.disabled = false;
    button.removeAttribute("aria-busy");
    button.classList.remove("is-loading");
    if (button.dataset.idleHtml) button.innerHTML = button.dataset.idleHtml;
  };

  const switchPane = (name) => {
    document.querySelectorAll(".calc-tab").forEach((tab) => {
      const active = tab.dataset.pane === name;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll(".pane").forEach((pane) => {
      const active = pane.dataset.pane === name;
      pane.classList.toggle("active", active);
      pane.hidden = !active;
    });
  };

  document.querySelectorAll(".calc-tab").forEach((tab) => {
    tab.addEventListener("click", () => switchPane(tab.dataset.pane));
    tab.addEventListener("keydown", (event) => {
      const tabs = Array.from(document.querySelectorAll(".calc-tab"));
      const current = tabs.indexOf(event.currentTarget);
      let next = null;
      if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
      if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      if (next === null) return;
      event.preventDefault();
      switchPane(tabs[next].dataset.pane);
      tabs[next].focus();
    });
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

  const displayLabel = (row) => {
    if (row.key === "ivtm") return "Impuesto de circulación (primer año, prorrateado)";
    if (row.key === "honorarios") return "Honorarios fijos de gestión";
    return row.label;
  };

  const displayNote = (note) => String(note || "").replaceAll("CO2", "CO₂").replaceAll(" -> ", " → ");

  const addBreakdownRow = (container, row, extraClass = "") => {
    const element = document.createElement("div");
    element.className = `bd-row ${extraClass}`.trim();
    const label = document.createElement("div");
    label.className = "bd-label";
    const labelBlock = document.createElement("div");
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = displayLabel(row);
    labelBlock.appendChild(name);
    if (row.note) {
      const note = document.createElement("div");
      note.className = "note";
      note.textContent = displayNote(row.note);
      labelBlock.appendChild(note);
    }
    label.appendChild(labelBlock);
    const help = breakdownHelp[row.key] || "Importe incluido en el precio final. El presupuesto formal confirmará esta partida por escrito.";
    const info = document.createElement("button");
    info.type = "button";
    info.className = "info";
    info.textContent = "i";
    info.dataset.tooltip = help;
    info.setAttribute("aria-label", `Más información sobre ${displayLabel(row)}`);
    label.appendChild(info);
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
    const savingsCard = byId("savings-card");
    const savingsLabel = savingsCard.querySelector(".lbl");
    savingsCard.classList.remove("positive", "negative", "unavailable");
    if (data.savings_eur === null || data.spanish_market_price_eur === null) {
      savingsCard.classList.add("unavailable");
      savingsLabel.textContent = "Ahorro aún no disponible";
      byId("r_save").textContent = "—";
      byId("r_es").textContent = "No hay suficientes comparables españoles. El precio final sí está calculado.";
    } else if (data.savings_eur >= 0) {
      savingsCard.classList.add("positive");
      savingsLabel.textContent = "Te ahorras";
      byId("r_save").textContent = money(data.savings_eur);
      byId("r_es").textContent = `frente a ${money(data.spanish_market_price_eur)} de media en España · ${data.market_sample_size} comparables`;
    } else {
      savingsCard.classList.add("negative");
      savingsLabel.textContent = "Cuesta más que en España";
      byId("r_save").textContent = money(Math.abs(data.savings_eur));
      byId("r_es").textContent = `sobre ${money(data.spanish_market_price_eur)} de media en España · ${data.market_sample_size} comparables`;
    }

    const rows = byId("breakdown-rows");
    rows.replaceChildren();
    (data.breakdown || []).forEach((row) => addBreakdownRow(rows, row, row.key === "honorarios" ? "fee" : ""));
    addBreakdownRow(rows, {
      key: "total",
      label: "Precio final, todo incluido",
      amount_eur: data.final_price_eur,
      note: "",
    }, "total");
    byId("b_disclaimer").textContent =
      `Cálculo según ${data.fiscal_version}. ` +
      (data.boe_model_match
        ? `Versión BOE encontrada: ${data.boe_model_match}.`
        : "La versión exacta no se ha podido confirmar en la tabla del BOE.");

    const riskBox = byId("risk-box");
    const riskList = byId("risk-list");
    riskList.replaceChildren();
    (data.warnings || []).forEach((warning) => {
      const item = document.createElement("li");
      item.textContent = warning;
      riskList.appendChild(item);
    });
    riskBox.hidden = !data.warnings || data.warnings.length === 0;

    const whatsapp = byId("whatsapp-link");
    const message = encodeURIComponent(
      `Hola, quiero revisar la importación de ${data.vehicle_label}. El cálculo orientativo es ${money(data.final_price_eur)}.`
    );
    whatsapp.href = config.whatsappNumber ? `https://wa.me/${config.whatsappNumber}?text=${message}` : `https://wa.me/?text=${message}`;

    const results = byId("results");
    results.classList.add("show");
    results.scrollIntoView({ behavior: "smooth", block: "start" });
    results.focus({ preventScroll: true });
  };

  const calculate = async (button = byId("manual-submit")) => {
    setStatus("manual-status", "Consultando Hacienda y comparables de coches.net…");
    setButtonLoading(button, true);
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
    } finally {
      setButtonLoading(button, false);
    }
  };

  byId("manual-submit").addEventListener("click", (event) => {
    event.preventDefault();
    calculate(event.currentTarget);
  });

  byId("url-submit").addEventListener("click", async (event) => {
    event.preventDefault();
    const url = byId("urlInput").value.trim();
    if (!url) {
      setStatus("url-status", "Pega primero el enlace del anuncio.", "error");
      return;
    }
    setStatus("url-status", "Leyendo el anuncio…");
    const button = event.currentTarget;
    setButtonLoading(button, true, "Leyendo anuncio…");
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
        const missing = listing.missing_fields.map((field) => fieldNames[field] || "algún dato necesario");
        setStatus(
          "manual-status",
          `Revisa los datos: el anuncio no aporta ${missing.join(", ")}.`,
          "error"
        );
      } else {
        setStatus("manual-status", "Anuncio leído. Revisa los datos y calculamos ahora.", "ok");
        await calculate(byId("manual-submit"));
      }
    } catch (error) {
      switchPane("manual");
      setStatus("url-status", "No hemos podido leer ese anuncio.", "error");
      setStatus("manual-status", `${error.message} Puedes continuar con los datos a mano.`, "error");
      byId("m_make").focus();
    } finally {
      setButtonLoading(button, false);
    }
  });

  byId("lead-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!latestCalculation) {
      setStatus("lead-status", "Haz primero un cálculo para preparar el presupuesto.", "error");
      return;
    }
    setStatus("lead-status", "Guardando tu solicitud…");
    const button = byId("lead-submit");
    setButtonLoading(button, true, "Enviando…");
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
    } finally {
      setButtonLoading(button, false);
    }
  });
})();
