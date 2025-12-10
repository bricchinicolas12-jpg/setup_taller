from flask import Flask, render_template, request, jsonify
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date, time, timedelta
from mysql.connector.errors import IntegrityError


app = Flask(__name__, template_folder="templates", static_folder="static")

# ========= CONFIGURACIÓN DB =========
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",         # <-- CAMBIAR
    "password": "root",    # <-- CAMBIAR
    "database": "setup_db",
    "port": 3306,
}


def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def normalize_row(row: dict) -> dict:
    """Convierte date/datetime/timedelta a string para poder serializar a JSON."""
    new_row = {}
    for k, v in row.items():
        if isinstance(v, (datetime, date)):
            new_row[k] = v.isoformat()
        elif isinstance(v, timedelta):
            total = int(v.total_seconds())
            h = total // 3600
            m = (total % 3600) // 60
            s = total % 60
            new_row[k] = f"{h:02d}:{m:02d}:{s:02d}"
        else:
            new_row[k] = v
    return new_row

# ========= HELPERS DE CATALOGO / RELACIONES =========

def asegurar_cliente(conn, nombre, telefono=None):
    """Busca cliente por nombre+tel; si no existe lo crea."""
    if not nombre:
        return None
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
    nuevo_id = cur.lastrowid
    cur.close()
    return nuevo_id


def asegurar_equipo(conn, descripcion, serie):
    """Busca equipo por serie (o por descripción si no hay serie); si no existe lo crea."""
    if not descripcion and not serie:
        return None
    cur = conn.cursor()

    if serie:
        cur.execute("SELECT id FROM equipos WHERE serie=%s", (serie,))
        row = cur.fetchone()
        if row:
            cur.close()
            return row[0]

    # si no hay serie o no se encontró, probar por descripción
    if descripcion:
        cur.execute(
            "SELECT id FROM equipos WHERE descripcion=%s AND (serie IS NULL OR serie='')",
            (descripcion,),
        )
        row = cur.fetchone()
        if row:
            cur.close()
            return row[0]

    # crear equipo nuevo
    cur.execute(
        "INSERT INTO equipos (descripcion, serie) VALUES (%s, %s)",
        (descripcion, serie),
    )
    conn.commit()
    nuevo_id = cur.lastrowid
    cur.close()
    return nuevo_id


def vincular_equipo_cliente(conn, equipo_id, cliente_id, rol="propietario"):
    """Crea relación equipo_cliente si no existe."""
    if not equipo_id or not cliente_id:
        return
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id FROM equipo_cliente
        WHERE equipo_id=%s AND cliente_id=%s AND activo=1
        """,
        (equipo_id, cliente_id),
    )
    if cur.fetchone():
        cur.close()
        return
    cur.execute(
        """
        INSERT INTO equipo_cliente (equipo_id, cliente_id, rol)
        VALUES (%s, %s, %s)
        """,
        (equipo_id, cliente_id, rol),
    )
    conn.commit()
    cur.close()


def asegurar_falla(conn, descripcion):
    if not descripcion:
        return None
    cur = conn.cursor()
    cur.execute("SELECT id FROM fallas WHERE descripcion=%s", (descripcion,))
    row = cur.fetchone()
    if row:
        cur.close()
        return row[0]
    cur.execute("INSERT INTO fallas (descripcion) VALUES (%s)", (descripcion,))
    conn.commit()
    nuevo_id = cur.lastrowid
    cur.close()
    return nuevo_id


def asegurar_accesorio(conn, nombre):
    if not nombre:
        return None
    cur = conn.cursor()
    cur.execute("SELECT id FROM accesorios WHERE nombre=%s", (nombre,))
    row = cur.fetchone()
    if row:
        cur.close()
        return row[0]
    cur.execute("INSERT INTO accesorios (nombre) VALUES (%s)", (nombre,))
    conn.commit()
    nuevo_id = cur.lastrowid
    cur.close()
    return nuevo_id


def asegurar_repuesto(conn, nombre):
    if not nombre:
        return None
    cur = conn.cursor()
    cur.execute("SELECT id FROM repuestos WHERE nombre=%s", (nombre,))
    row = cur.fetchone()
    if row:
        cur.close()
        return row[0]
    cur.execute("INSERT INTO repuestos (nombre) VALUES (%s)", (nombre,))
    conn.commit()
    nuevo_id = cur.lastrowid
    cur.close()
    return nuevo_id


# ========= RUTAS HTML =========

@app.route("/")
def index():
    return render_template("ordenes.html")


# ========= API CATÁLOGOS =========

@app.route("/api/fallas", methods=["GET"])
def api_fallas():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, descripcion FROM fallas ORDER BY descripcion")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)


@app.route("/api/accesorios", methods=["GET"])
def api_accesorios():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, nombre FROM accesorios ORDER BY nombre")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)


@app.route("/api/repuestos", methods=["GET"])
def api_repuestos():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, nombre FROM repuestos ORDER BY nombre")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)
# ========= API CLIENTES (ABM sencillo) =========

@app.route("/api/clientes", methods=["GET"])
def api_clientes():
    """Lista completa de clientes (para tabs y datalist)."""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM clientes ORDER BY nombre")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([normalize_row(r) for r in rows])


@app.route("/api/clientes", methods=["POST"])
def crear_cliente():
    data = request.json or {}
    if not data.get("nombre"):
        return jsonify({"error": "El nombre es obligatorio"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO clientes
            (nombre, telefono, direccion, localidad, provincia, cp, email, cuit,
             contacto, observaciones, giro_empresa, cliente_garantia, cliente_con_contrato)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                data.get("nombre"),
                data.get("telefono"),
                data.get("direccion"),
                data.get("localidad"),
                data.get("provincia"),
                data.get("cp"),
                data.get("email"),
                data.get("cuit"),
                data.get("contacto"),
                data.get("observaciones"),
                data.get("giro_empresa"),
                1 if data.get("cliente_garantia") else 0,
                1 if data.get("cliente_con_contrato") else 0,
            ),
        )
        conn.commit()
        nuevo_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"ok": True, "id": nuevo_id})
    except Error as e:
        print("Error crear_cliente:", e)
        return jsonify({"error": "Error al guardar cliente"}), 500


@app.route("/api/clientes/<int:cliente_id>", methods=["PUT"])
def modificar_cliente(cliente_id):
    data = request.json or {}
    if not data.get("nombre"):
        return jsonify({"error": "El nombre es obligatorio"}), 400
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE clientes
            SET nombre=%s,
                telefono=%s,
                direccion=%s,
                localidad=%s,
                provincia=%s,
                cp=%s,
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
                data.get("nombre"),
                data.get("telefono"),
                data.get("direccion"),
                data.get("localidad"),
                data.get("provincia"),
                data.get("cp"),
                data.get("email"),
                data.get("cuit"),
                data.get("contacto"),
                data.get("observaciones"),
                data.get("giro_empresa"),
                1 if data.get("cliente_garantia") else 0,
                1 if data.get("cliente_con_contrato") else 0,
                cliente_id,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": True})
    except Error as e:
        print("Error modificar_cliente:", e)
        return jsonify({"error": "Error al modificar cliente"}), 500


# ========= API EQUIPOS (siempre ligados a un cliente) =========

@app.route("/api/equipos", methods=["GET"])
def api_equipos():
    """Lista de equipos con nombres de clientes asociados (concat)."""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT e.*,
               GROUP_CONCAT(c.nombre SEPARATOR ', ') AS clientes
        FROM equipos e
        LEFT JOIN equipo_cliente ec ON e.id = ec.equipo_id AND ec.activo=1
        LEFT JOIN clientes c ON ec.cliente_id = c.id
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
    if not data.get("descripcion") and not data.get("serie"):
        return jsonify({"error": "Debe indicar al menos descripción o serie"}), 400
    cliente_id = data.get("cliente_id")
    if not cliente_id:
        return jsonify({"error": "Debe seleccionar un cliente para el equipo"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO equipos (tipo, marca, modelo, serie, descripcion)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (
                data.get("tipo"),
                data.get("marca"),
                data.get("modelo"),
                data.get("serie"),
                data.get("descripcion"),
            ),
        )
        conn.commit()
        equipo_id = cur.lastrowid
        cur.close()

        # vincular con cliente (usa helper que ya tenés)
        vincular_equipo_cliente(conn, equipo_id, int(cliente_id), "propietario")

        conn.close()
        return jsonify({"ok": True, "id": equipo_id})
    except Error as e:
        print("Error crear_equipo:", e)
        return jsonify({"error": "Error al guardar equipo"}), 500


@app.route("/api/equipos/<int:equipo_id>", methods=["PUT"])
def modificar_equipo_api(equipo_id):
    data = request.json or {}
    if not data.get("descripcion") and not data.get("serie"):
        return jsonify({"error": "Debe indicar al menos descripción o serie"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE equipos
            SET tipo=%s,
                marca=%s,
                modelo=%s,
                serie=%s,
                descripcion=%s
            WHERE id=%s
            """,
            (
                data.get("tipo"),
                data.get("marca"),
                data.get("modelo"),
                data.get("serie"),
                data.get("descripcion"),
                equipo_id,
            ),
        )
        conn.commit()
        cur.close()

        # si envían cliente_id, garantizar vínculo (no borramos otros)
        if data.get("cliente_id"):
            vincular_equipo_cliente(conn, equipo_id, int(data.get("cliente_id")), "propietario")

        conn.close()
        return jsonify({"ok": True})
    except Error as e:
        print("Error modificar_equipo:", e)
        return jsonify({"error": "Error al modificar equipo"}), 500



# ========= API ORDENES =========

@app.route("/api/ordenes", methods=["GET"])
def listar_ordenes():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM ordenes ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    rows = [normalize_row(r) for r in rows]
    return jsonify(rows)



@app.route("/api/ordenes/<int:nro>", methods=["GET"])
def obtener_orden(nro):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM ordenes WHERE id=%s", (nro,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({"error": "No existe esa orden"}), 404
    row = normalize_row(row)
    return jsonify(row)



@app.route("/api/ordenes", methods=["POST"])
def crear_orden():
    data = request.json or {}

    if not data.get("nombre"):
        return jsonify({"error": "El nombre es obligatorio"}), 400

    # fecha/hora ingreso automáticas si no las mandan
    fecha = data.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    hora_ingreso = data.get("hora_ingreso") or datetime.now().strftime("%H:%M:%S")

    try:
        conn = get_db()

        # asegurar cliente/equipo y relación
        cliente_id = asegurar_cliente(conn, data.get("nombre"), data.get("telefono"))
        equipo_id = asegurar_equipo(conn, data.get("equipo"), data.get("serie"))
        vincular_equipo_cliente(conn, equipo_id, cliente_id)

        # catálogos
        asegurar_falla(conn, data.get("falla"))
        asegurar_accesorio(conn, data.get("accesorios"))
        asegurar_repuesto(conn, data.get("repuestos"))

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ordenes
            (cliente_id, equipo_id,
             fecha, hora_ingreso,
             fecha_salida, hora_salida,
             fecha_regreso, hora_regreso,
             nombre_contacto, telefono_contacto,
             equipo_texto, serie_texto,
             falla, observaciones, accesorios,
             reparacion, repuestos,
             importe, estado)
            VALUES
            (%s,%s,
             %s,%s,
             %s,%s,
             %s,%s,
             %s,%s,
             %s,%s,
             %s,%s,%s,
             %s,%s,
             %s,%s)
            """,
            (
                cliente_id,
                equipo_id,
                fecha,
                hora_ingreso,
                data.get("fecha_salida") or None,
                data.get("hora_salida") or None,
                data.get("fecha_regreso") or None,
                data.get("hora_regreso") or None,
                data.get("nombre"),
                data.get("telefono"),
                data.get("equipo"),
                data.get("serie"),
                data.get("falla"),
                data.get("observaciones"),
                data.get("accesorios"),
                data.get("reparacion"),
                data.get("repuestos"),
                float(data.get("importe") or 0),
                data.get("estado") or "EN REPARACION",
            ),
        )
        conn.commit()
        nuevo_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"ok": True, "id": nuevo_id})
    except Error as e:
        print("Error MySQL crear_orden:", e)
        return jsonify({"error": "Error al guardar"}), 500


@app.route("/api/ordenes/<int:nro>", methods=["PUT"])
def modificar_orden(nro):
    data = request.json or {}

    ESTADOS_EXTERNOS = {
        "EN SOS", "EN WIRTECH", "EN EKON",
        "EN AIR", "EN SERVPRINT", "EN NICO GORI"
    }

    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT estado, fecha_salida, hora_salida,
                   fecha_regreso, hora_regreso
            FROM ordenes WHERE id=%s
            """,
            (nro,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return jsonify({"error": "No existe esa orden"}), 404

        estado_actual = row["estado"]
        fecha_salida = row["fecha_salida"]
        hora_salida = row["hora_salida"]
        fecha_regreso = row["fecha_regreso"]
        hora_regreso = row["hora_regreso"]

        nuevo_estado = data.get("estado", estado_actual)
        hoy = datetime.now().strftime("%Y-%m-%d")
        ahora = datetime.now().strftime("%H:%M:%S")

        # permitir override manual
        if data.get("fecha_salida"):
            fecha_salida = data["fecha_salida"]
        if data.get("hora_salida"):
            hora_salida = data["hora_salida"]
        if data.get("fecha_regreso"):
            fecha_regreso = data["fecha_regreso"]
        if data.get("hora_regreso"):
            hora_regreso = data["hora_regreso"]

        # lógica automática si sigue vacío
        if estado_actual not in ESTADOS_EXTERNOS and nuevo_estado in ESTADOS_EXTERNOS:
            if not fecha_salida:
                fecha_salida = hoy
            if not hora_salida:
                hora_salida = ahora

        if estado_actual in ESTADOS_EXTERNOS and nuevo_estado not in ESTADOS_EXTERNOS:
            if not fecha_regreso:
                fecha_regreso = hoy
            if not hora_regreso:
                hora_regreso = ahora

        # cliente/equipo
        cliente_id = asegurar_cliente(conn, data.get("nombre"), data.get("telefono"))
        equipo_id = asegurar_equipo(conn, data.get("equipo"), data.get("serie"))
        vincular_equipo_cliente(conn, equipo_id, cliente_id)

        cur.close()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE ordenes
            SET cliente_id=%s,
                equipo_id=%s,
                fecha=%s,
                hora_ingreso=%s,
                fecha_salida=%s,
                hora_salida=%s,
                fecha_regreso=%s,
                hora_regreso=%s,
                nombre_contacto=%s,
                telefono_contacto=%s,
                equipo_texto=%s,
                serie_texto=%s,
                falla=%s,
                observaciones=%s,
                accesorios=%s,
                reparacion=%s,
                repuestos=%s,
                importe=%s,
                estado=%s
            WHERE id=%s
            """,
            (
                cliente_id,
                equipo_id,
                data.get("fecha") or row.get("fecha"),
                data.get("hora_ingreso") or row.get("hora_ingreso"),
                fecha_salida,
                hora_salida,
                fecha_regreso,
                hora_regreso,
                data.get("nombre"),
                data.get("telefono"),
                data.get("equipo"),
                data.get("serie"),
                data.get("falla"),
                data.get("observaciones"),
                data.get("accesorios"),
                data.get("reparacion"),
                data.get("repuestos"),
                float(data.get("importe") or 0),
                nuevo_estado,
                nro,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": True})
    except Error as e:
        print("Error MySQL modificar_orden:", e)
        return jsonify({"error": "Error al modificar"}), 500

# =========================================================
#                     FALLAS
# =========================================================

# =========================================================
#                     FALLAS
# =========================================================

@app.route("/api/fallas", methods=["GET"])
def api_listar_fallas():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, descripcion FROM fallas ORDER BY descripcion")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)


@app.route("/api/fallas", methods=["POST"])
def api_crear_falla():
    data = request.get_json() or {}
    desc = (data.get("descripcion") or "").strip()

    if not desc:
        return jsonify({"ok": False, "error": "Descripción obligatoria"}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO fallas (descripcion) VALUES (%s)", (desc,))
        conn.commit()
        new_id = cur.lastrowid
        return jsonify({"ok": True, "id": new_id})
    except IntegrityError:
        conn.rollback()
        # choca contra el índice único uk_falla_unica
        return (
            jsonify({"ok": False, "error": "Ya existe una falla con esa descripción"}),
            409,
        )
    finally:
        cur.close()
        conn.close()


# =========================================================
#                   REPARACIONES
# =========================================================

@app.route("/api/reparaciones", methods=["GET"])
def api_listar_reparaciones():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, descripcion FROM reparaciones ORDER BY descripcion")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)


@app.route("/api/reparaciones", methods=["POST"])
def api_crear_reparacion():
    data = request.get_json() or {}
    desc = (data.get("descripcion") or "").strip()

    if not desc:
        return jsonify({"ok": False, "error": "Descripción obligatoria"}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO reparaciones (descripcion) VALUES (%s)", (desc,))
        conn.commit()
        new_id = cur.lastrowid
        return jsonify({"ok": True, "id": new_id})
    except IntegrityError:
        conn.rollback()
        # si tenés un índice único para reparaciones
        return (
            jsonify({"ok": False, "error": "Ya existe una reparación con esa descripción"}),
            409,
        )
    finally:
        cur.close()
        conn.close()



# =========================================================
#                     REPUESTOS
# =========================================================

@app.route("/api/repuestos", methods=["GET"])
def api_listar_repuestos():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, nombre, descripcion, costo FROM repuestos ORDER BY nombre")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)


import mysql.connector  # asegúrate de tener este import arriba del archivo
# ...

@app.route("/api/repuestos", methods=["POST"])
def api_crear_repuesto():
    data = request.get_json()

    nombre = data.get("nombre")
    descripcion = data.get("descripcion")
    costo = data.get("costo")

    if not nombre:
        return jsonify({"ok": False, "error": "El nombre es obligatorio"}), 400

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO repuestos (nombre, descripcion, costo)
            VALUES (%s, %s, %s)
        """, (nombre, descripcion, costo))

        conn.commit()
        new_id = cur.lastrowid

    except mysql.connector.errors.IntegrityError as e:
        # Error 1062 = entrada duplicada (rompe el índice único)
        if e.errno == 1062:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({
                "ok": False,
                "error": "Ya existe un repuesto con esos datos (índice único uk_repuesto_unico)."
            }), 409
        # cualquier otro error de integridad lo re-lanzamos
        conn.rollback()
        cur.close()
        conn.close()
        raise

    cur.close()
    conn.close()

    return jsonify({"ok": True, "id": new_id})


if __name__ == "__main__":
    # host 0.0.0.0 para que lo vean otras PCs de la red
    app.run(host="0.0.0.0", port=5000, debug=True)
