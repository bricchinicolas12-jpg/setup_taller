

import pandas as pd
import mysql.connector
from pathlib import Path

# -------------------------
# CONFIGURACIÓN DE LA BD
# -------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",        # <-- tu usuario MySQL
    "password": "root",   # <-- tu contraseña
    "database": "setup_db",      # <-- tu base de datos
}

# Carpeta donde está ESTE archivo .py
BASE_DIR = Path(__file__).resolve().parent

# Nombre del archivo Excel a importar (en la misma carpeta que el .py)
EXCEL_FILE = BASE_DIR / "clientes otro.xlsx"
SHEET_NAME = 0  # primera hoja


# -------------------------
# FUNCIONES AUXILIARES
# -------------------------
def s(val):
    """Convierte valores de pandas a str o None, quitando NaN y espacios."""
    if pd.isna(val):
        return None
    text = str(val).strip()
    return text or None


def s_int(val):
    """Convierte a int o None (sirve para CODIGO, etc.)."""
    if pd.isna(val) or val == "":
        return None
    try:
        return int(val)
    except ValueError:
        try:
            return int(float(val))
        except Exception:
            return None


# -------------------------
# IMPORTAR CLIENTES
# -------------------------
def importar_clientes_desde_excel(ruta_excel: str):
    print(f"Leyendo archivo Excel: {ruta_excel} ...")

    # El Excel NO tiene encabezados -> header=None
    df = pd.read_excel(ruta_excel, sheet_name=SHEET_NAME, header=None)

    # Asignar nombres de columna manualmente, en el orden exacto que nos diste
    df.columns = [
        "CODIGO",
        "R_SOC",
        "CATEGORIA",
        "DIRE",
        "NRO_CASA",
        "LOCALIDAD",
        "COD_POS",
        "PROVINCIA",
        "CUIT",
        "COD_IVA",
        "COD_TASA",
        "ING_BRU",
        "TELEFONO",
        "DOCUMENTO",
        "OBSERVA",
        "FEC_NAC",
        "E_MAIL",
    ]

    print("Columnas asignadas al DataFrame:")
    print(list(df.columns))

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    filas_ok = 0
    filas_err = 0

    for idx, row in df.iterrows():
        try:
            # ----- Mapear columnas del Excel a los campos de la tabla clientes -----
            codigo = s_int(row["CODIGO"])        # id
            nombre = s(row["R_SOC"])             # razón social / nombre
            telefono = s(row["TELEFONO"])

            # Dirección = calle + número
            dire = s(row["DIRE"])
            nro_casa = s(row["NRO_CASA"])
            if dire and nro_casa:
                direccion = f"{dire} {nro_casa}"
            else:
                direccion = dire or nro_casa

            localidad = s(row["LOCALIDAD"])
            provincia = s(row["PROVINCIA"])
            cp = s(row["COD_POS"])
            email = s(row["E_MAIL"])
            cuit = s(row["CUIT"])
            contacto = s(row["DOCUMENTO"])       # podés cambiar esto después si querés

            # Armar un campo de observaciones más completo
            obs_partes = []
            cat = s(row["CATEGORIA"])
            if cat:
                obs_partes.append(f"Categoría: {cat}")
            cod_iva = s(row["COD_IVA"])
            if cod_iva:
                obs_partes.append(f"IVA: {cod_iva}")
            cod_tasa = s(row["COD_TASA"])
            if cod_tasa:
                obs_partes.append(f"Tasa: {cod_tasa}")
            ing_bru = s(row["ING_BRU"])
            if ing_bru:
                obs_partes.append(f"Ingresos Brutos: {ing_bru}")
            obs_excel = s(row["OBSERVA"])
            if obs_excel:
                obs_partes.append(f"Obs: {obs_excel}")
            fec_nac = s(row["FEC_NAC"])
            if fec_nac:
                obs_partes.append(f"Fec. Nac: {fec_nac}")

            observaciones = " | ".join(obs_partes) if obs_partes else None

            # Podés usar CATEGORIA como giro_empresa si querés
            giro_empresa = cat

            # Flags por ahora en 0 (podés ajustarlos a mano después)
            cliente_garantia = 0
            cliente_con_contrato = 0

            # Si no hay código, no tiene sentido insertarlo
            if codigo is None:
                raise ValueError("Cliente sin CODIGO, se omite.")

            # ----- INSERT / UPDATE en la tabla clientes -----
            cur.execute(
                """
                INSERT INTO clientes (
                    id, nombre, telefono, direccion, localidad, provincia, cp,
                    email, cuit, contacto, observaciones, giro_empresa,
                    cliente_garantia, cliente_con_contrato
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    nombre = VALUES(nombre),
                    telefono = VALUES(telefono),
                    direccion = VALUES(direccion),
                    localidad = VALUES(localidad),
                    provincia = VALUES(provincia),
                    cp = VALUES(cp),
                    email = VALUES(email),
                    cuit = VALUES(cuit),
                    contacto = VALUES(contacto),
                    observaciones = VALUES(observaciones),
                    giro_empresa = VALUES(giro_empresa),
                    cliente_garantia = VALUES(cliente_garantia),
                    cliente_con_contrato = VALUES(cliente_con_contrato)
                """,
                (
                    codigo,
                    nombre,
                    telefono,
                    direccion,
                    localidad,
                    provincia,
                    cp,
                    email,
                    cuit,
                    contacto,
                    observaciones,
                    giro_empresa,
                    cliente_garantia,
                    cliente_con_contrato,
                ),
            )
            filas_ok += 1
        except Exception as e:
            filas_err += 1
            print(f"[Fila {idx + 1}] Error importando cliente: {e}")

    conn.commit()
    cur.close()
    conn.close()

    print(f"Importación finalizada. OK: {filas_ok}, con error: {filas_err}")


if __name__ == "__main__":
    importar_clientes_desde_excel(str(EXCEL_FILE))
