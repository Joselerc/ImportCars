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
  let selectedBoeRowId = null;

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
    cylinders: "el número de cilindros",
    mileage_km: "los kilómetros",
    power_kw: "la potencia",
    body_type: "la carrocería",
    transmission: "el tipo de cambio",
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
    const payload = {
      make: byId("m_make").value.trim(),
      model: byId("m_model").value.trim(),
      version: byId("m_version").value.trim() || null,
      first_registration: byId("m_date").value,
      purchase_price: numeric("m_price"),
      fuel: byId("m_fuel").value,
      displacement_cc: numeric("m_cc"),
      cylinders: numeric("m_cylinders"),
      co2_gkm: numeric("m_co2"),
      mileage_km: numeric("m_km"),
      power_kw: numeric("m_kw"),
      body_type: byId("m_body").value || null,
      transmission: byId("m_transmission")?.value || null,
      seller_type: byId("m_seller").value,
      autonomous_community: location.autonomousCommunity,
      municipality: location.municipality,
      co2_confirmed: byId("m_co2_confirmed").checked,
      damaged: byId("m_damaged").value === "true",
      damage_condition: byId("m_damage_condition").value || null,
    };
    if (config.auditMode && selectedBoeRowId !== null) {
      payload.boe_row_id_override = selectedBoeRowId;
    }
    return payload;
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
      m_cylinders: listing.cylinders,
      m_co2: listing.co2_gkm,
      m_km: listing.mileage_km,
      m_kw: listing.power_kw,
      m_body: listing.body_type,
      m_transmission: listing.transmission,
      m_seller: listing.seller_type,
      m_damaged: String(Boolean(listing.damaged)),
      m_damage_condition: listing.damage_condition,
    };
    Object.entries(values).forEach(([id, value]) => {
      if (byId(id)) byId(id).value = value ?? "";
    });
    byId("m_body").value = listing.body_type || "";
    byId("m_co2_confirmed").checked = Boolean(listing.co2_confirmed);
    byId("m_prov").value = byId("u_prov").value;
  };

  const displayLabel = (row) => {
    if (row.key === "ivtm") return "Impuesto de circulación (primer año, prorrateado)";
    if (row.key === "honorarios") return "Honorarios fijos de gestión";
    return row.label;
  };

  const displayNote = (note) => String(note || "").replaceAll("CO2", "CO₂").replaceAll(" -> ", " → ");

  const auditValue = (item) => {
    const value = item?.value;
    if (value === null || value === undefined || value === "") return "No disponible";
    if (item.unit === "EUR") return new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 2 }).format(Number(value));
    if (typeof value === "number") {
      const formatted = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 4 }).format(value);
      return `${formatted}${item.unit ? ` ${item.unit}` : ""}`;
    }
    return `${value}${item.unit ? ` ${item.unit}` : ""}`;
  };

  const addBreakdownRow = (container, row, extraClass = "", auditLine = null) => {
    const element = document.createElement(auditLine ? "details" : "div");
    element.className = `bd-row ${extraClass} ${auditLine ? "audit-breakdown" : ""}`.trim();
    const shell = auditLine ? document.createElement("summary") : element;
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
    shell.append(label, value);
    if (auditLine) {
      element.appendChild(shell);
      const detail = document.createElement("div");
      detail.className = "audit-line-detail";
      const formula = document.createElement("div");
      formula.className = "audit-formula";
      formula.textContent = auditLine.formula || "Partida directa sin fórmula adicional.";
      const values = document.createElement("div");
      values.className = "audit-values";
      (auditLine.intermediates || []).forEach((item) => {
        const wrapper = document.createElement("div");
        wrapper.className = "audit-value";
        const itemLabel = document.createElement("span");
        itemLabel.textContent = item.label;
        const itemValue = document.createElement("strong");
        itemValue.textContent = auditValue(item);
        if (item.note) {
          const note = document.createElement("small");
          note.textContent = item.note;
          itemValue.appendChild(note);
        }
        wrapper.append(itemLabel, itemValue);
        values.appendChild(wrapper);
      });
      detail.append(formula, values);
      element.appendChild(detail);
    }
    container.appendChild(element);
  };

  const addTextElement = (parent, tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = text;
    parent.appendChild(element);
    return element;
  };

  const statusLabel = {
    used: "Usado",
    not_used: "No usado",
    unavailable: "Sin dato",
  };

  const renderAuditMarket = (market) => {
    const panel = byId("audit-market");
    if (!panel || !market) return;
    panel.hidden = false;

    const summary = byId("audit-summary");
    summary.replaceChildren();
    [
      ["Precio medio", money(market.average_eur)],
      ["Rango mínimo–máximo", market.minimum_eur === null ? "—" : `${money(market.minimum_eur)} – ${money(market.maximum_eur)}`],
      ["Comparables", String(market.sample_size || 0)],
      ["Nivel aplicado", market.match_level || "Sin nivel"],
    ].forEach(([label, value]) => {
      const card = document.createElement("div");
      card.className = "audit-stat";
      addTextElement(card, "span", "", label);
      addTextElement(card, "strong", "", value);
      summary.appendChild(card);
    });

    const warning = byId("audit-warning");
    const warningText = market.quality_warning || (market.sample_size === 0 ? "No se encontró ningún comparable homologable para esta búsqueda." : "");
    warning.textContent = warningText;
    warning.hidden = !warningText;

    const criteria = byId("audit-criteria");
    criteria.replaceChildren();
    (market.criteria || []).forEach((criterion) => {
      const card = document.createElement("div");
      card.className = "criterion";
      const head = document.createElement("div");
      head.className = "criterion-head";
      addTextElement(head, "strong", "", criterion.label);
      addTextElement(head, "span", `status-chip status-${criterion.status}`, statusLabel[criterion.status] || criterion.status);
      card.appendChild(head);
      addTextElement(card, "code", "", criterion.target_value ?? "No disponible");
      addTextElement(card, "p", "", criterion.rule);
      if (criterion.note) addTextElement(card, "p", "", criterion.note);
      criteria.appendChild(card);
    });

    const comparables = byId("audit-comparables");
    comparables.replaceChildren();
    (market.comparables || []).forEach((car, index) => {
      const details = document.createElement("details");
      const itemSummary = document.createElement("summary");
      const heading = document.createElement("div");
      heading.className = "comparable-head";
      addTextElement(heading, "strong", "", `${index + 1}. ${car.title || car.version || "Anuncio sin título"}`);
      addTextElement(heading, "span", "", `${money(car.price_eur)} · nivel ${car.match_level}`);
      itemSummary.appendChild(heading);
      details.appendChild(itemSummary);
      const body = document.createElement("div");
      body.className = "audit-detail-body";
      const facts = document.createElement("div");
      facts.className = "comparable-facts";
      [
        ["Kilómetros", car.mileage_km === null ? "No consta" : `${new Intl.NumberFormat("es-ES").format(car.mileage_km)} km`],
        ["Año", car.year ?? "No consta"],
        ["Combustible", car.fuel || "No consta"],
        ["Cambio", car.transmission || "No consta"],
        ["Versión / motor", car.version || "No consta"],
      ].forEach(([label, value]) => {
        const fact = document.createElement("div");
        fact.className = "comparable-fact";
        addTextElement(fact, "span", "", label);
        addTextElement(fact, "strong", "", String(value));
        facts.appendChild(fact);
      });
      body.appendChild(facts);
      const link = document.createElement("a");
      link.className = "comparable-link";
      link.href = car.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = "Abrir anuncio en coches.net ↗";
      body.appendChild(link);
      const groups = { used: [], not_used: [], unavailable: [] };
      (car.checks || []).forEach((check) => groups[check.status]?.push(check.label));
      const checks = document.createElement("div");
      checks.className = "audit-checks";
      checks.textContent = [
        `Usados: ${groups.used.join(", ") || "ninguno"}.`,
        `No usados por la política actual: ${groups.not_used.join(", ") || "ninguno"}.`,
        `No aplicables por falta de datos: ${groups.unavailable.join(", ") || "ninguno"}.`,
      ].join(" ");
      body.appendChild(checks);
      details.appendChild(body);
      comparables.appendChild(details);
    });
  };

  const renderAuditBoe = (boe) => {
    const panel = byId("audit-boe");
    if (!panel || !boe) return;
    panel.hidden = false;
    const summary = byId("audit-boe-summary");
    summary.replaceChildren();
    [
      ["Modelo + año", String(boe.base_candidate_count || 0)],
      ["Filtro técnico", String(boe.technical_candidate_count || 0)],
      ["Tras cambio", String(boe.transmission_candidate_count || 0)],
      ["Confianza", boe.confidence === "non_conclusive" ? "No concluyente" : boe.confidence === "manual" ? "Confirmación manual" : boe.confidence === "high" ? "Alta" : "Sin resolver"],
    ].forEach(([label, value]) => {
      const card = document.createElement("div");
      card.className = "audit-stat";
      addTextElement(card, "span", "", label);
      addTextElement(card, "strong", "", value);
      summary.appendChild(card);
    });
    byId("audit-boe-query").textContent = `Consulta: ${boe.brand || "—"} · ${boe.query || "—"} · ${boe.year || "—"}${boe.price_spread_pct === null ? "" : ` · dispersión ${boe.price_spread_pct}%`}`;
    const warning = byId("audit-boe-warning");
    warning.textContent = boe.warning || "";
    warning.hidden = !boe.warning;
    const container = byId("audit-boe-candidates");
    container.replaceChildren();
    if (!(boe.candidates || []).length) {
      addTextElement(container, "p", "audit-intro", "No hay filas que superen todos los filtros técnicos obligatorios.");
      return;
    }
    (boe.candidates || []).forEach((candidate) => {
      const card = document.createElement("article");
      card.className = `boe-candidate${candidate.selected ? " selected" : ""}`;
      const head = document.createElement("div");
      head.className = "boe-candidate-head";
      const title = document.createElement("div");
      addTextElement(title, "strong", "", `Fila ${candidate.row_id} · ${candidate.model_type}`);
      addTextElement(title, "small", "", candidate.selected ? "Fila aplicada al cálculo" : "Candidata técnica");
      head.appendChild(title);
      addTextElement(head, "span", "", money(candidate.value_eur));
      card.appendChild(head);
      addTextElement(card, "div", "boe-candidate-meta", `Periodo ${candidate.commercial_start ?? "—"}–${candidate.commercial_end ?? "—"} · ${candidate.displacement_cc} cc · ${candidate.cylinders} cil. · ${candidate.fuel_code} · ${candidate.power_kw} kW / ${candidate.power_cv} CV · ${candidate.transmission_kind} · similitud ${candidate.text_score}`);
      addTextElement(card, "div", "boe-candidate-decision", candidate.decision);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "boe-select";
      button.disabled = candidate.selected;
      button.textContent = candidate.selected ? "Fila aplicada" : "Usar esta fila y recalcular";
      button.addEventListener("click", () => {
        selectedBoeRowId = candidate.row_id;
        calculate(button);
      });
      card.appendChild(button);
      container.appendChild(card);
    });
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
    const auditLines = new Map((data.audit?.fiscal_breakdown || []).map((line) => [line.key, line]));
    (data.breakdown || []).forEach((row) => addBreakdownRow(
      rows,
      row,
      row.key === "honorarios" ? "fee" : "",
      config.auditMode ? auditLines.get(row.key) : null
    ));
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
    riskBox.classList.toggle(
      "critical",
      (data.warnings || []).some((warning) => warning.startsWith("ATENCIÓN"))
    );
    riskBox.hidden = !data.warnings || data.warnings.length === 0;
    if (config.auditMode) {
      renderAuditBoe(data.audit?.boe);
      renderAuditMarket(data.audit?.market);
    }

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
      const response = await fetch(config.calculationEndpoint || "/api/public/calculate", {
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

  document.querySelectorAll("#pane-manual input, #pane-manual select").forEach((field) => {
    field.addEventListener("change", () => {
      selectedBoeRowId = null;
    });
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
      selectedBoeRowId = null;
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
