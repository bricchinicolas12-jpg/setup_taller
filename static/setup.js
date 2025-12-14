// ============================
// setup.js (LIMPIO)
// ============================

// ---------- GLOBALES / CACHES ----------
let ingresoHoraMem = "";
let salidaHoraMem  = "";
let regresoHoraMem = "";
let modoAccionLista = null; // "duplicar" | "reabrir" | null
let ordenSeleccionadaLista = null;


let retiroFecha = "";
let retiroHora  = "";

let listaOrdenes  = [];
let listaClientes = [];
let listaEquipos  = [];

let mapaRepuestos = {}; // nombre -> costo

const ESTADOS_EN_PROCESO = new Set([
  "EN REPARACION",
  "EN SOS",
  "EN WERTECH",
  "EN EKON",
  "EN AIR",
  "EN SERVIPRINT",
  "EN NICO GORI"
]);
const ESTADO_TERMINADA = "TERMINADA";
const ESTADO_RETIRADA  = "RETIRADA";
// ============================
// utils.js (ARREGLADO)
// ============================

// ---------- DEBOUNCE ----------
function debounce(fn, ms = 150) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

// ---------- NORMALIZACIÓN / BÚSQUEDA ----------
function normalizeText(s) {
  return String(s ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // quita tildes
    .trim();
}

/**
 * matchQuery(text, query)
 * - query puede tener varias palabras (separadas por espacio)
 * - todas las palabras deben aparecer (AND)
 * - ignora mayúsculas y tildes
 */
function matchQuery(text, query) {
  const q = normalizeText(query);
  if (!q) return true;

  const t = normalizeText(text);
  const parts = q.split(/\s+/).filter(Boolean);

  return parts.every(p => t.includes(p));
}

// ---------- FECHA / HORA ----------
function pad2(n) {
  return String(n).padStart(2, "0");
}

function nowISODate() {
  const d = new Date();
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function nowTimeHM() {
  const d = new Date();
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

// ---------- TOAST ----------
function showToast(message, type = "info", ms = 2500) {
  const el = document.getElementById("toast");
  if (!el) {
    // fallback si no existe el div toast
    if (type === "error") console.error(message);
    else console.log(message);
    return;
  }

  el.textContent = String(message ?? "");
  el.style.display = "block";

  // clases opcionales (si tenés CSS para .toast.ok/.toast.error/.toast.info)
  el.classList.remove("ok", "error", "info");
  if (type === "ok" || type === "success") el.classList.add("ok");
  else if (type === "error") el.classList.add("error");
  else el.classList.add("info");

  clearTimeout(el.__toastTimer);
  el.__toastTimer = setTimeout(() => {
    el.style.display = "none";
  }, ms);
}

// ---------- FETCH JSON SAFE ----------
/**
 * fetchJSONSafe(url, options)
 * - Devuelve el JSON si existe
 * - Si hay error HTTP, intenta leer JSON y devuelve { ok:false, error:... }
 * - No revienta si el backend devuelve HTML/texto
 */
async function fetchJSONSafe(url, options = {}) {
  let resp;
  try {
    resp = await fetch(url, options);
  } catch (err) {
    return { ok: false, error: "No se pudo conectar con el servidor." };
  }

  const contentType = (resp.headers.get("content-type") || "").toLowerCase();
  let data = null;

  try {
    if (contentType.includes("application/json")) {
      data = await resp.json();
    } else {
      // puede ser texto/HTML
      const txt = await resp.text();
      data = txt ? { raw: txt } : null;
    }
  } catch (_e) {
    data = null;
  }

  if (!resp.ok) {
    // intenta sacar un mensaje humano del JSON si existe
    const msg =
      (data && (data.error || data.message)) ||
      `Error HTTP ${resp.status}`;

    return { ok: false, status: resp.status, error: msg, data };
  }

  // si el backend ya devuelve {ok:...} lo respetamos; si devuelve objeto normal, lo devolvemos
  if (data && typeof data === "object") return data;
  return { ok: true, data };
}

// ---------- HELPERS ----------
function setValue(id, v = "") {
  const el = document.getElementById(id);
  if (el) el.value = v;
}
function setChecked(id, v = false) {
  const el = document.getElementById(id);
  if (el) el.checked = !!v;
}
function resetSelect(id) {
  const el = document.getElementById(id);
  if (el) el.selectedIndex = 0;
}
function setDisabled(id, disabled) {
  const el = document.getElementById(id);
  if (el) el.disabled = !!disabled;
}
function normalizarEstado(s) {
  return String(s || "")
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "") // quita tildes
    .trim()
    .toUpperCase()
    .replace(/\s+/g, " ");
}


function setIngresoAhoraSiVacio() {
  const f = document.getElementById("fecha");
  const h = document.getElementById("hora_ingreso");
  if (f && !f.value) f.value = nowISODate();
  if (!ingresoHoraMem) ingresoHoraMem = nowTimeHM();
  if (h && !h.value) h.value = ingresoHoraMem;
}
function setSalidaAhoraSiVacia() {
  const fs = document.getElementById("fecha_salida");
  const hs = document.getElementById("hora_salida");
  if (fs && !fs.value) fs.value = nowISODate();
  if (!salidaHoraMem) salidaHoraMem = nowTimeHM();
  if (hs && !hs.value) hs.value = salidaHoraMem;
}
function setRegresoAhora() {
  const fr = document.getElementById("fecha_regreso");
  const hr = document.getElementById("hora_regreso");
  if (fr && !fr.value) fr.value = nowISODate();
  if (!regresoHoraMem) regresoHoraMem = nowTimeHM();
  if (hr && !hr.value) hr.value = regresoHoraMem;
}
function setRetiroAhoraMem() {
  retiroFecha = nowISODate();
  retiroHora  = nowTimeHM();
}

function setEstado(nuevo) {
  const sel  = document.getElementById("estado");
  const chip = document.getElementById("estado_display");
  if (sel) sel.value = nuevo;
  if (chip) chip.textContent = nuevo;
}

function ordenCargada() {
  const nro = document.getElementById("nro")?.value;
  return !!(nro && String(nro).trim());
}

// ---------- TABS ----------
const tabButtons = document.querySelectorAll(".tab-button");
const tabPanes   = document.querySelectorAll(".tab-pane");

function cambiarTab(id) {
  tabButtons.forEach(b => b.classList.toggle("active", b.dataset.tab === id));
  tabPanes.forEach(p => p.classList.toggle("active", p.id === id));
}
tabButtons.forEach(btn => btn.addEventListener("click", () => cambiarTab(btn.dataset.tab)));
function irATabFormulario() { cambiarTab("form"); }

// ---------- MULTI SELECT UTILS ----------
function getMultiValues(selectId) {
  const sel = document.getElementById(selectId);
  if (!sel) return [];
  return Array.from(sel.selectedOptions).map(o => o.value).filter(Boolean);
}
function setMultiValues(selectId, values) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  const setVals = new Set(values);
  Array.from(sel.options).forEach(o => { o.selected = setVals.has(o.value); });
}

// ---------- TOKEN APPEND ----------
function appendToken(inputEl, token) {
  const t = (token || "").trim();
  if (!t) return;
  const actual = (inputEl.value || "").trim();
  inputEl.value = actual ? (actual + " + " + t) : t;
}
function habilitarAppendDesdeSelect(selectId, inputId, opts = {}) {
  const { clearAfter = true } = opts;
  const sel = document.getElementById(selectId);
  const inp = document.getElementById(inputId);
  if (!sel || !inp) return;

  sel.addEventListener("change", () => {
    const seleccionadas = Array.from(sel.selectedOptions)
      .map(o => (o.value || "").trim())
      .filter(v => v && !v.startsWith("-- Seleccionar"));

    if (seleccionadas.length === 0) return;
    seleccionadas.forEach(v => appendToken(inp, v));

    if (clearAfter) {
      if (sel.multiple) Array.from(sel.options).forEach(o => (o.selected = false));
      else sel.value = "";
    }
    inp.focus();
  });
}

// ---------- CAMPOS COMBINADOS (falla/reparación/repuestos) ----------
function combinarSeleccion(selectId, comentarioId) {
  const sel   = document.getElementById(selectId);
  const input = document.getElementById(comentarioId);

  let base = "";
  if (sel?.multiple) base = getMultiValues(selectId).join(" + ");
  else base = sel?.value || "";

  const com = (input?.value || "").trim();
  if (!base && !com) return "";
  if (!base) return com;
  if (!com) return base;
  return base + " - " + com;
}

function descomponerCampo(valor, selectId, comentarioId) {
  const sel   = document.getElementById(selectId);
  const input = document.getElementById(comentarioId);
  if (!sel || !input) return;

  const v = (valor == null) ? "" : String(valor).trim();

  const limpiarSeleccion = () => {
    if (sel.multiple) Array.from(sel.options).forEach(o => (o.selected = false));
    else sel.value = "";
  };

  if (!v) {
    limpiarSeleccion();
    input.value = "";
    return;
  }

  if (!v.includes(" - ")) {
    limpiarSeleccion();
    input.value = v;
    return;
  }

  const idx  = v.indexOf(" - ");
  const base = (idx >= 0) ? v.slice(0, idx).trim() : v.trim();
  const com  = (idx >= 0) ? v.slice(idx + 3).trim() : "";

  const partes = base.split("+").map(s => s.trim()).filter(Boolean);

  if (sel.multiple) {
    setMultiValues(selectId, partes);
    input.value = com;
  } else {
    sel.value = partes[0] || "";
    const resto = partes.slice(1).join(" + ");
    input.value = [resto, com].filter(Boolean).join(" - ");
  }
}

// ---------- SELECT SEARCH ----------
function makeSelectSearch(inputId, selectId) {
  const inp = document.getElementById(inputId);
  const sel = document.getElementById(selectId);
  if (!inp || !sel) return;

  const ensureCache = () => {
    if (!sel.__allOptions) {
      sel.__allOptions = Array.from(sel.options).map(o => ({
        value: o.value,
        text: o.textContent
      }));
    }
  };

  const apply = () => {
    ensureCache();
    const q = inp.value || "";
    const prevSelected = new Set(Array.from(sel.selectedOptions).map(o => o.value));

    sel.innerHTML = "";
    sel.__allOptions.forEach(o => {
      const combined = `${o.value} | ${o.text}`;
      if (!matchQuery(combined, q)) return;
      const opt = document.createElement("option");
      opt.value = o.value;
      opt.textContent = o.text;
      opt.selected = prevSelected.has(o.value);
      sel.appendChild(opt);
    });
  };

  inp.addEventListener("input", debounce(apply, 120));
  inp.addEventListener("change", apply);
  apply();
}

// ---------- SELECTS DESDE API ----------
async function cargarSelect(url, selectId, labelField) {
  const resp = await fetch(url);
  if (!resp.ok) {
    console.error("cargarSelect() error:", url, resp.status);
    return;
  }

  const data = await resp.json();
  const sel  = document.getElementById(selectId);
  if (!sel) return;

  const seleccionActual = sel.multiple
    ? Array.from(sel.selectedOptions).map(o => o.value)
    : [sel.value];

  sel.innerHTML = "";

  if (!sel.multiple) {
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = "-- Seleccionar --";
    sel.appendChild(opt0);
  }

  data.forEach(row => {
    const val = (row.descripcion ?? row.nombre ?? "").toString().trim();
    if (!val) return;
    const opt = document.createElement("option");
    opt.value = val;
    opt.textContent = row[labelField] || val;
    sel.appendChild(opt);
  });

  sel.__allOptions = Array.from(sel.options).map(o => ({ value: o.value, text: o.textContent }));

  if (sel.multiple) setMultiValues(selectId, seleccionActual.filter(Boolean));
  else sel.value = seleccionActual[0] || "";
}

async function cargarSelectRepuestos() {
  const resp = await fetch("/api/repuestos");
  if (!resp.ok) return;

  const datos = await resp.json();
  const sel   = document.getElementById("repuesto_select");
  if (!sel) return;

  const prevSelected = new Set(Array.from(sel.selectedOptions).map(o => o.value));

  sel.innerHTML = "";
  mapaRepuestos = {};

  datos.forEach(r => {
    const nombre  = (r.nombre || "").trim();
    const detalle = (r.detalle || r.descripcion || "").trim();
    const costo   = r.costo ?? 0;
    if (!nombre) return;

    const opt = document.createElement("option");
    opt.value = nombre;
    opt.textContent = detalle ? `${nombre} — ${detalle}` : nombre;
    opt.selected = prevSelected.has(nombre);
    sel.appendChild(opt);

    mapaRepuestos[nombre] = parseFloat(costo) || 0;
  });

  sel.__allOptions = Array.from(sel.options).map(o => ({ value: o.value, text: o.textContent }));
}

async function cargarListasAuxiliares() {
  await Promise.all([
    cargarSelect("/api/fallas",       "falla_select",      "descripcion"),
    cargarSelect("/api/reparaciones", "reparacion_select", "descripcion"),
  ]);
  await cargarSelectRepuestos();
}

// ---------- CATÁLOGOS (TABLAS) ----------
async function cargarTablasCatalogos() {
  try {
    // FALLAS
    let resp = await fetch("/api/fallas");
    if (resp.ok) {
      const data = await resp.json();
      const tbody = document.querySelector("#tablaCatFallas tbody");
      if (tbody) {
        tbody.innerHTML = "";
        data.forEach(f => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${f.id}</td>
            <td>${f.descripcion || ""}</td>
            <td><button type="button" class="btnDelFalla" data-id="${f.id}">Eliminar</button></td>
          `;
          tbody.appendChild(tr);
        });
      }
    }

    // REPARACIONES
    resp = await fetch("/api/reparaciones");
    if (resp.ok) {
      const data = await resp.json();
      const tbody = document.querySelector("#tablaCatReparaciones tbody");
      if (tbody) {
        tbody.innerHTML = "";
        data.forEach(rp => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${rp.id}</td>
            <td>${rp.descripcion || ""}</td>
            <td><button type="button" class="btnDelReparacion" data-id="${rp.id}">Eliminar</button></td>
          `;
          tbody.appendChild(tr);
        });
      }
    }

    // REPUESTOS
    resp = await fetch("/api/repuestos");
    if (resp.ok) {
      const data = await resp.json();
      const tbody = document.querySelector("#tablaCatRepuestos tbody");
      if (tbody) {
        tbody.innerHTML = "";
        data.forEach(r => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${r.id}</td>
            <td>${r.nombre || ""}</td>
            <td>${r.detalle || r.descripcion || ""}</td>
            <td>${(r.costo ?? "")}</td>
            <td><button type="button" class="btnDelRepuesto" data-id="${r.id}">Eliminar</button></td>
          `;
          tbody.appendChild(tr);
        });
      }
    }
  } catch (err) {
    console.error("cargarTablasCatalogos() falló:", err);
  }
}

document.addEventListener("click", async (e) => {
  const b1 = e.target.closest(".btnDelFalla");
  if (b1) {
    if (!confirm("¿Eliminar esta falla?")) return;
    try {
      await fetchJSONSafe(`/api/fallas/${b1.dataset.id}`, { method: "DELETE" });
      await cargarListasAuxiliares();
      await cargarTablasCatalogos();
      showToast("Falla eliminada", "ok");
    } catch (err) { showToast(err.message, "error"); }
    return;
  }

  const b2 = e.target.closest(".btnDelReparacion");
  if (b2) {
    if (!confirm("¿Eliminar esta reparación?")) return;
    try {
      await fetchJSONSafe(`/api/reparaciones/${b2.dataset.id}`, { method: "DELETE" });
      await cargarListasAuxiliares();
      await cargarTablasCatalogos();
      showToast("Reparación eliminada", "ok");
    } catch (err) { showToast(err.message, "error"); }
    return;
  }

  const b3 = e.target.closest(".btnDelRepuesto");
  if (b3) {
    if (!confirm("¿Eliminar este repuesto?")) return;
    try {
      await fetchJSONSafe(`/api/repuestos/${b3.dataset.id}`, { method: "DELETE" });
      await cargarListasAuxiliares();
      await cargarTablasCatalogos();
      showToast("Repuesto eliminado", "ok");
    } catch (err) { showToast(err.message, "error"); }
    return;
  }
});

// ---------- IMPORTE POR REPUESTOS ----------
function normalizarTokensRepuestos(str) {
  return (str || "").split("+").map(s => s.trim()).filter(Boolean);
}
function recalcularImportePorRepuestos() {
  const inpRep = document.getElementById("repuesto_comentario");
  const inpImp = document.getElementById("importe");
  if (!inpRep || !inpImp) return;

  if (inpImp.dataset.base == null || inpImp.dataset.base === "") {
    const baseInicial = parseFloat(String(inpImp.value || "0").replace(",", ".")) || 0;
    inpImp.dataset.base = String(baseInicial);
  }
  const base = parseFloat(inpImp.dataset.base) || 0;

  const tokens = normalizarTokensRepuestos(inpRep.value);
  let suma = 0;
  tokens.forEach(nombre => {
    const costo = mapaRepuestos[nombre];
    if (costo != null) suma += (parseFloat(costo) || 0);
  });

  inpImp.value = (base + suma).toFixed(2);
}

// ---------- RETIRO UI ----------
function renderRetiroUI(fecha, hora, estado) {
  const box = document.getElementById("retiro_box");
  const txt = document.getElementById("retiro_texto");
  if (!box || !txt) return;

  if ((estado || "").trim() !== "RETIRADA") {
    box.style.display = "none";
    txt.textContent = "—";
    return;
  }

  box.style.display = "block";
  const f = (fecha || "").slice(0, 10);
  const h = (hora || "").slice(0, 5);
  txt.textContent = (f || h) ? `${f || "---- -- --"} ${h || "--:--"}` : "—";
}

// ---------- ORDEN: UI ACCIONES ----------
function actualizarAccionesOrdenUI() {
  const idRaw = document.getElementById("nro")?.value || "";
  const id = String(idRaw).trim();

  const estadoRaw = document.getElementById("estado")?.value || "";
  const estado = normalizarEstado(estadoRaw); // asegurate que devuelve strings tipo "EN REPARACION"

  const existeOrden = id !== "";

  const bSalida    = document.getElementById("btnRegistrarSalida");
  const bTerminada = document.getElementById("btnMarcarTerminada");
  const bRetirada  = document.getElementById("btnMarcarRetirada");

  const setB = (btn, disabled) => { if (btn) btn.disabled = !!disabled; };

  // Si no hay orden cargada: todo bloqueado
  if (!existeOrden) {
    setB(bSalida, true);
    setB(bTerminada, true);
    setB(bRetirada, true);
    return;
  }

  // Regla de “en curso”: EN SOS / EN AIR / EN WERTECH / EN REPARACION / etc.
  const enCurso = estado.startsWith("EN ");

  if (estado === "RETIRADA") {
    setB(bSalida, true);
    setB(bTerminada, true);
    setB(bRetirada, true);
    return;
  }

  if (estado === "TERMINADA") {
    setB(bSalida, true);
    setB(bTerminada, true);
    setB(bRetirada, false);
    return;
  }

  if (estado === "SUSPENDIDA") {
    setB(bSalida, true);
    setB(bTerminada, true);
    setB(bRetirada, true);
    return;
  }

  // Cualquier estado “en curso” permite registrar salida y terminar
  if (enCurso) {
    setB(bSalida, false);
    setB(bTerminada, false);
    setB(bRetirada, true);
    return;
  }

  // fallback (por si aparece un estado raro)
  setB(bSalida, true);
  setB(bTerminada, true);
  setB(bRetirada, true);
}



// ---------- ORDEN: FORM ----------
function leerFormulario() {
  const selCliente = document.getElementById("cliente_select_form");
  const selEquipo  = document.getElementById("equipo_select_form");

  const hi = document.getElementById("hora_ingreso");
  const hs = document.getElementById("hora_salida");
  const hr = document.getElementById("hora_regreso");

  const fallaStr      = combinarSeleccion("falla_select", "falla_comentario");
  const reparacionStr = combinarSeleccion("reparacion_select", "reparacion_comentario");
  const repuestosStr  = (document.getElementById("repuesto_comentario")?.value || "");

  return {
    cliente_id: selCliente?.value || null,
    equipo_id:  selEquipo?.value  || null,

    fecha:         document.getElementById("fecha")?.value || "",
    fecha_salida:  document.getElementById("fecha_salida")?.value || "",
    fecha_regreso: document.getElementById("fecha_regreso")?.value || "",

    hora_ingreso: (hi?.value || ingresoHoraMem || ""),
    hora_salida:  (hs?.value || salidaHoraMem  || ""),
    hora_regreso: (hr?.value || regresoHoraMem || ""),

    telefono_contacto: document.getElementById("telefono")?.value || "",

    observaciones: document.getElementById("observaciones")?.value || "",
    accesorios:    document.getElementById("accesorios")?.value || "",

    falla:      fallaStr,
    reparacion: reparacionStr,
    repuestos:  repuestosStr,

    importe: document.getElementById("importe")?.value || "",
    estado:  document.getElementById("estado")?.value || "EN REPARACION",

    fecha_retiro: retiroFecha || "",
    hora_retiro:  retiroHora  || ""
  };
}

function validarClienteYEquipo() {
  const clienteId = document.getElementById("cliente_select_form")?.value;
  const equipoId  = document.getElementById("equipo_select_form")?.value;

  const equipoObj = listaEquipos.find(e => String(e.id) === String(equipoId));

  if (!clienteId) { showToast("Debes seleccionar un cliente existente.", "error"); return false; }
  if (!equipoId || !equipoObj) { showToast("Debes seleccionar un equipo existente.", "error"); return false; }
  if (String(equipoObj.cliente_id) !== String(clienteId)) {
    showToast("Ese equipo no pertenece al cliente seleccionado.", "error");
    return false;
  }
  return true;
}

function limpiarFormularioOrden() {
  const set = (id, v="") => { const el = document.getElementById(id); if (el) el.value = v; };

  set("nro"); set("buscar_nro");
  set("fecha"); set("telefono"); set("serie");
  set("observaciones"); set("accesorios");
  set("importe"); set("fecha_salida"); set("fecha_regreso");

  const imp = document.getElementById("importe");
  if (imp) imp.dataset.base = "";

  document.getElementById("cliente_select_form") && (document.getElementById("cliente_select_form").value = "");
  document.getElementById("equipo_select_form") && (document.getElementById("equipo_select_form").value = "");

  // horas
  set("hora_ingreso"); set("hora_salida"); set("hora_regreso");
  ingresoHoraMem = ""; salidaHoraMem = ""; regresoHoraMem = "";

  // selects multi + comentarios
  ["falla_select","reparacion_select","repuesto_select"].forEach(idSel => {
    const sel = document.getElementById(idSel);
    if (sel) Array.from(sel.options).forEach(o => (o.selected = false));
  });
  set("falla_comentario"); set("reparacion_comentario"); set("repuesto_comentario");

  setEstado("EN REPARACION");

  retiroFecha = ""; retiroHora = "";
  renderRetiroUI("", "", "");
  actualizarAccionesOrdenUI();
}

function escribirFormulario(o) {
  const imp = document.getElementById("importe");
  if (imp) imp.dataset.base = "";

  document.getElementById("nro") && (document.getElementById("nro").value = o.id || "");
  document.getElementById("fecha") && (document.getElementById("fecha").value = (o.fecha || "").slice(0,10));

  // cliente/equipo
  const selCliente = document.getElementById("cliente_select_form");
  if (selCliente) selCliente.value = (o.cliente_id != null) ? String(o.cliente_id) : "";

  refrescarEquiposDeCliente();

  const selEquipo = document.getElementById("equipo_select_form");
  if (selEquipo) selEquipo.value = (o.equipo_id != null) ? String(o.equipo_id) : "";

  document.getElementById("serie") && (document.getElementById("serie").value = o.serie_texto || o.serie || "");

  document.getElementById("telefono") && (document.getElementById("telefono").value = o.telefono_contacto || "");

  document.getElementById("observaciones") && (document.getElementById("observaciones").value = o.observaciones || "");
  document.getElementById("accesorios") && (document.getElementById("accesorios").value = o.accesorios || "");
  document.getElementById("importe") && (document.getElementById("importe").value = (o.importe ?? ""));

  const est = (o.estado || "EN REPARACION").trim();
  setEstado(est);

  document.getElementById("fecha_salida") && (document.getElementById("fecha_salida").value = (o.fecha_salida || "").slice(0,10));
  document.getElementById("fecha_regreso") && (document.getElementById("fecha_regreso").value = (o.fecha_regreso || "").slice(0,10));

  // horas
  document.getElementById("hora_ingreso") && (document.getElementById("hora_ingreso").value = (o.hora_ingreso || "").slice(0,5));
  document.getElementById("hora_salida") && (document.getElementById("hora_salida").value = (o.hora_salida || "").slice(0,5));
  document.getElementById("hora_regreso") && (document.getElementById("hora_regreso").value = (o.hora_regreso || "").slice(0,5));

  ingresoHoraMem = (o.hora_ingreso || "").slice(0,5);
  salidaHoraMem  = (o.hora_salida  || "").slice(0,5);
  regresoHoraMem = (o.hora_regreso || "").slice(0,5);

  descomponerCampo(o.falla,      "falla_select",      "falla_comentario");
  descomponerCampo(o.reparacion, "reparacion_select", "reparacion_comentario");
  descomponerCampo(o.repuestos,  "repuesto_select",   "repuesto_comentario");

  recalcularImportePorRepuestos();

  retiroFecha = (o.fecha_retiro || "").slice(0,10);
  retiroHora  = (o.hora_retiro  || "").slice(0,5);
  renderRetiroUI(retiroFecha, retiroHora, est);

  actualizarAccionesOrdenUI();
}

// ---------- CLIENTES / EQUIPOS (FORM TABS) ----------
function limpiarFormularioClientes() {
  setValue("cliente_id", "");
  setValue("cliente_nombre", "");
  setValue("cliente_direccion", "");
  setValue("cliente_localidad", "");
  setValue("cliente_provincia", "");
  setValue("cliente_cp", "");
  setValue("cliente_telefono", "");
  setValue("cliente_celular", "");
  setValue("cliente_email", "");
  setValue("cliente_contacto", "");
  setValue("cliente_cuit", "");
  setValue("cliente_giro", "");
  setValue("cliente_observaciones", "");
  setChecked("cliente_garantia", false);
  setChecked("cliente_contrato", false); // si en HTML el id es "cliente_contrato"
   // por si tu HTML usa este id
}

function escribirFormularioCliente(c) {
  document.getElementById("cliente_id").value            = c.id || "";
  document.getElementById("cliente_nombre").value        = c.nombre || "";
  document.getElementById("cliente_direccion").value     = c.direccion || "";
  document.getElementById("cliente_localidad").value     = c.localidad || "";
  document.getElementById("cliente_provincia").value     = c.provincia || "";
  document.getElementById("cliente_cp").value            = c.cp || "";
  document.getElementById("cliente_telefono").value      = c.telefono || "";
  document.getElementById("cliente_celular").value       = c.celular || "";
  document.getElementById("cliente_email").value         = c.email || "";
  document.getElementById("cliente_cuit").value          = c.cuit || "";
  document.getElementById("cliente_contacto").value      = c.contacto || "";
  document.getElementById("cliente_observaciones").value = c.observaciones || "";
  document.getElementById("cliente_giro").value          = c.giro_empresa || "";
  document.getElementById("cliente_garantia").checked    = !!c.cliente_garantia;
  document.getElementById("cliente_contrato").checked    = !!c.cliente_con_contrato;
}

function limpiarFormularioEquipos() {
  setValue("equipo_id", "");
  setValue("equipo_descripcion", "");
  setValue("equipo_serie", "");
  setValue("equipo_tipo", "");
  setValue("equipo_marca", "");
  setValue("equipo_modelo", "");
  resetSelect("equipo_cliente_select"); // ✅ ID correcto
}

function escribirFormularioEquipo(e) {
  document.getElementById("equipo_id").value          = e.id || "";
  document.getElementById("equipo_descripcion").value = e.descripcion || "";
  document.getElementById("equipo_serie").value       = e.serie || "";
  document.getElementById("equipo_tipo").value        = e.tipo || "";
  document.getElementById("equipo_marca").value       = e.marca || "";
  document.getElementById("equipo_modelo").value      = e.modelo || "";
  document.getElementById("equipo_cliente_select").value = e.cliente_id || "";
}

// ---------- RENDER TABLAS ----------
function renderizarTablaClientes() {
  const tbody = document.querySelector("#tablaClientes tbody");
  if (!tbody) return;
  const q = document.getElementById("cliente_filtro")?.value || "";
  tbody.innerHTML = "";

  listaClientes
    .filter(c => {
      const text = [
        c.id, c.nombre, c.telefono, c.celular, c.email, c.cuit, c.contacto,
        c.direccion, c.localidad, c.provincia, c.cp, c.giro_empresa, c.observaciones
      ].join(" | ");
      return matchQuery(text, q);
    })
    .forEach(c => {
      const tr = document.createElement("tr");
      tr.dataset.id = c.id;
      tr.innerHTML = `
        <td>${c.id}</td>
        <td>${c.nombre || ""}</td>
        <td>${c.telefono || c.celular || ""}</td>
        <td>${c.direccion || ""}</td>
        <td>${c.localidad || ""}</td>
      `;
      tbody.appendChild(tr);
    });
}

function renderizarTablaEquipos() {
  const tbody = document.querySelector("#tablaEquipos tbody");
  if (!tbody) return;
  const q = document.getElementById("equipo_filtro")?.value || "";
  tbody.innerHTML = "";

  listaEquipos
    .filter(e => {
      const text = [
        e.id, e.descripcion, e.serie, e.tipo, e.marca, e.modelo, e.clientes, e.cliente_id
      ].join(" | ");
      return matchQuery(text, q);
    })
    .forEach(e => {
      const tr = document.createElement("tr");
      tr.dataset.id = e.id;
      tr.innerHTML = `
        <td>${e.id}</td>
        <td>${e.descripcion || ""}</td>
        <td>${e.serie || ""}</td>
        <td>${e.tipo || ""}</td>
        <td>${e.marca || ""}</td>
        <td>${e.modelo || ""}</td>
        <td>${e.clientes || ""}</td>
      `;
      tbody.appendChild(tr);
    });
}

function renderizarListaOrdenes() {
  const tbody = document.querySelector("#tablaOrdenes tbody");
  if (!tbody) return;

  const q = document.getElementById("filtro_texto")?.value || "";
  tbody.innerHTML = "";

  listaOrdenes
    .filter(o => {
      const text = [
        o.id,
        o.fecha, o.hora_ingreso,
        o.nombre_contacto, o.telefono_contacto,
        o.equipo_texto, o.serie_texto,
        o.estado,
        o.falla, o.reparacion, o.repuestos,
        o.observaciones, o.accesorios,
        o.importe,
        o.fecha_salida, o.hora_salida,
        o.fecha_regreso, o.hora_regreso
      ].join(" | ");
      return matchQuery(text, q);
    })
    .forEach(o => {
      const tr = document.createElement("tr");
      tr.dataset.id = o.id;

      tr.innerHTML = `
        <td>${o.id}</td>
        <td>${(o.fecha || "").slice(0,10)}</td>
        <td>${(o.hora_ingreso || "").slice(0,5)}</td>
        <td>${o.nombre_contacto || ""}</td>
        <td>${o.telefono_contacto || ""}</td>
        <td>${o.equipo_texto || ""}</td>
        <td>${o.serie_texto || ""}</td>
        <td>${o.falla || ""}</td>
        <td>${o.observaciones || ""}</td>
        <td>${o.accesorios || ""}</td>
        <td>${o.reparacion || ""}</td>
        <td>${o.repuestos || ""}</td>
        <td>${o.importe ?? ""}</td>
        <td>${o.estado || ""}</td>
        <td>${(o.fecha_salida || "").slice(0,10)}</td>
        <td>${(o.hora_salida || "").slice(0,5)}</td>
        <td>${(o.fecha_regreso || "").slice(0,10)}</td>
        <td>${(o.hora_regreso || "").slice(0,5)}</td>
      `;

      tbody.appendChild(tr);
    });
}


// ---------- CARGAS ----------
async function cargarClientes() {
  const resp = await fetch("/api/clientes");
  if (!resp.ok) return;
  listaClientes = await resp.json();

  // select del formulario de orden
  const selForm = document.getElementById("cliente_select_form");
  if (selForm) {
    selForm.innerHTML = '<option value="">-- Seleccionar cliente --</option>';
    listaClientes.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.id;
      const tel = c.telefono || c.celular || "";
      opt.textContent = tel ? `${c.nombre} (${tel})` : c.nombre;
      selForm.appendChild(opt);
    });
    selForm.__allOptions = Array.from(selForm.options).map(o => ({ value: o.value, text: o.textContent }));
  }

  // select de equipos (tab equipos)
  const selEq = document.getElementById("equipo_cliente_select");
  if (selEq) {
    selEq.innerHTML = '<option value="">-- Seleccionar cliente --</option>';
    listaClientes.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.id;
      const tel = c.telefono || c.celular || "";
      opt.textContent = tel ? `${c.nombre} (${tel})` : c.nombre;
      selEq.appendChild(opt);
    });
    selEq.__allOptions = Array.from(selEq.options).map(o => ({ value: o.value, text: o.textContent }));
  }

  renderizarTablaClientes();
}

async function cargarEquipos() {
  const resp = await fetch("/api/equipos");
  if (!resp.ok) return;
  listaEquipos = await resp.json();
  renderizarTablaEquipos();
  refrescarEquiposDeCliente();
}

async function cargarListaOrdenes() {
  const resp = await fetch("/api/ordenes");
  if (!resp.ok) {
    showToast("Error al cargar órdenes", "error");
    return;
  }

  listaOrdenes = await resp.json();
  renderizarListaOrdenes();

  // ===== MINIPARCHE: botones duplicar/reabrir =====
  const btnDup = document.getElementById("btnDuplicarDesdeLista");
  const btnRea = document.getElementById("btnReabrirDesdeLista");

  const hayOrdenes = Array.isArray(listaOrdenes) && listaOrdenes.length > 0;

  // Si hay órdenes => habilita botones (para poder activar el modo)
  if (btnDup) btnDup.disabled = !hayOrdenes;
  if (btnRea) btnRea.disabled = !hayOrdenes;

  // Limpia selección y modo al refrescar (evita que quede “modo activo” sin querer)
  modoAccionLista = null;
  ordenSeleccionadaLista = null;

  // Quita highlight de filas seleccionadas
  document.querySelectorAll("#tablaOrdenes tbody tr")
    .forEach(tr => tr.classList.remove("selected"));
}


// ---------- EQUIPOS POR CLIENTE (FORM ORDEN) ----------
function refrescarEquiposDeCliente() {
  const clienteId = document.getElementById("cliente_select_form")?.value || "";
  const selEqForm = document.getElementById("equipo_select_form");
  if (!selEqForm) return;

  const valorActual = selEqForm.value;
  selEqForm.innerHTML = '<option value="">-- Seleccionar equipo --</option>';

  listaEquipos
    .filter(e => !clienteId || String(e.cliente_id) === String(clienteId))
    .forEach(e => {
      const opt = document.createElement("option");
      opt.value = e.id;
      const desc  = e.descripcion || "";
      const serie = e.serie || "";
      const marca = e.marca || "";
      const modelo= e.modelo || "";
      const label = `${desc} ${marca} ${modelo}`.trim();
      opt.textContent = serie ? `${label} (${serie})` : label;
      selEqForm.appendChild(opt);
    });

  selEqForm.__allOptions = Array.from(selEqForm.options).map(o => ({ value: o.value, text: o.textContent }));

  if (valorActual && Array.from(selEqForm.options).some(o => o.value === valorActual)) {
    selEqForm.value = valorActual;
  } else {
    selEqForm.value = "";
    const serie = document.getElementById("serie");
    if (serie) serie.value = "";
  }
}

// ============================
// DOMContentLoaded (INIT)
// ============================
document.addEventListener("DOMContentLoaded", async () => {
  if (window.__initAppDone) return;
  window.__initAppDone = true;
  document.getElementById("btnDuplicarDesdeLista")?.addEventListener("click", () => {
  modoAccionLista = "duplicar";
  showToast("Modo DUPLICAR activo: ahora hacé click en una orden", "ok");
  });

  document.getElementById("btnReabrirDesdeLista")?.addEventListener("click", () => {
    modoAccionLista = "reabrir";
    showToast("Modo REABRIR activo: ahora hacé click en una orden", "ok");
  });
  // ----- BOTONES (definidos -> editor feliz) -----
  const btnLimpiarOrden   = document.getElementById("btnLimpiar");
  const btnBuscar         = document.getElementById("btnBuscar");
  const btnAgregar        = document.getElementById("btnAgregar");
  const btnModificar      = document.getElementById("btnModificar");
  const btnRefrescarLista = document.getElementById("btnRefrescarLista");

  const btnLimpiarCliente = document.getElementById("btn_limpiar_cliente");
  const btnLimpiarEquipo  = document.getElementById("btn_limpiar_equipo");

  // Acciones de estado (asegurate que existan estos IDs en HTML)
  


  // ----- Handlers limpiar cliente/equipo -----
  btnLimpiarCliente?.addEventListener("click", limpiarFormularioClientes);
  btnLimpiarEquipo?.addEventListener("click", limpiarFormularioEquipos);

  // ----- Serie bloqueada -----
  const serie0 = document.getElementById("serie");
  if (serie0) { serie0.readOnly = true; serie0.disabled = true; serie0.classList.add("locked"); }

// ----- Cargas -----
  await Promise.all([
    cargarClientes(),
    cargarEquipos(),
    cargarListaOrdenes(),
    cargarTablasCatalogos(),
    cargarListasAuxiliares()
  ]);

  // ----- Buscadores de selects -----
  makeSelectSearch("falla_search", "falla_select");
  makeSelectSearch("reparacion_search", "reparacion_select");
  makeSelectSearch("repuesto_search", "repuesto_select");
  makeSelectSearch("cliente_form_search", "cliente_select_form");
  makeSelectSearch("equipo_form_search", "equipo_select_form");

  habilitarAppendDesdeSelect("falla_select", "falla_comentario");
  habilitarAppendDesdeSelect("reparacion_select", "reparacion_comentario");

  // equipos por cliente
  refrescarEquiposDeCliente();
  document.getElementById("cliente_select_form")?.addEventListener("change", refrescarEquiposDeCliente);

  // cuando cambia equipo => set serie + cliente
  document.getElementById("equipo_select_form")?.addEventListener("change", () => {
    const id = document.getElementById("equipo_select_form")?.value;
    const eq = listaEquipos.find(e => String(e.id) === String(id));
    const inpSerie = document.getElementById("serie");
    if (!eq) { if (inpSerie) inpSerie.value = ""; return; }
    if (inpSerie) inpSerie.value = eq.serie || "";
    const selCliente = document.getElementById("cliente_select_form");
    if (selCliente) selCliente.value = (eq.cliente_id != null) ? String(eq.cliente_id) : "";
    refrescarEquiposDeCliente();
    document.getElementById("equipo_select_form").value = id;
  });

  // repuestos => importe
  document.getElementById("repuesto_comentario")
    ?.addEventListener("input", debounce(recalcularImportePorRepuestos, 120));

  document.getElementById("btnRepuestoPlus")?.addEventListener("click", () => {
    const sel = document.getElementById("repuesto_select");
    const inp = document.getElementById("repuesto_comentario");
    if (!sel || !inp) return;

    const seleccionados = Array.from(sel.selectedOptions)
      .map(o => (o.value || "").trim())
      .filter(Boolean);

    if (seleccionados.length === 0) return;

    seleccionados.forEach(v => appendToken(inp, v));
    Array.from(sel.options).forEach(o => (o.selected = false));
    recalcularImportePorRepuestos();
  });

  // limpiar orden
  btnLimpiarOrden?.addEventListener("click", () => {
    limpiarFormularioOrden();
    recalcularImportePorRepuestos();
    actualizarAccionesOrdenUI();
  });

  // filtros tablas
  document.getElementById("filtro_texto")?.addEventListener("input", debounce(renderizarListaOrdenes, 120));
  document.getElementById("cliente_filtro")?.addEventListener("input", debounce(renderizarTablaClientes, 120));
  document.getElementById("equipo_filtro")?.addEventListener("input", debounce(renderizarTablaEquipos, 120));
  btnRefrescarLista?.addEventListener("click", cargarListaOrdenes);

  // click orden => cargar en formulario
 document.querySelector("#tablaOrdenes tbody")?.addEventListener("click", async (e) => {
  const fila = e.target.closest("tr");
  if (!fila) return;

  const id = fila.dataset.id;
  const orden = listaOrdenes.find(o => String(o.id) === String(id));
  if (!orden) return;

  // marcar selección visual
  document.querySelectorAll("#tablaOrdenes tbody tr")
    .forEach(tr => tr.classList.remove("selected"));
  fila.classList.add("selected");

  ordenSeleccionadaLista = orden;

  // ===== MODO DUPLICAR =====
  if (modoAccionLista === "duplicar") {
    modoAccionLista = null;

    if (!confirm(`¿Duplicar la orden #${orden.id}?`)) return;

    const r = await fetchJSONSafe(`/api/ordenes/${orden.id}/duplicar`, {
      method: "POST"
    });

    if (r.ok === false) {
      showToast(r.error || "No se pudo duplicar", "error");
      return;
    }

    showToast(`Orden duplicada (#${r.id})`, "ok");
    await cargarListaOrdenes();
    return;
  }

  // ===== MODO REABRIR =====
  if (modoAccionLista === "reabrir") {
    modoAccionLista = null;

    const est = normalizarEstado(orden.estado);
    const puedeReabrir = (est === "TERMINADA" || est === "RETIRADA");

    if (!puedeReabrir) {
      showToast("Solo se puede reabrir una orden TERMINADA o RETIRADA", "error");
      return;
    }

    const motivo = (prompt("Motivo de reapertura (opcional):", "") || "").trim();

    const r = await fetchJSONSafe(`/api/ordenes/${orden.id}/reabrir`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ motivo })
    });

    if (r.ok === false) {
      showToast(r.error || "No se pudo reabrir", "error");
      return;
    }

    showToast(`Orden #${orden.id} reabierta`, "ok");
    await cargarListaOrdenes();
    return;
  }

  // ===== COMPORTAMIENTO NORMAL =====
  const imp = document.getElementById("importe");
  if (imp) imp.dataset.base = "";

  escribirFormulario(orden);
  document.getElementById("buscar_nro") &&
    (document.getElementById("buscar_nro").value = orden.id);

  irATabFormulario();
  actualizarAccionesOrdenUI();
});


  // click cliente/equipo => editar
  document.querySelector("#tablaClientes tbody")?.addEventListener("click", (e) => {
    const fila = e.target.closest("tr");
    if (!fila) return;
    const id = parseInt(fila.dataset.id);
    const c = listaClientes.find(x => x.id === id);
    if (c) escribirFormularioCliente(c);
  });

  document.querySelector("#tablaEquipos tbody")?.addEventListener("click", (e) => {
    const fila = e.target.closest("tr");
    if (!fila) return;
    const id = parseInt(fila.dataset.id);
    const eq = listaEquipos.find(x => x.id === id);
    if (eq) escribirFormularioEquipo(eq);
  });

  // buscar por nro
  btnBuscar?.addEventListener("click", async () => {
    const nro = document.getElementById("buscar_nro")?.value;
    if (!nro) { showToast("Ingresa un número de orden", "error"); return; }

    const resp = await fetch(`/api/ordenes/${nro}`);
    if (!resp.ok) { showToast("No se encontró la orden", "error"); return; }

    const data = await resp.json();
    const imp = document.getElementById("importe");
    if (imp) imp.dataset.base = "";
    escribirFormulario(data);
    irATabFormulario();
    actualizarAccionesOrdenUI();
  });

  // agregar orden
  btnAgregar?.addEventListener("click", async () => {
    setIngresoAhoraSiVacio();
    if (!validarClienteYEquipo()) return;

    const datos = leerFormulario();
    try {
      const r = await fetchJSONSafe("/api/ordenes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(datos)
      });
      showToast("Orden creada", "ok");

      if (r.id) {
        document.getElementById("nro").value = r.id;
        document.getElementById("buscar_nro").value = r.id;
      }

      await cargarListaOrdenes();
      actualizarAccionesOrdenUI();
    } catch (err) {
      showToast(err.message || "Error al crear orden", "error");
    }
  });



  // modificar orden
  btnModificar?.addEventListener("click", async () => {
    const nro = document.getElementById("nro")?.value;
    if (!nro) { showToast("Primero busca o crea una orden", "error"); return; }
    if (!validarClienteYEquipo()) return;

    try {
      const datos = leerFormulario();
      await fetchJSONSafe(`/api/ordenes/${nro}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(datos)
      });
      showToast("Orden modificada", "ok");
      await cargarListaOrdenes();
      actualizarAccionesOrdenUI();
    } catch (err) {
      showToast(err.message || "Error al modificar orden", "error");
    }
  });

  // guardar repuesto catálogo
  document.getElementById("btnCatRepuestoGuardar")?.addEventListener("click", async () => {
    const nombre  = document.getElementById("cat_rep_nombre")?.value.trim();
    const detalle = document.getElementById("cat_rep_detalle")?.value.trim();
    const costo   = document.getElementById("cat_rep_costo")?.value;

    if (!nombre) { showToast("Ingresá un nombre de repuesto", "error"); return; }

    try {
      const r = await fetchJSONSafe("/api/repuestos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre, detalle, costo })
      });

      if (!r.ok) { showToast(r.error || "Error al guardar repuesto", "error"); return; }

      document.getElementById("cat_rep_nombre").value  = "";
      document.getElementById("cat_rep_detalle").value = "";
      document.getElementById("cat_rep_costo").value   = "";

      showToast("Repuesto guardado", "ok");
      await cargarListasAuxiliares();
      await cargarTablasCatalogos();
    } catch (err) {
      showToast(err.message || "Error al guardar repuesto", "error");
    }
  });
  document.getElementById("btnRegistrarSalida")?.addEventListener("click", async () => {
  if (!ordenCargada()) return;

  setSalidaAhoraSiVacia();
  setEstado("EN REPARACION"); // o lo que definas

  const datos = leerFormulario();

  const nro = document.getElementById("nro").value;
  const r = await fetchJSONSafe(`/api/ordenes/${nro}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos)
  });

  if (r.ok === false) {
    showToast(r.error, "error");
    return;
  }

  showToast("Salida registrada", "ok");
  await cargarListaOrdenes();
});

document.getElementById("btnMarcarTerminada")?.addEventListener("click", async () => {
  if (!ordenCargada()) return;

  setEstado("TERMINADA");

  const datos = leerFormulario();
  const nro = document.getElementById("nro").value;

  const r = await fetchJSONSafe(`/api/ordenes/${nro}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos)
  });

  if (r.ok === false) {
    showToast(r.error, "error");
    return;
  }

  showToast("Orden terminada", "ok");
  await cargarListaOrdenes();
  actualizarAccionesOrdenUI();
});
document.getElementById("btnMarcarRetirada")?.addEventListener("click", async () => {
  if (!ordenCargada()) return;

  setRetiroAhoraMem();
  setEstado("RETIRADA");

  const datos = leerFormulario();
  const nro = document.getElementById("nro").value;

  const r = await fetchJSONSafe(`/api/ordenes/${nro}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos)
  });

  if (r.ok === false) {
    showToast(r.error, "error");
    return;
  }

  showToast("Orden retirada", "ok");
  await cargarListaOrdenes();
  actualizarAccionesOrdenUI();
});

// =========================
// Guardar FALLA (catálogo)
// =========================
document.getElementById("btnCatFallaGuardar")?.addEventListener("click", async () => {
  const descripcion = (document.getElementById("cat_falla_desc")?.value || "").trim();
  if (!descripcion) return showToast("Ingresá una descripción de falla", "error");

  try {
    const r = await fetchJSONSafe("/api/fallas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ descripcion })
    });

    if (!r.ok) return showToast(r.error || "Error al guardar falla", "error");

    document.getElementById("cat_falla_desc").value = "";
    showToast("Falla guardada", "ok");
    await cargarListasAuxiliares();
    await cargarTablasCatalogos();
  } catch (err) {
    showToast(err.message || "Error al guardar falla", "error");
  }
});

// ==============================
// Guardar REPARACIÓN (catálogo)
// ==============================
document.getElementById("btnCatReparacionGuardar")?.addEventListener("click", async () => {
  const descripcion = (document.getElementById("cat_rep_desc")?.value || "").trim();
  if (!descripcion) return showToast("Ingresá una descripción de reparación", "error");

  try {
    const r = await fetchJSONSafe("/api/reparaciones", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ descripcion })
    });

    if (!r.ok) return showToast(r.error || "Error al guardar reparación", "error");

    document.getElementById("cat_rep_desc").value = "";
    showToast("Reparación guardada", "ok");
    await cargarListasAuxiliares();
    await cargarTablasCatalogos();
  } catch (err) {
    showToast(err.message || "Error al guardar reparación", "error");
  }
});

const tel = document.getElementById("telefono");
if (tel) {
  tel.readOnly = true;
  tel.disabled = true;     // opcional si querés bloquearlo del todo
  tel.classList.add("locked");
}


});
