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
const adjustmentForm = document.querySelector("#adjustment-form");
const approvalForm = document.querySelector("#approval-form");
const invoiceLines = document.querySelector("#invoice-lines");
const dispatchLines = document.querySelector("#dispatch-lines");
const currentUserLabel = document.querySelector("#current-user-label");
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

const API_BASE_URL = "http://127.0.0.1:8000";
let currentUser = null;

function formatNumber(value) {
  return Number(value || 0).toLocaleString("es-EC");
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

async function apiRequest(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const response = await fetch(`${API_BASE_URL}${path}`, {
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
}

function showAuthForm(formToShow) {
  currentUser = null;
  authView.hidden = false;
  applicationView.hidden = true;
  currentUserLabel.hidden = true;
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
  logoutButton.hidden = false;
  currentUserLabel.textContent = `${user.full_name} · ${user.role}`;
  applyPermissions(user.permissions);
  await loadAvailability();
  if (user.role === "principal") {
    await loadUsers();
  }
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
      item[field.name] = field.number ? Number(input.value || 0) : input.value.trim().toUpperCase();
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
  const addButton = event.target.closest("[data-add-line]");
  if (addButton) {
    addLine(addButton.dataset.addLine === "dispatch" ? dispatchLines : invoiceLines, addButton.dataset.addLine);
  }

  const removeButton = event.target.closest(".remove-line");
  if (removeButton) {
    const list = removeButton.closest(".line-list");
    if (list.querySelectorAll(".line-item").length > 1) {
      removeButton.closest(".line-item").remove();
    }
  }
});

refreshButton.addEventListener("click", loadAvailability);

addLine(invoiceLines, "invoice");
addLine(dispatchLines, "dispatch");
checkApi();
