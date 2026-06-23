const statusEl = document.querySelector("#api-status");
const availabilityBody = document.querySelector("#availability-body");
const metricPhysical = document.querySelector("#metric-physical");
const metricReserved = document.querySelector("#metric-reserved");
const metricInvoiced = document.querySelector("#metric-invoiced");
const metricBlocked = document.querySelector("#metric-blocked");
const refreshButton = document.querySelector("#refresh-button");
const messagePanel = document.querySelector("#message-panel");
const invoiceForm = document.querySelector("#invoice-form");
const reservationForm = document.querySelector("#reservation-form");
const dispatchForm = document.querySelector("#dispatch-form");
const purchaseOrderForm = document.querySelector("#purchase-order-form");
const adjustmentForm = document.querySelector("#adjustment-form");
const approvalForm = document.querySelector("#approval-form");
const stockImportForm = document.querySelector("#stock-import-form");
const stockTemplateButton = document.querySelector("#stock-template-button");
const stockImportPreview = document.querySelector("#stock-import-preview");
const stockImportSummary = document.querySelector("#stock-import-summary");
const stockImportErrors = document.querySelector("#stock-import-errors");
const stockImportBody = document.querySelector("#stock-import-body");
const confirmStockImportButton = document.querySelector("#confirm-stock-import");
const bulkApprovalForm = document.querySelector("#bulk-approval-form");
const stockImportRequestsBody = document.querySelector("#stock-import-requests-body");
const refreshStockImportsButton = document.querySelector("#refresh-stock-imports");
const invoiceLines = document.querySelector("#invoice-lines");
const dispatchLines = document.querySelector("#dispatch-lines");
const purchaseOrderLines = document.querySelector("#purchase-order-lines");
const currentUserLabel = document.querySelector("#current-user-label");
const currentRoleLabel = document.querySelector("#current-role-label");
const userSummary = document.querySelector("#user-summary");
const logoutButton = document.querySelector("#logout-button");
const authView = document.querySelector("#auth-view");
const applicationView = document.querySelector("#application-view");
const loginForm = document.querySelector("#login-form");
const bootstrapForm = document.querySelector("#bootstrap-form");
const passwordChangeForm = document.querySelector("#password-change-form");
const userCreateForm = document.querySelector("#user-create-form");
const userUpdateForm = document.querySelector("#user-update-form");
const userResetForm = document.querySelector("#user-reset-form");
const usersBody = document.querySelector("#users-body");
const productCountBadge = document.querySelector("#product-count-badge");
const refreshTrackingButton = document.querySelector("#refresh-tracking");
const trackingInvoicesBody = document.querySelector("#tracking-invoices-body");
const trackingReservationsBody = document.querySelector("#tracking-reservations-body");
const trackingDispatchesBody = document.querySelector("#tracking-dispatches-body");
const purchaseOrdersBody = document.querySelector("#purchase-orders-body");
const incidentsBody = document.querySelector("#incidents-body");
const refreshPurchaseOrdersButton = document.querySelector("#refresh-purchase-orders");
const refreshIncidentsButton = document.querySelector("#refresh-incidents");
const moduleButtons = [...document.querySelectorAll("[data-module]")];
const moduleViews = [...document.querySelectorAll(".module-view")];
const workspaceTitle = document.querySelector("#workspace-title");
const workspaceDescription = document.querySelector("#workspace-description");
const workspaceRole = document.querySelector("#workspace-role");

const API_BASE_URL = (() => {
  const configuredBase = document.body?.dataset?.apiBaseUrl?.trim();
  if (configuredBase) {
    return configuredBase.replace(/\/$/, "");
  }
  if (window.location.protocol.startsWith("http")) {
    const isLocalhost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
    return isLocalhost ? "http://127.0.0.1:8000" : "/api";
  }
  return "http://127.0.0.1:8000";
})();
let currentUser = null;
let currentStockImportPreview = null;

const ROLE_LABELS = {
  principal: "Principal",
  administracion: "Administracion",
  ventas: "Ventas",
  bodega: "Bodega",
  consulta: "Consulta",
};

const MODULE_META = {
  overview: {
    title: "Resumen de inventario",
    description: "Disponibilidad operativa, indicadores y catalogo central.",
  },
  tracking: {
    title: "Seguimiento operativo",
    description: "Consulta facturas, reservas y productos pendientes de despacho.",
  },
  "purchase-orders": {
    title: "Ordenes de compra",
    description: "Registra OCs, guarda trazabilidad por cadena y prepara el trabajo de facturacion.",
  },
  incidents: {
    title: "Incidencias",
    description: "Muestra faltantes y problemas detectados para que no se pierda el seguimiento.",
  },
  invoices: {
    title: "Facturacion",
    description: "Registra facturas confirmadas en Contifico sin exceder el disponible.",
  },
  reservations: {
    title: "Reservas",
    description: "Separa unidades para pedidos pendientes y conserva su trazabilidad.",
  },
  dispatches: {
    title: "Despachos",
    description: "Confirma salidas completas, parciales o faltantes reportados por bodega.",
  },
  adjustments: {
    title: "Ajustes de stock",
    description: "Registra ajustes individuales o carga el conteo fisico completo de bodega.",
  },
  approvals: {
    title: "Aprobaciones",
    description: "Revisa ajustes y conteos masivos antes de modificar el inventario.",
  },
  users: {
    title: "Usuarios y accesos",
    description: "Crea cuentas, asigna roles y administra el acceso al sistema.",
  },
};

function formatNumber(value) {
  return Number(value || 0).toLocaleString("es-EC");
}

function formatDate(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("es-EC", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setMessage(text, type = "info") {
  messagePanel.textContent = text;
  messagePanel.className = `message-panel ${type}`;
}

function setApiStatus(text, connected) {
  statusEl.textContent = text;
  statusEl.classList.toggle("ok", connected);
}

function buildApiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

async function apiRequest(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (options.body instanceof FormData) {
    delete headers["Content-Type"];
  }
  const response = await fetch(buildApiUrl(path), {
    ...options,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    let detail = "La API rechazo la operacion.";
    try {
      const data = await response.json();
      detail = Array.isArray(data.detail)
        ? data.detail.map((item) => item.msg).join(" ")
        : data.detail || detail;
    } catch (error) {
      detail = response.statusText || detail;
    }
    const requestError = new Error(detail);
    requestError.status = response.status;
    throw requestError;
  }
  return response.json();
}

function applyPermissions(permissionValues) {
  const permissions = new Set(permissionValues);
  document.querySelectorAll("[data-permission]").forEach((element) => {
    element.classList.toggle("allowed", permissions.has(element.dataset.permission));
  });
  activateFirstAllowedModule();
}

function activateModule(moduleName) {
  const button = moduleButtons.find(
    (item) => item.dataset.module === moduleName && item.classList.contains("allowed"),
  );
  if (!button) return;

  moduleButtons.forEach((item) => {
    const active = item === button;
    item.classList.toggle("active", active);
    item.setAttribute("aria-current", active ? "page" : "false");
  });
  moduleViews.forEach((view) => {
    view.classList.toggle("active", view.dataset.view === moduleName);
  });

  const meta = MODULE_META[moduleName];
  workspaceTitle.textContent = meta.title;
  workspaceDescription.textContent = meta.description;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function activateFirstAllowedModule() {
  const currentButton = moduleButtons.find(
    (item) => item.classList.contains("active") && item.classList.contains("allowed"),
  );
  const preferredButton = moduleButtons.find(
    (item) => item.dataset.module === "overview" && item.classList.contains("allowed"),
  );
  const target = currentButton || preferredButton || moduleButtons.find((item) => item.classList.contains("allowed"));
  if (target) activateModule(target.dataset.module);
}

function showAuthForm(formToShow) {
  currentUser = null;
  authView.hidden = false;
  applicationView.hidden = true;
  currentUserLabel.hidden = true;
  userSummary.hidden = true;
  logoutButton.hidden = true;
  [loginForm, bootstrapForm, passwordChangeForm].forEach((form) => {
    form.hidden = form !== formToShow;
  });
  applyPermissions([]);
}

async function showApplication(user) {
  currentUser = user;
  authView.hidden = true;
  applicationView.hidden = false;
  currentUserLabel.hidden = false;
  userSummary.hidden = false;
  logoutButton.hidden = false;
  currentUserLabel.textContent = user.full_name;
  currentRoleLabel.textContent = ROLE_LABELS[user.role] || user.role;
  workspaceRole.textContent = `Vista ${ROLE_LABELS[user.role] || user.role}`;
  applyPermissions(user.permissions);
  await loadAvailability();
  if (user.role === "principal") {
    await loadUsers();
    await loadStockImportRequests();
  }
}

function renderStockImportPreview(preview) {
  currentStockImportPreview = preview;
  stockImportPreview.hidden = false;
  stockImportSummary.textContent = `${preview.file_products} productos · ${formatNumber(preview.total_units)} unidades · ${preview.changed_products} cambios`;

  const errors = [];
  if (preview.missing_skus.length) errors.push(`Faltan SKU: ${preview.missing_skus.join(", ")}`);
  if (preview.unknown_skus.length) errors.push(`SKU desconocidos: ${preview.unknown_skus.join(", ")}`);
  if (preview.duplicate_skus.length) errors.push(`SKU duplicados: ${preview.duplicate_skus.join(", ")}`);
  stockImportErrors.textContent = errors.join(" · ");
  stockImportErrors.hidden = errors.length === 0;
  confirmStockImportButton.disabled = !preview.valid;

  stockImportBody.innerHTML = preview.rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.sku)}</td>
          <td>${escapeHtml(row.product_name)}</td>
          <td>${formatNumber(row.current_physical_confirmed)}</td>
          <td>${formatNumber(row.requested_physical_confirmed)}</td>
          <td class="${row.difference < 0 ? "negative-value" : ""}">${row.difference > 0 ? "+" : ""}${formatNumber(row.difference)}</td>
        </tr>
      `,
    )
    .join("");
}

function renderStockImportRequests(requests) {
  if (!requests.length) {
    stockImportRequestsBody.innerHTML = '<tr><td colspan="6">No hay conteos masivos registrados.</td></tr>';
    return;
  }
  stockImportRequestsBody.innerHTML = requests
    .map(
      (request) => `
        <tr>
          <td>${request.approval_id}</td>
          <td>${escapeHtml(request.status)}</td>
          <td>${request.line_count}</td>
          <td>${formatNumber(request.total_units)}</td>
          <td>${escapeHtml(request.reason)}</td>
          <td>${request.status === "solicitada" ? `<button class="secondary-button compact-action" type="button" data-select-stock-import="${request.approval_id}">Revisar</button>` : ""}</td>
        </tr>
      `,
    )
    .join("");
}

async function loadStockImportRequests() {
  const requests = await apiRequest("/stock-imports");
  renderStockImportRequests(requests);
}

function renderUsers(users) {
  usersBody.innerHTML = users
    .map(
      (user) => `
        <tr>
          <td>${user.id}</td>
          <td>${escapeHtml(user.username)}</td>
          <td>${escapeHtml(user.full_name)}</td>
          <td>${escapeHtml(user.email)}</td>
          <td>${escapeHtml(user.role)}</td>
          <td>${user.is_active ? "Activo" : "Inactivo"}</td>
          <td>${user.must_change_password ? "Si" : "No"}</td>
        </tr>
      `,
    )
    .join("");
}

async function loadUsers() {
  const users = await apiRequest("/users");
  renderUsers(users);
}

async function loadCurrentUser() {
  try {
    const user = await apiRequest("/users/me");
    if (user.must_change_password) {
      currentUser = user;
      showAuthForm(passwordChangeForm);
      currentUser = user;
      setMessage("Debes cambiar la contrasena provisional antes de continuar.", "info");
    } else {
      await showApplication(user);
    }
  } catch (error) {
    if (error.status === 401) {
      showAuthForm(loginForm);
      return;
    }
    throw error;
  }
}

function lineTemplate(type) {
  if (type === "purchase-order") {
    return `
      <div class="line-item">
        <label>
          SKU
          <input name="sku" required />
        </label>
        <label>
          Solicitado
          <input name="requested_quantity" type="number" min="1" required />
        </label>
        <label>
          Descripcion OC
          <input name="original_description" />
        </label>
        <button class="icon-button remove-line" type="button" aria-label="Quitar producto" title="Quitar producto">-</button>
      </div>
    `;
  }

  if (type === "dispatch") {
    return `
      <div class="line-item">
        <label>
          SKU
          <input name="sku" required />
        </label>
        <label>
          Despachado
          <input name="dispatched_quantity" type="number" min="0" required />
        </label>
        <label>
          Faltante
          <input name="missing_quantity" type="number" min="0" value="0" required />
        </label>
        <button class="icon-button remove-line" type="button" aria-label="Quitar producto" title="Quitar producto">-</button>
      </div>
    `;
  }

  return `
    <div class="line-item">
      <label>
        SKU
        <input name="sku" required />
      </label>
      <label>
        Unidades
        <input name="quantity" type="number" min="1" required />
      </label>
      <button class="icon-button remove-line" type="button" aria-label="Quitar producto" title="Quitar producto">-</button>
    </div>
  `;
}

function addLine(container, type) {
  container.insertAdjacentHTML("beforeend", lineTemplate(type));
}

function readLines(container, fields) {
  return [...container.querySelectorAll(".line-item")].map((row) => {
    const item = {};
    fields.forEach((field) => {
      const input = row.querySelector(`[name="${field.name}"]`);
      if (field.number) {
        item[field.name] = Number(input.value || 0);
        return;
      }
      const value = input.value.trim();
      item[field.name] = field.uppercase === false ? value : value.toUpperCase();
    });
    return item;
  });
}

function updateMetrics(rows) {
  const totals = rows.reduce(
    (acc, row) => {
      acc.physical += Number(row.physical_confirmed || 0);
      acc.reserved += Number(row.reserved || 0);
      acc.invoiced += Number(row.invoiced_pending_dispatch || 0);
      acc.blocked += Number(row.blocked_incident || 0);
      return acc;
    },
    { physical: 0, reserved: 0, invoiced: 0, blocked: 0 },
  );

  metricPhysical.textContent = formatNumber(totals.physical);
  metricReserved.textContent = formatNumber(totals.reserved);
  metricInvoiced.textContent = formatNumber(totals.invoiced);
  metricBlocked.textContent = formatNumber(totals.blocked);
}

function renderAvailability(rows) {
  productCountBadge.textContent = `${formatNumber(rows.length)} ${rows.length === 1 ? "producto" : "productos"}`;
  if (!rows.length) {
    availabilityBody.innerHTML = '<tr><td colspan="8">No hay productos cargados.</td></tr>';
    updateMetrics([]);
    return;
  }

  availabilityBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.sku)}</td>
          <td>${escapeHtml(row.name)}</td>
          <td>${formatNumber(row.units_per_case)}</td>
          <td>${formatNumber(row.physical_confirmed)}</td>
          <td>${formatNumber(row.reserved)}</td>
          <td>${formatNumber(row.invoiced_pending_dispatch)}</td>
          <td>${formatNumber(row.blocked_incident)}</td>
          <td>${formatNumber(row.available_to_invoice)}</td>
        </tr>
      `,
    )
    .join("");

  updateMetrics(rows);
}

async function loadAvailability() {
  try {
    const rows = await apiRequest("/products/availability");
    renderAvailability(rows);
    setMessage("Inventario actualizado.", "success");
  } catch (error) {
    availabilityBody.innerHTML =
      '<tr><td colspan="8">La API responde, pero la disponibilidad aun no esta lista.</td></tr>';
    setMessage(error.message, "error");
  }
}

function renderInvoiceTracking(rows) {
  if (!rows.length) {
    trackingInvoicesBody.innerHTML = '<tr><td colspan="6">No hay facturas registradas.</td></tr>';
    return;
  }
  trackingInvoicesBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.invoice_number)}</td>
          <td>${escapeHtml(row.customer_name || "Sin cliente")}</td>
          <td>${escapeHtml(row.status)}</td>
          <td>${formatNumber(row.total_units)}</td>
          <td>${formatNumber(row.pending_units)}</td>
          <td>${formatDate(row.registered_at)}</td>
        </tr>
      `,
    )
    .join("");
}

function renderReservationTracking(rows) {
  if (!rows.length) {
    trackingReservationsBody.innerHTML = '<tr><td colspan="6">No hay reservas registradas.</td></tr>';
    return;
  }
  trackingReservationsBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${row.id}</td>
          <td title="${escapeHtml(row.product_name)}">${escapeHtml(row.sku)}</td>
          <td>${escapeHtml(row.customer_name || "Sin cliente")}</td>
          <td>${formatNumber(row.quantity)}</td>
          <td>${escapeHtml(row.status)}</td>
          <td>${formatDate(row.created_at)}</td>
        </tr>
      `,
    )
    .join("");
}

function renderPendingDispatches(rows) {
  if (!rows.length) {
    trackingDispatchesBody.innerHTML = '<tr><td colspan="6">No hay productos pendientes de despacho.</td></tr>';
    return;
  }
  trackingDispatchesBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.invoice_number)}</td>
          <td>${escapeHtml(row.customer_name || "Sin cliente")}</td>
          <td title="${escapeHtml(row.product_name)}">${escapeHtml(row.sku)}</td>
          <td>${formatNumber(row.invoiced_quantity)}</td>
          <td>${formatNumber(row.dispatched_quantity)}</td>
          <td>${formatNumber(row.pending_quantity)}</td>
        </tr>
      `,
    )
    .join("");
}

function renderPurchaseOrders(rows) {
  if (!rows.length) {
    purchaseOrdersBody.innerHTML = '<tr><td colspan="7">No hay OCs registradas.</td></tr>';
    return;
  }
  purchaseOrdersBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${row.id}</td>
          <td>${escapeHtml(row.chain_name)}</td>
          <td>${escapeHtml(row.order_number)}</td>
          <td>${escapeHtml(row.status)}</td>
          <td>${formatNumber(row.total_units)}</td>
          <td>${formatNumber(row.line_count)}</td>
          <td>${formatDate(row.created_at)}</td>
        </tr>
      `,
    )
    .join("");
}

function renderIncidents(rows) {
  if (!rows.length) {
    incidentsBody.innerHTML = '<tr><td colspan="8">No hay incidencias registradas.</td></tr>';
    return;
  }
  incidentsBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${row.id}</td>
          <td>${escapeHtml(row.status)}</td>
          <td>${escapeHtml(row.incident_type)}</td>
          <td title="${escapeHtml(row.product_name || "")}">${escapeHtml(row.sku || "-")}</td>
          <td>${escapeHtml(row.invoice_number || "-")}</td>
          <td>${escapeHtml(row.purchase_order_reference || row.customer_name || "-")}</td>
          <td title="${escapeHtml(row.description)}">${escapeHtml(row.description)}</td>
          <td>${formatDate(row.created_at)}</td>
        </tr>
      `,
    )
    .join("");
}

async function loadTracking() {
  const [invoices, reservations, dispatches] = await Promise.all([
    apiRequest("/invoices"),
    apiRequest("/reservations"),
    apiRequest("/dispatches/pending"),
  ]);
  renderInvoiceTracking(invoices);
  renderReservationTracking(reservations);
  renderPendingDispatches(dispatches);
  setMessage("Seguimiento actualizado.", "success");
}

async function loadPurchaseOrders() {
  const rows = await apiRequest("/purchase-orders");
  renderPurchaseOrders(rows);
  setMessage("Ordenes de compra actualizadas.", "success");
}

async function loadIncidents() {
  const rows = await apiRequest("/incidents");
  renderIncidents(rows);
  setMessage("Incidencias actualizadas.", "success");
}

async function checkApi() {
  try {
    const data = await apiRequest("/health");
    setApiStatus(data.status === "ok" ? "API conectada" : "API responde", true);
    const setup = await apiRequest("/auth/setup-status");
    if (setup.needs_bootstrap) {
      showAuthForm(bootstrapForm);
      setMessage("Crea el primer usuario principal para iniciar.", "info");
    } else {
      await loadCurrentUser();
    }
  } catch (error) {
    setApiStatus("API sin conexion", false);
    setMessage("Backend no disponible.", "error");
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(loginForm);
  const payload = {
    username: form.get("username").trim().toLowerCase(),
    password: form.get("password"),
  };

  try {
    const data = await apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    loginForm.reset();
    if (data.user.must_change_password) {
      showAuthForm(passwordChangeForm);
      setMessage("Debes cambiar la contrasena provisional antes de continuar.", "info");
    } else {
      await showApplication(data.user);
    }
  } catch (error) {
    setMessage(error.message, "error");
  }
});

bootstrapForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(bootstrapForm);
  const payload = {
    full_name: form.get("full_name").trim(),
    username: form.get("username").trim().toLowerCase(),
    email: form.get("email").trim().toLowerCase(),
    password: form.get("password"),
    reason: form.get("reason").trim(),
  };

  try {
    await apiRequest("/users/bootstrap", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    bootstrapForm.reset();
    showAuthForm(loginForm);
    setMessage("Usuario principal creado. Ya puedes ingresar.", "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
});

passwordChangeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(passwordChangeForm);
  const newPassword = form.get("new_password");
  if (newPassword !== form.get("confirm_password")) {
    setMessage("Las nuevas contrasenas no coinciden.", "error");
    return;
  }

  const payload = {
    current_password: form.get("current_password"),
    new_password: newPassword,
    reason: form.get("reason"),
  };

  try {
    const data = await apiRequest("/auth/change-password", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    passwordChangeForm.reset();
    showAuthForm(loginForm);
    setMessage(data.message, "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
});

logoutButton.addEventListener("click", async () => {
  try {
    await apiRequest("/auth/logout", { method: "POST", body: "{}" });
  } catch (error) {
    if (error.status !== 401) {
      setMessage(error.message, "error");
      return;
    }
  }
  showAuthForm(loginForm);
  setMessage("Sesion cerrada.", "success");
});

purchaseOrderForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(purchaseOrderForm);
  const payload = {
    chain_name: form.get("chain_name").trim(),
    order_number: form.get("order_number").trim(),
    notes: form.get("notes").trim() || null,
    reason: form.get("reason").trim(),
    lines: readLines(purchaseOrderLines, [
      { name: "sku" },
      { name: "requested_quantity", number: true },
      { name: "original_description", uppercase: false },
    ]).map((line) => ({
      ...line,
      original_description: line.original_description?.trim() || null,
    })),
  };

  try {
    const data = await apiRequest("/purchase-orders", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setMessage(`OC registrada: ${data.chain_name} / ${data.order_number}`, "success");
    purchaseOrderForm.reset();
    purchaseOrderLines.innerHTML = "";
    addLine(purchaseOrderLines, "purchase-order");
    await loadPurchaseOrders();
  } catch (error) {
    setMessage(error.message, "error");
  }
});

invoiceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(invoiceForm);
  const payload = {
    invoice_number: form.get("invoice_number").trim(),
    customer_name: form.get("customer_name").trim() || null,
    reason: form.get("reason").trim(),
    lines: readLines(invoiceLines, [
      { name: "sku" },
      { name: "quantity", number: true },
    ]),
  };

  try {
    const data = await apiRequest("/invoices", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setMessage(`Factura registrada: ${data.invoice_number}`, "success");
    invoiceForm.reset();
    invoiceLines.innerHTML = "";
    addLine(invoiceLines, "invoice");
    await loadAvailability();
  } catch (error) {
    setMessage(error.message, "error");
  }
});

reservationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(reservationForm);
  const payload = {
    sku: form.get("sku").trim().toUpperCase(),
    quantity: Number(form.get("quantity") || 0),
    customer_name: form.get("customer_name").trim() || null,
    reason: form.get("reason").trim(),
  };

  try {
    const data = await apiRequest("/reservations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setMessage(`Reserva creada: ${data.sku} x ${formatNumber(data.quantity)}`, "success");
    reservationForm.reset();
    await loadAvailability();
  } catch (error) {
    setMessage(error.message, "error");
  }
});

dispatchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(dispatchForm);
  const payload = {
    invoice_number: form.get("invoice_number").trim(),
    reason: form.get("reason").trim(),
    lines: readLines(dispatchLines, [
      { name: "sku" },
      { name: "dispatched_quantity", number: true },
      { name: "missing_quantity", number: true },
    ]),
  };

  try {
    const data = await apiRequest("/dispatches", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setMessage(`Despacho registrado para factura ${data.invoice_number}`, "success");
    dispatchForm.reset();
    dispatchLines.innerHTML = "";
    addLine(dispatchLines, "dispatch");
    await loadAvailability();
  } catch (error) {
    setMessage(error.message, "error");
  }
});

adjustmentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(adjustmentForm);
  const payload = {
    sku: form.get("sku").trim().toUpperCase(),
    requested_physical_confirmed: Number(form.get("requested_physical_confirmed") || 0),
    reason: form.get("reason").trim(),
  };

  try {
    const data = await apiRequest("/stock-adjustments", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setMessage(`Solicitud de ajuste creada: ${data.approval_id}`, "success");
    adjustmentForm.reset();
  } catch (error) {
    setMessage(error.message, "error");
  }
});

stockTemplateButton.addEventListener("click", async () => {
  try {
    const response = await fetch(buildApiUrl("/stock-imports/template"), {
      credentials: "include",
    });
    if (!response.ok) throw new Error("No se pudo descargar la plantilla.");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "plantilla_conteo_fisico.csv";
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    setMessage(error.message, "error");
  }
});

stockImportForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(stockImportForm);
  const file = form.get("stock_file");
  const upload = new FormData();
  upload.append("file", file);

  try {
    const preview = await apiRequest("/stock-imports/preview", {
      method: "POST",
      body: upload,
    });
    renderStockImportPreview(preview);
    setMessage(
      preview.valid
        ? "Archivo completo. Revisa las diferencias antes de enviarlo."
        : "El archivo tiene observaciones y no puede enviarse todavia.",
      preview.valid ? "success" : "error",
    );
  } catch (error) {
    currentStockImportPreview = null;
    stockImportPreview.hidden = true;
    setMessage(error.message, "error");
  }
});

confirmStockImportButton.addEventListener("click", async () => {
  if (!currentStockImportPreview?.valid) return;
  const form = new FormData(stockImportForm);
  const payload = {
    reason: form.get("reason").trim(),
    lines: currentStockImportPreview.rows.map((row) => ({
      sku: row.sku,
      physical_confirmed: row.requested_physical_confirmed,
    })),
  };

  try {
    const request = await apiRequest("/stock-imports", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setMessage(`Conteo enviado para aprobacion: solicitud ${request.approval_id}.`, "success");
    stockImportForm.reset();
    stockImportPreview.hidden = true;
    currentStockImportPreview = null;
    if (currentUser?.role === "principal") await loadStockImportRequests();
  } catch (error) {
    setMessage(error.message, "error");
  }
});

approvalForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const decision = event.submitter.dataset.decision;
  const form = new FormData(approvalForm);
  const approvalId = Number(form.get("approval_id") || 0);
  const payload = {
    reason: form.get("reason").trim(),
  };

  try {
    const data = await apiRequest(`/stock-adjustments/${approvalId}/${decision}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setMessage(`Solicitud ${data.status}: ${data.sku}`, "success");
    approvalForm.reset();
    await loadAvailability();
  } catch (error) {
    setMessage(error.message, "error");
  }
});

bulkApprovalForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const decision = event.submitter.dataset.decision;
  const form = new FormData(bulkApprovalForm);
  const approvalId = Number(form.get("approval_id") || 0);
  const payload = { reason: form.get("reason").trim() };

  try {
    const result = await apiRequest(`/stock-imports/${approvalId}/${decision}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setMessage(`Conteo masivo ${result.status}: solicitud ${result.approval_id}.`, "success");
    bulkApprovalForm.reset();
    await Promise.all([loadAvailability(), loadStockImportRequests()]);
  } catch (error) {
    setMessage(error.message, "error");
  }
});

refreshStockImportsButton.addEventListener("click", async () => {
  try {
    await loadStockImportRequests();
    setMessage("Lista de conteos actualizada.", "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
});

userCreateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(userCreateForm);
  const payload = {
    full_name: form.get("full_name").trim(),
    username: form.get("username").trim().toLowerCase(),
    email: form.get("email").trim().toLowerCase(),
    temporary_password: form.get("temporary_password"),
    role: form.get("role"),
    reason: form.get("reason").trim(),
  };

  try {
    const user = await apiRequest("/users", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setMessage(`Usuario creado: ${user.full_name} (${user.role})`, "success");
    userCreateForm.reset();
    await loadUsers();
  } catch (error) {
    setMessage(error.message, "error");
  }
});

userResetForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(userResetForm);
  const userId = Number(form.get("user_id"));
  const payload = {
    temporary_password: form.get("temporary_password"),
    reason: form.get("reason").trim(),
  };

  try {
    const user = await apiRequest(`/users/${userId}/reset-password`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setMessage(`Contrasena restablecida para ${user.username}.`, "success");
    userResetForm.reset();
    if (currentUser && userId === currentUser.id) {
      showAuthForm(loginForm);
      setMessage("Tu contrasena fue restablecida. Ingresa con la clave provisional.", "success");
    } else {
      await loadUsers();
    }
  } catch (error) {
    setMessage(error.message, "error");
  }
});

userUpdateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(userUpdateForm);
  const payload = { reason: form.get("reason").trim() };
  const fullName = form.get("full_name").trim();
  const role = form.get("role");
  const isActive = form.get("is_active");
  if (fullName) payload.full_name = fullName;
  if (role) payload.role = role;
  if (isActive) payload.is_active = isActive === "true";

  try {
    const userId = Number(form.get("user_id"));
    const user = await apiRequest(`/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    setMessage(`Usuario actualizado: ${user.full_name}`, "success");
    userUpdateForm.reset();
    if (currentUser && userId === currentUser.id) {
      if (!user.is_active) {
        showAuthForm(loginForm);
        setMessage("Tu cuenta fue desactivada. La sesion se cerro.", "info");
      } else {
        await loadCurrentUser();
      }
    } else {
      await loadUsers();
    }
  } catch (error) {
    setMessage(error.message, "error");
  }
});

document.addEventListener("click", (event) => {
  const moduleButton = event.target.closest("[data-module]");
  if (moduleButton) {
    activateModule(moduleButton.dataset.module);
    if (moduleButton.dataset.module === "tracking") {
      loadTracking().catch((error) => setMessage(error.message, "error"));
    }
    if (moduleButton.dataset.module === "purchase-orders") {
      loadPurchaseOrders().catch((error) => setMessage(error.message, "error"));
    }
    if (moduleButton.dataset.module === "incidents") {
      loadIncidents().catch((error) => setMessage(error.message, "error"));
    }
    return;
  }

  const addButton = event.target.closest("[data-add-line]");
  if (addButton) {
    const type = addButton.dataset.addLine;
    const container =
      type === "dispatch"
        ? dispatchLines
        : type === "purchase-order"
          ? purchaseOrderLines
          : invoiceLines;
    addLine(container, type);
  }

  const removeButton = event.target.closest(".remove-line");
  if (removeButton) {
    const list = removeButton.closest(".line-list");
    if (list.querySelectorAll(".line-item").length > 1) {
      removeButton.closest(".line-item").remove();
    }
  }

  const selectImportButton = event.target.closest("[data-select-stock-import]");
  if (selectImportButton) {
    bulkApprovalForm.elements.approval_id.value = selectImportButton.dataset.selectStockImport;
    bulkApprovalForm.elements.approval_id.focus();
  }
});

refreshButton.addEventListener("click", loadAvailability);
refreshTrackingButton.addEventListener("click", () => {
  loadTracking().catch((error) => setMessage(error.message, "error"));
});
refreshPurchaseOrdersButton.addEventListener("click", () => {
  loadPurchaseOrders().catch((error) => setMessage(error.message, "error"));
});
refreshIncidentsButton.addEventListener("click", () => {
  loadIncidents().catch((error) => setMessage(error.message, "error"));
});

addLine(invoiceLines, "invoice");
addLine(dispatchLines, "dispatch");
addLine(purchaseOrderLines, "purchase-order");
checkApi();
