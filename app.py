import os
from datetime import datetime, date, time, timedelta

import mysql.connector
from mysql.connector import Error
from mysql.connector.errors import IntegrityError

from flask import Flask, render_template, request, jsonify, send_from_directory

from orden_docx import generar_docx_orden
import re
import unicodedata

ESTADOS_EN_PROCESO = {
    "EN REPARACION", "EN SOS", "EN WERTECH", "EN EKON",
    "EN AIR", "EN SERVIPRINT", "EN NICO GORI"
}
ESTADO_TERMINADA = "TERMINADA"
ESTADO_RETIRADA  = "RETIRADA"

def to_upper(s):
    return str(s or "").strip().upper()

def to_capitalize(s):
    """
    Normaliza texto:
    - strip
    - colapsa espacios
    - capitalize por oración simple (primera letra mayus, resto igual)
    Si querés TODO uppercase para textos también, te lo cambio.
    """
    if s is None:
        return None
    t = str(s).strip()
    t = re.sub(r"\s+", " ", t)
    if not t:
        return None
    return t[:1].upper() + t[1:]

def parse_fecha(v):
    # espera YYYY-MM-DD
    if not v:
        return None
    v = str(v).strip()
    if not v:
        return None
    return v[:10]

def parse_hora(v):
    # espera HH:MM
    if not v:
        return None
    v = str(v).strip()
    if not v:
        return None
    return v[:5]

def now_fecha_hora():
    # usá tu función existente si ya la tenés
    from datetime import datetime
    d = datetime.now()
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M")

def _clean_text(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # sin tildes
    s = re.sub(r"\s+", " ", s)
    return s

def clean_digits(s: str) -> str:
    return re.sub(r"\D", "", _clean_text(s))

def clean_email(s: str) -> str:
    return _clean_text(s).lower()

def clean_serie(s: str) -> str:
    # Serie/SN: mayúsculas y sin espacios
    return re.sub(r"\s+", "", to_upper(s))

# ========= APP =========
app = Flask(__name__, template_folder='templates', static_folder='static')

# ========= CONFIGURACIÓN DB =========
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',         # <-- CAMBIAR
    'password': 'root',     # <-- CAMBIAR
    'database': 'setup_db',
    'port': 3306,
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

DOCX_DIR = os.path.join(os.path.dirname(__file__), "ordenes_docx")
os.makedirs(DOCX_DIR, exist_ok=True)

def generar_word_de_orden(conn, orden_id):
    """
    Lee la orden desde DB y genera el Word imprimible.
    """
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT
            o.*,
            c.nombre AS nombre_contacto,
            c.telefono AS telefono_contacto,
            e.descripcion AS equipo_texto,
            e.serie       AS serie_texto
        FROM ordenes o
        LEFT JOIN clientes c ON o.cliente_id = c.id
        LEFT JOIN equipos  e ON o.equipo_id   = e.id
        WHERE o.id=%s
        """,
        (orden_id,),
    )
    orden = cur.fetchone()
    cur.close()

    if orden:
        generar_docx_orden(orden, DOCX_DIR, filename=f"Orden_{orden_id}.docx")

def _usuario_actual():
    return request.headers.get("X-User", "sistema")

def _insert_hist(conn, orden_id, accion, nota=None):
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO orden_historial (orden_id, usuario, accion, nota)
            VALUES (%s, %s, %s, %s)
            """,
            (orden_id, _usuario_actual(), accion, nota),
        )
        cur.close()
    except Exception:
        pass

def normalize_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        # fechas / datetimes
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        # horas puras
        elif isinstance(v, time):
            out[k] = v.strftime("%H:%M:%S")
        # campos TIME de MySQL que vienen como timedelta
        elif isinstance(v, timedelta):
            total = int(v.total_seconds())
            h = total // 3600
            m = (total % 3600) // 60
            s = total % 60
            out[k] = f"{h:02d}:{m:02d}:{s:02d}"
        else:
            out[k] = v
    return out


# ========= PÁGINAS PRINCIPALES =========
@app.route("/")
def index():
    return render_template("ordenes.html")


@app.route("/ordenes")
def ordenes():
    return render_template("ordenes.html")


# ========= API CATÁLOGOS SENCILLOS (fallas / reparaciones / repuestos / accesorios) =========
@app.route("/api/fallas", methods=["GET"])
def api_fallas():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, descripcion FROM fallas ORDER BY descripcion")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)


@app.route("/api/reparaciones", methods=["GET"])
def api_reparaciones():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, descripcion FROM reparaciones ORDER BY descripcion")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)


@app.route("/api/repuestos", methods=["GET"])
def api_repuestos():
    """Lista de repuestos (incluye costo para que el front pueda sumar)."""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT id, nombre, descripcion, costo
        FROM repuestos
        ORDER BY nombre
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    # normalizo por si algún día costo es DECIMAL, etc.
    return jsonify([normalize_row(r) for r in rows])


@app.route("/api/accesorios", methods=["GET"])
def api_accesorios():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, nombre FROM accesorios ORDER BY nombre")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)

@app.route("/api/clientes", methods=["GET"])
def api_clientes():
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # SELECT * para no romper si agregás/quitás columnas
    cur.execute("SELECT * FROM clientes ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    rows = [normalize_row(r) for r in rows]
    return jsonify(rows)

def _clientes_tiene_col(conn, colname: str) -> bool:
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT COUNT(*) AS c
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'clientes'
          AND COLUMN_NAME = %s
    """, (colname,))
    ok = (cur.fetchone() or {}).get("c", 0) > 0
    cur.close()
    return ok
@app.route("/api/clientes", methods=["POST"])
def api_clientes_crear():
    data = request.json or {}

    nombre   = to_capitalize(data.get("nombre"))

    telefono = clean_digits(data.get("telefono")) or None

    if not nombre:
        return jsonify({"ok": False, "error": "El nombre del cliente es obligatorio"}), 400

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT id
            FROM clientes
            WHERE nombre=%s
              AND (telefono=%s OR (telefono IS NULL AND %s IS NULL))
            """,
            (nombre, telefono, telefono),
        )
        existente = cur.fetchone()
        if existente:
            cur.close(); conn.close()
            return jsonify({
                "ok": False,
                "error": "Ya existe un cliente con ese nombre y teléfono",
                "id": existente["id"],
            }), 409

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO clientes
              (nombre, direccion, localidad, provincia, cp,
               telefono, email, cuit, contacto,
               observaciones, giro_empresa,
               cliente_garantia, cliente_con_contrato)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                nombre,
                to_capitalize(data.get("direccion")) or None,
                to_capitalize(data.get("localidad")) or None,
                to_capitalize(data.get("provincia")) or None,
                _clean_text(data.get("cp")) or None,
                telefono,
                clean_email(data.get("email")),
                clean_digits(data.get("cuit")) or None,
                to_capitalize(data.get("contacto")) or None,
                to_capitalize(data.get("observaciones")) or None,
                to_capitalize(data.get("giro_empresa")) or None,
                data.get("cliente_garantia") or 0,
                data.get("cliente_con_contrato") or 0,
            ),
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close(); conn.close()
        return jsonify({"ok": True, "id": new_id})

    except Error as e:
        print("Error api_clientes_crear:", e)

        if getattr(e, "errno", None) == 1062:
            return jsonify({"ok": False, "error": "Cliente duplicado (restricción única)"}), 409

        conn.rollback()
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "Error al guardar cliente"}), 500
@app.route("/api/clientes/<int:cliente_id>", methods=["PUT"])
def api_clientes_actualizar(cliente_id):
    data = request.json or {}

    nombre   = to_capitalize(data.get("nombre"))

    telefono = clean_digits(data.get("telefono")) or None

    if not nombre:
        return jsonify({"ok": False, "error": "El nombre del cliente es obligatorio"}), 400

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT id
            FROM clientes
            WHERE nombre=%s
              AND (telefono=%s OR (telefono IS NULL AND %s IS NULL))
              AND id <> %s
            """,
            (nombre, telefono, telefono, cliente_id),
        )
        duplicado = cur.fetchone()
        if duplicado:
            cur.close(); conn.close()
            return jsonify({
                "ok": False,
                "error": "Ya existe otro cliente con ese nombre y teléfono",
                "id": duplicado["id"],
            }), 409

        cur = conn.cursor()
        cur.execute(
            """
            UPDATE clientes
            SET nombre=%s,
                direccion=%s,
                localidad=%s,
                provincia=%s,
                cp=%s,
                telefono=%s,
                email=%s,
                cuit=%s,
                contacto=%s,
                observaciones=%s,
                giro_empresa=%s,
                cliente_garantia=%s,
                cliente_con_contrato=%s
            WHERE id=%s
            """,
            (
                nombre,
                to_capitalize(data.get("direccion")) or None,
                to_capitalize(data.get("localidad")) or None,
                to_capitalize(data.get("provincia")) or None,
                _clean_text(data.get("cp")) or None,
                telefono,
                clean_email(data.get("email")),
                clean_digits(data.get("cuit")) or None,
                to_capitalize(data.get("contacto")) or None,
                to_capitalize(data.get("observaciones")) or None,
                to_capitalize(data.get("giro_empresa")) or None,
                data.get("cliente_garantia") or 0,
                data.get("cliente_con_contrato") or 0,
                cliente_id,
            ),
        )
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"ok": True})

    except Error as e:
        print("Error api_clientes_actualizar:", e)
        conn.rollback()
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "Error al actualizar cliente"}), 500


# ========= API EQUIPOS (siempre ligados a un cliente) =========
@app.route("/api/equipos", methods=["GET"])
def api_equipos():
    """
    Devuelve los equipos junto con:
    - cliente_id (cliente principal propietario)
    - clientes (string con todos los clientes asociados, separador ", ")
    """
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT
            e.*,
            MIN(CASE WHEN ec.activo = 1 THEN ec.cliente_id END) AS cliente_id,
            GROUP_CONCAT(c.nombre SEPARATOR ', ') AS clientes
        FROM equipos e
        LEFT JOIN equipo_cliente ec
               ON e.id = ec.equipo_id AND ec.activo = 1
        LEFT JOIN clientes c
               ON ec.cliente_id = c.id
        GROUP BY e.id
        ORDER BY e.id DESC
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([normalize_row(r) for r in rows])


@app.route("/api/equipos", methods=["POST"])
def crear_equipo_api():
    data = request.json or {}

    descripcion = to_capitalize(data.get("descripcion"))
    serie       = clean_serie(data.get("serie"))
    cliente_id  = data.get("cliente_id")

    if not descripcion and not serie:
        return jsonify({"ok": False, "error": "Debe indicar al menos Descripción o Serie"}), 400
    if not cliente_id:
        return jsonify({"ok": False, "error": "Debe seleccionar un cliente para el equipo"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO equipos (descripcion, serie, tipo, marca, modelo)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (
                descripcion or None,
                serie or None,
                to_capitalize(data.get("tipo")) or None,
                to_capitalize(data.get("marca")) or None,
                to_capitalize(data.get("modelo")) or None,
            ),
        )
        conn.commit()
        equipo_id = cur.lastrowid
        cur.close()

        # vincular con cliente
        vincular_equipo_cliente(conn, equipo_id, int(cliente_id), "propietario")

        conn.close()
        return jsonify({"ok": True, "id": equipo_id})

    except Error as e:
        print("Error crear_equipo:", e)

        # 1062 = Duplicate entry (ej: serie única)
        if getattr(e, "errno", None) == 1062:
            return jsonify({
                "ok": False,
                "error": "Ya existe un equipo con esa SERIE. Elegí otra o buscá el equipo existente."
            }), 409

        # 1452 = FK fail
        if getattr(e, "errno", None) == 1452:
            return jsonify({
                "ok": False,
                "error": "Cliente inválido (no existe). Seleccioná un cliente válido."
            }), 409

        return jsonify({"ok": False, "error": "Error al guardar equipo"}), 500
@app.route("/api/equipos/<int:equipo_id>", methods=["PUT"])
def modificar_equipo_api(equipo_id):
    data = request.json or {}

    descripcion = to_capitalize(data.get("descripcion"))
    serie       = clean_serie(data.get("serie"))
    cliente_id  = data.get("cliente_id")

    if not descripcion and not serie:
        return jsonify({"ok": False, "error": "Debe indicar al menos Descripción o Serie"}), 400
    if not cliente_id:
        return jsonify({"ok": False, "error": "Debe seleccionar un cliente para el equipo"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE equipos
            SET descripcion=%s, serie=%s, tipo=%s, marca=%s, modelo=%s
            WHERE id=%s
            """,
            (
                descripcion or None,
                serie or None,
                to_capitalize(data.get("tipo")) or None,
                to_capitalize(data.get("marca")) or None,
                to_capitalize(data.get("modelo")) or None,
                equipo_id,
            ),
        )
        conn.commit()
        cur.close()

        vincular_equipo_cliente(conn, equipo_id, int(cliente_id), "propietario")

        conn.close()
        return jsonify({"ok": True})

    except Error as e:
        print("Error modificar_equipo:", e)

        if getattr(e, "errno", None) == 1062:
            return jsonify({
                "ok": False,
                "error": "No se pudo guardar: la SERIE ya existe en otro equipo."
            }), 409

        return jsonify({"ok": False, "error": "Error al modificar equipo"}), 500

def vincular_equipo_cliente(conn, equipo_id, cliente_id, rol="propietario"):
    """
    Mantiene la tabla equipo_cliente con tu esquema actual:
      (equipo_id, cliente_id, rol, fecha_asignacion, activo)

    - Desactiva vínculos activos del equipo
    - Reactiva o inserta el vínculo con el cliente
    """
    cur = conn.cursor()

    # 1) desactivar todas las relaciones activas de ese equipo
    cur.execute(
        "UPDATE equipo_cliente SET activo=0 WHERE equipo_id=%s AND activo=1",
        (equipo_id,),
    )

    # 2) ver si ya existe vínculo equipo-cliente
    cur.execute(
        """
        SELECT id
        FROM equipo_cliente
        WHERE equipo_id=%s AND cliente_id=%s
        """,
        (equipo_id, cliente_id),
    )
    row = cur.fetchone()

    if row:
        # reactivar y actualizar rol
        cur.execute(
            """
            UPDATE equipo_cliente
            SET activo=1, rol=%s
            WHERE id=%s
            """,
            (rol, row[0]),
        )
    else:
        # crear nuevo vínculo
        cur.execute(
            """
            INSERT INTO equipo_cliente (equipo_id, cliente_id, rol, activo)
            VALUES (%s, %s, %s, 1)
            """,
            (equipo_id, cliente_id, rol),
        )

    conn.commit()
    cur.close()

# ========= API ÓRDENES =========

def buscar_o_crear_cliente(conn, nombre, telefono):
    """
    Busca un cliente por nombre y teléfono. Si no existe, lo crea.
    Devuelve el id del cliente.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id FROM clientes
        WHERE nombre=%s AND (telefono=%s OR (telefono IS NULL AND %s IS NULL))
        """,
        (nombre, telefono, telefono),
    )
    row = cur.fetchone()
    if row:
        cur.close()
        return row[0]

    cur.execute(
        "INSERT INTO clientes (nombre, telefono) VALUES (%s, %s)",
        (nombre, telefono),
    )
    conn.commit()
    new_id = cur.lastrowid
    cur.close()
    return new_id
@app.route("/api/ordenes", methods=["GET"])
def api_ordenes():
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
            o.*,
            c.nombre   AS nombre_contacto,
            COALESCE(NULLIF(TRIM(c.telefono),''), NULLIF(TRIM(c.celular),''), '') AS telefono_contacto,
            e.serie    AS serie_texto,
            CONCAT_WS(' ', e.descripcion, e.marca, e.modelo) AS equipo_texto
        FROM ordenes o
        LEFT JOIN clientes c ON c.id = o.cliente_id
        LEFT JOIN equipos   e ON e.id = o.equipo_id
        ORDER BY o.id DESC
    """)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    rows = [normalize_row(r) for r in rows]
    return jsonify(rows)



def normalizar_orden(data: dict) -> dict:
    data["estado"] = to_upper(data.get("estado"))

    data["telefono_contacto"] = re.sub(
        r"\D", "", data.get("telefono_contacto") or ""
    )

    for campo in (
        "observaciones",
        "accesorios",
        "falla",
        "reparacion",
        "repuestos",
    ):
        data[campo] = to_capitalize(data.get(campo))

    return data


@app.route("/api/fallas", methods=["POST"])
def api_crear_falla():
    data = request.get_json()
    desc = to_capitalize(data.get("descripcion"))
    if not desc:
        return jsonify({"ok": False, "error": "La descripción es obligatoria"}), 400

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO fallas (descripcion) VALUES (%s)", (desc,))
        conn.commit()
        new_id = cur.lastrowid
    except IntegrityError:
        # clave única duplicada
        return (
            jsonify({"ok": False, "error": "Ya existe una falla con esa descripción"}),
            409,
        )
    finally:
        cur.close()
        conn.close()

    return jsonify({"ok": True, "id": new_id})


# =========================================================
#                CATÁLOGOS: REPARACIONES
# =========================================================

@app.route("/api/reparaciones", methods=["POST"])
def api_crear_reparacion():
    data = request.get_json()
    desc = to_capitalize(data.get("descripcion"))
    if not desc:
        return jsonify({"ok": False, "error": "La descripción es obligatoria"}), 400

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO reparaciones (descripcion) VALUES (%s)", (desc,))
        conn.commit()
        new_id = cur.lastrowid
    except IntegrityError:
        return (
            jsonify({"ok": False, "error": "Ya existe una reparación con esa descripción"}),
            409,
        )
    finally:
        cur.close()
        conn.close()
    return jsonify({"ok": True, "id": new_id})



# =========================================================
#                     REPUESTOS
# =========================================================


@app.route("/api/repuestos", methods=["POST"])
def api_crear_repuesto():
    data = request.json or {}
    nombre = to_capitalize(data.get("nombre"))
    descripcion = to_capitalize(data.get("detalle") or data.get("descripcion"))
    costo = data.get("costo", 0)

    if not nombre:
        return jsonify({"ok": False, "error": "Falta nombre"}), 400

    try:
        costo = float(costo) if costo not in (None, "") else 0.0
    except:
        costo = 0.0

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO repuestos (nombre, descripcion, costo) VALUES (%s,%s,%s)",
        (nombre, descripcion, costo)
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})



@app.route("/api/fallas/<int:falla_id>", methods=["DELETE"])
def api_borrar_falla(falla_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM fallas WHERE id=%s", (falla_id,))
        conn.commit()

        if cur.rowcount == 0:
            return jsonify({"ok": False, "error": "Falla no encontrada"}), 404

        return jsonify({"ok": True})
    except Error as e:
        print("Error api_borrar_falla:", e)
        conn.rollback()
        return jsonify({"ok": False, "error": "Error al borrar falla"}), 500
    finally:
        cur.close()
        conn.close()


# =========================
# DELETE: REPARACIONES
# =========================
@app.route("/api/reparaciones/<int:reparacion_id>", methods=["DELETE"])
def api_borrar_reparacion(reparacion_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM reparaciones WHERE id=%s", (reparacion_id,))
        conn.commit()

        if cur.rowcount == 0:
            return jsonify({"ok": False, "error": "Reparación no encontrada"}), 404

        return jsonify({"ok": True})
    except Error as e:
        print("Error api_borrar_reparacion:", e)
        conn.rollback()
        return jsonify({"ok": False, "error": "Error al borrar reparación"}), 500
    finally:
        cur.close()
        conn.close()


# =========================
# DELETE: REPUESTOS
# =========================
@app.route("/api/repuestos/<int:repuesto_id>", methods=["DELETE"])
def api_borrar_repuesto(repuesto_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM repuestos WHERE id=%s", (repuesto_id,))
        conn.commit()

        if cur.rowcount == 0:
            return jsonify({"ok": False, "error": "Repuesto no encontrado"}), 404

        return jsonify({"ok": True})
    except Error as e:
        print("Error api_borrar_repuesto:", e)
        conn.rollback()
        return jsonify({"ok": False, "error": "Error al borrar repuesto"}), 500
    finally:
        cur.close()
        conn.close()

@app.route("/api/ordenes/<int:orden_id>/docx", methods=["GET"])
def descargar_docx_orden(orden_id):
    filename = f"Orden_{orden_id}.docx"
    return send_from_directory(DOCX_DIR, filename, as_attachment=True)
@app.route("/api/ordenes/<int:orden_id>/reabrir", methods=["POST"])
def reabrir_orden(orden_id):
    motivo = (request.json or {}).get("motivo", "").strip()

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT estado FROM ordenes WHERE id=%s", (orden_id,))
    o = cur.fetchone()
    if not o:
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "Orden no encontrada"}), 404

    if o["estado"] not in ("TERMINADA", "RETIRADA"):
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "Estado no permite reapertura"}), 400

    cur2 = conn.cursor()
    cur2.execute(
        "UPDATE ordenes SET estado=%s WHERE id=%s",
        ("EN REPARACION", orden_id)
    )
    conn.commit()

    _insert_hist(conn, orden_id, "REOPEN", motivo or "Reapertura")
    conn.commit()

    cur2.close(); cur.close(); conn.close()
    return jsonify({"ok": True})
@app.route("/api/ordenes/<int:orden_id>/suspender", methods=["POST"])
def suspender_orden(orden_id):
    motivo = (request.json or {}).get("motivo", "").strip()
    if not motivo:
        return jsonify({"ok": False, "error": "Motivo requerido"}), 400

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT estado FROM ordenes WHERE id=%s", (orden_id,))
    o = cur.fetchone()
    if not o:
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "Orden no encontrada"}), 404

    if o["estado"] == "RETIRADA":
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "No se puede suspender una orden retirada"}), 400

    cur2 = conn.cursor()
    cur2.execute(
        "UPDATE ordenes SET estado=%s WHERE id=%s",
        ("SUSPENDIDA", orden_id)
    )
    conn.commit()

    _insert_hist(conn, orden_id, "SUSPEND", motivo)
    conn.commit()

    cur2.close(); cur.close(); conn.close()
    return jsonify({"ok": True})


@app.route("/api/ordenes/<int:orden_id>/duplicar", methods=["POST"])
def duplicar_orden(orden_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM ordenes WHERE id=%s", (orden_id,))
    o = cur.fetchone()
    if not o:
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "Orden no encontrada"}), 404

    copia = dict(o)
    copia.pop("id", None)

    copia["estado"] = "EN REPARACION"
    copia["fecha_salida"] = None
    copia["hora_salida"] = None
    copia["fecha_regreso"] = None
    copia["hora_regreso"] = None

    cols = list(copia.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    colnames = ", ".join(cols)

    cur2 = conn.cursor()
    cur2.execute(
        f"INSERT INTO ordenes ({colnames}) VALUES ({placeholders})",
        [copia[c] for c in cols]
    )
    new_id = cur2.lastrowid
    conn.commit()

    _insert_hist(conn, new_id, "DUPLICATE", f"Duplicada desde orden #{orden_id}")
    conn.commit()

    cur2.close(); cur.close(); conn.close()
    return jsonify({"ok": True, "id": new_id})

# ========= API ÓRDENES =========
# =========================
# ORDENES: helpers
# =========================
import re
from flask import request, jsonify

ESTADOS_EN_PROCESO = {
    "EN REPARACION", "EN SOS", "EN WERTECH", "EN EKON",
    "EN AIR", "EN SERVIPRINT", "EN NICO GORI"
}
ESTADO_TERMINADA = "TERMINADA"
ESTADO_RETIRADA  = "RETIRADA"

def to_upper(s):
    return str(s or "").strip().upper()

def to_capitalize(s):
    """
    Normaliza texto:
    - strip
    - colapsa espacios
    - capitalize por oración simple (primera letra mayus, resto igual)
    Si querés TODO uppercase para textos también, te lo cambio.
    """
    if s is None:
        return None
    t = str(s).strip()
    t = re.sub(r"\s+", " ", t)
    if not t:
        return None
    return t[:1].upper() + t[1:]

def parse_fecha(v):
    # espera YYYY-MM-DD
    if not v:
        return None
    v = str(v).strip()
    if not v:
        return None
    return v[:10]

def parse_hora(v):
    # espera HH:MM
    if not v:
        return None
    v = str(v).strip()
    if not v:
        return None
    return v[:5]

def now_fecha_hora():
    # usá tu función existente si ya la tenés
    from datetime import datetime
    d = datetime.now()
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M")


# =========================
# POST /api/ordenes
# =========================
@app.route("/api/ordenes", methods=["POST"])
def crear_orden():
    data = request.get_json(silent=True) or {}

    cliente_id = data.get("cliente_id")
    equipo_id  = data.get("equipo_id")
    if not cliente_id or not equipo_id:
        return jsonify({"ok": False, "error": "Cliente y equipo obligatorios"}), 400

    # ingreso (si no viene, lo seteo)
    fecha_ingreso = parse_fecha(data.get("fecha")) or now_fecha_hora()[0]
    hora_ingreso  = parse_hora(data.get("hora_ingreso")) or now_fecha_hora()[1]

    estado = to_upper(data.get("estado") or "EN REPARACION")

    # textos normalizados
    falla         = to_capitalize(data.get("falla"))
    observaciones = to_capitalize(data.get("observaciones"))
    accesorios    = to_capitalize(data.get("accesorios"))
    reparacion    = to_capitalize(data.get("reparacion"))
    repuestos     = to_capitalize(data.get("repuestos"))

    # importe
    try:
        importe = float(str(data.get("importe") or 0).replace(",", "."))
    except:
        importe = 0.0

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO ordenes (
                fecha, hora_ingreso,
                cliente_id, equipo_id,
                falla, observaciones, accesorios,
                reparacion, repuestos,
                importe,
                estado,
                fecha_salida, hora_salida,
                fecha_regreso, hora_regreso,
                fecha_retiro, hora_retiro
            )
            VALUES (%s,%s,%s,%s,
                    %s,%s,%s,
                    %s,%s,
                    %s,
                    %s,
                    NULL,NULL,
                    NULL,NULL,
                    NULL,NULL)
            """,
            (
                fecha_ingreso,
                hora_ingreso,
                cliente_id,
                equipo_id,
                falla,
                observaciones,
                accesorios,
                reparacion,
                repuestos,
                importe,
                estado,
            )
        )

        conn.commit()
        orden_id = cur.lastrowid

        # si tenés word:
        try:
            generar_word_de_orden(conn, orden_id)
        except Exception as e:
            print("WARN word:", e)

        cur.close()
        conn.close()
        return jsonify({"ok": True, "id": orden_id})

    except Exception as e:
        print("Error crear_orden:", e)
        return jsonify({"ok": False, "error": "Error al crear orden"}), 500


# =========================
# PUT /api/ordenes/<id>
# =========================
@app.route("/api/ordenes/<int:orden_id>", methods=["PUT"])
def actualizar_orden(orden_id):
    data = request.get_json(silent=True) or {}

    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # Traer estado actual
        cur.execute("""
            SELECT id, cliente_id, equipo_id, estado,
                   fecha_salida, hora_salida,
                   fecha_regreso, hora_regreso,
                   fecha_retiro, hora_retiro
            FROM ordenes
            WHERE id=%s
        """, (orden_id,))
        actual = cur.fetchone()

        if not actual:
            cur.close(); conn.close()
            return jsonify({"ok": False, "error": "Orden no encontrada"}), 404

        # mantener si no mandan
        cliente_id = data.get("cliente_id") or actual["cliente_id"]
        equipo_id  = data.get("equipo_id")  or actual["equipo_id"]

        # bloquear cambio de equipo SOLO si el front lo manda distinto
        if data.get("equipo_id") and str(data.get("equipo_id")) != str(actual["equipo_id"]):
            cur.close(); conn.close()
            return jsonify({"ok": False, "error": "No se puede cambiar el equipo de la orden"}), 409

        estado_actual = to_upper(actual.get("estado") or "EN REPARACION")
        estado_nuevo  = to_upper(data.get("estado") or estado_actual)

        # normalizar textos
        falla         = to_capitalize(data.get("falla"))
        observaciones = to_capitalize(data.get("observaciones"))
        accesorios    = to_capitalize(data.get("accesorios"))
        reparacion    = to_capitalize(data.get("reparacion"))
        repuestos     = to_capitalize(data.get("repuestos"))

        # importe
        try:
            importe = float(str(data.get("importe") or 0).replace(",", "."))
        except:
            importe = 0.0

        # tomar timestamps que vengan, o conservar DB
        fecha_salida  = parse_fecha(data.get("fecha_salida"))  or actual["fecha_salida"]
        hora_salida   = parse_hora(data.get("hora_salida"))    or actual["hora_salida"]
        fecha_regreso = parse_fecha(data.get("fecha_regreso")) or actual["fecha_regreso"]
        hora_regreso  = parse_hora(data.get("hora_regreso"))   or actual["hora_regreso"]
        fecha_retiro  = parse_fecha(data.get("fecha_retiro"))  or actual["fecha_retiro"]
        hora_retiro   = parse_hora(data.get("hora_retiro"))    or actual["hora_retiro"]

        # ---------- reglas de transiciones ----------

        # EN PROCESO -> TERMINADA (NO obliga salida, pero si no existe la setea)
        if estado_actual in ESTADOS_EN_PROCESO and estado_nuevo == ESTADO_TERMINADA:
            if not fecha_salida:
                fecha_salida, hora_salida = now_fecha_hora()

        # TERMINADA -> EN PROCESO (regreso)
        if estado_actual == ESTADO_TERMINADA and estado_nuevo in ESTADOS_EN_PROCESO:
            if not fecha_regreso:
                fecha_regreso, hora_regreso = now_fecha_hora()

        # -> RETIRADA (solo si venía TERMINADA)
        if estado_nuevo == ESTADO_RETIRADA:
            if estado_actual != ESTADO_TERMINADA:
                cur.close(); conn.close()
                return jsonify({"ok": False, "error": "Para retirar, la orden debe estar TERMINADA"}), 400
            if not fecha_retiro:
                fecha_retiro, hora_retiro = now_fecha_hora()

        cur2 = conn.cursor()
        cur2.execute("""
            UPDATE ordenes
            SET cliente_id=%s,
                equipo_id=%s,
                falla=%s,
                observaciones=%s,
                accesorios=%s,
                reparacion=%s,
                repuestos=%s,
                importe=%s,
                estado=%s,
                fecha_salida=%s,
                hora_salida=%s,
                fecha_regreso=%s,
                hora_regreso=%s,
                fecha_retiro=%s,
                hora_retiro=%s
            WHERE id=%s
        """, (
            cliente_id,
            equipo_id,
            falla,
            observaciones,
            accesorios,
            reparacion,
            repuestos,
            importe,
            estado_nuevo,
            fecha_salida,
            hora_salida,
            fecha_regreso,
            hora_regreso,
            fecha_retiro,
            hora_retiro,
            orden_id
        ))

        conn.commit()

        # opcional: regenerar Word
        try:
            generar_word_de_orden(conn, orden_id)
        except Exception as e:
            print("WARN word:", e)

        cur2.close()
        cur.close()
        conn.close()

        return jsonify({"ok": True})

    except Exception as e:
        print("Error actualizar_orden:", e)
        return jsonify({"ok": False, "error": "Error al actualizar orden"}), 500

@app.route("/api/ordenes/<int:orden_id>", methods=["GET"])
def api_orden_por_id(orden_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
            o.*,
            c.nombre   AS nombre_contacto,
            COALESCE(NULLIF(TRIM(c.telefono),''), NULLIF(TRIM(c.celular),''), '') AS telefono_contacto,
            e.serie    AS serie_texto,
            CONCAT_WS(' ', e.descripcion, e.marca, e.modelo) AS equipo_texto
        FROM ordenes o
        LEFT JOIN clientes c ON c.id = o.cliente_id
        LEFT JOIN equipos   e ON e.id = o.equipo_id
        WHERE o.id=%s
        LIMIT 1
    """, (orden_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return jsonify(normalize_row(row))


    return jsonify(row)
@app.route("/api/ordenes/<int:orden_id>/retirar", methods=["POST"])
def orden_retirar(orden_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT id, estado, fecha_retiro, hora_retiro FROM ordenes WHERE id=%s", (orden_id,))
    o = cur.fetchone()
    if not o:
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "Orden no encontrada"}), 404

    if o["estado"] != "TERMINADA":
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "Para retirar, la orden debe estar TERMINADA"}), 400

    if not o["fecha_retiro"]:
        f, h = now_fecha_hora()
    else:
        f, h = o["fecha_retiro"], o["hora_retiro"]

    cur2 = conn.cursor()
    cur2.execute("""
        UPDATE ordenes
        SET estado='RETIRADA', fecha_retiro=%s, hora_retiro=%s
        WHERE id=%s
    """, (f, h, orden_id))
    conn.commit()
    cur2.close()

    cur.close(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/ordenes/<int:orden_id>/terminar", methods=["POST"])
def orden_terminar(orden_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT id, estado, fecha_salida, hora_salida FROM ordenes WHERE id=%s", (orden_id,))
    o = cur.fetchone()
    if not o:
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "Orden no encontrada"}), 404

    if o["estado"] == "RETIRADA":
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "La orden ya está retirada"}), 400

    # opcional: si querés setear salida automática al terminar, descomentá:
    # if not o["fecha_salida"]:
    #     f, h = now_fecha_hora()
    # else:
    #     f, h = o["fecha_salida"], o["hora_salida"]

    cur2 = conn.cursor()
    cur2.execute("UPDATE ordenes SET estado='TERMINADA' WHERE id=%s", (orden_id,))
    conn.commit()
    cur2.close()

    cur.close(); conn.close()
    return jsonify({"ok": True})


@app.route("/api/ordenes/<int:orden_id>/salida", methods=["POST"])
def orden_registrar_salida(orden_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT id, estado, fecha_salida, hora_salida FROM ordenes WHERE id=%s", (orden_id,))
    o = cur.fetchone()
    if not o:
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "Orden no encontrada"}), 404

    if o["estado"] == "RETIRADA":
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "La orden ya está retirada"}), 400

    if not o["fecha_salida"]:
        f, h = now_fecha_hora()
        cur2 = conn.cursor()
        cur2.execute("""
            UPDATE ordenes SET fecha_salida=%s, hora_salida=%s
            WHERE id=%s
        """, (f, h, orden_id))
        conn.commit()
        cur2.close()

    cur.close(); conn.close()
    return jsonify({"ok": True})

if __name__ == "__main__":
    # host 0.0.0.0 para que lo vean otras PCs de la red
    app.run(host="0.0.0.0", port=5000, debug=True)
