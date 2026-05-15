from flask import Blueprint, request, jsonify
import math
import os
import mysql.connector
import plotly.graph_objs as go
import plotly.io as pio


bairstow_bp = Blueprint("bairstow", __name__)
MAX_ITER = 100


def _db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="metodos_numericos",
    )


def _asegurar_tabla():
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS metodo_bairstow (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ejercicio INT NOT NULL,
            iteracion INT NOT NULL,
            r DOUBLE,
            s DOUBLE,
            dr DOUBLE,
            ds DOUBLE,
            ea DOUBLE
        )
        """
    )
    conn.commit()
    cur.close()
    conn.close()


def _obtener_columnas_tabla():
    conn = _db()
    cur = conn.cursor()
    cur.execute("SHOW COLUMNS FROM metodo_bairstow")
    columnas = [fila[0] for fila in cur.fetchall()]
    cur.close()
    conn.close()
    return set(columnas)


def _campo_texto(nombre, etiqueta):
    v = (request.form.get(nombre) or "").strip()
    if not v:
        raise ValueError(f"Complete {etiqueta}.")
    return v


def _campo_float(nombre, etiqueta):
    raw = _campo_texto(nombre, etiqueta)
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{etiqueta} debe ser un número válido.") from exc


def _parse_coeficientes(texto: str):
    # Espera: "1, -3, 2, 5" (de mayor a menor grado)
    partes = [p.strip() for p in texto.replace(";", ",").split(",") if p.strip()]
    if len(partes) < 3:
        raise ValueError("Ingrese al menos 3 coeficientes (grado >= 2).")
    try:
        return [float(p) for p in partes]
    except ValueError as exc:
        raise ValueError("Coeficientes inválidos. Use números separados por coma.") from exc


def _bairstow(a, r, s, es):
    n = len(a) - 1
    if n < 2:
        raise ValueError("El polinomio debe ser de grado >= 2.")

    filas = []

    for it in range(1, MAX_ITER + 1):
        b = [0.0] * (n + 1)
        c = [0.0] * (n + 1)

        b[n] = a[n]
        b[n - 1] = a[n - 1] + r * b[n]
        for i in range(n - 2, -1, -1):
            b[i] = a[i] + r * b[i + 1] + s * b[i + 2]

        c[n] = b[n]
        c[n - 1] = b[n - 1] + r * c[n]
        for i in range(n - 2, 0, -1):
            c[i] = b[i] + r * c[i + 1] + s * c[i + 2]

        det = (c[2] * c[2]) - (c[3] * c[1]) if n >= 3 else (c[2] * c[2])
        if abs(det) < 1e-14:
            raise ValueError("El sistema para Δr/Δs es singular con los valores iniciales.")

        # Sistema lineal estándar:
        # [c2 c3][dr] = [-b1]
        # [c1 c2][ds] = [-b0]
        # Nota: índices dependen de convención; aquí b[0], b[1] son residuos.
        c1 = c[1] if n >= 3 else 0.0
        c2 = c[2]
        c3 = c[3] if n >= 3 else 0.0

        rhs1 = -b[1]
        rhs2 = -b[0]

        if n >= 3:
            dr = (rhs1 * c2 - rhs2 * c3) / det
            ds = (rhs2 * c2 - rhs1 * c1) / det
        else:
            dr = rhs1 / c2 if abs(c2) > 1e-14 else 0.0
            ds = 0.0

        r_new = r + dr
        s_new = s + ds
        ea = 0.0 if it == 1 or (r_new == 0 and s_new == 0) else max(
            abs(dr / (r_new if r_new != 0 else 1)) * 100.0,
            abs(ds / (s_new if s_new != 0 else 1)) * 100.0,
        )
        filas.append((it, r, s, dr, ds, round(ea, 4)))

        if it > 1 and ea < es:
            r, s = r_new, s_new
            break

        r, s = r_new, s_new

    return filas


def _guardar(ejercicio: int, filas):
    columnas_existentes = _obtener_columnas_tabla()
    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM metodo_bairstow WHERE ejercicio = %s", (ejercicio,))

    columnas_insert = ["ejercicio", "iteracion", "r", "s", "dr", "ds", "ea"]
    if "factor" in columnas_existentes:
        columnas_insert.append("factor")
    if "grado" in columnas_existentes:
        columnas_insert.append("grado")
    if "b1" in columnas_existentes:
        columnas_insert.append("b1")
    if "b0" in columnas_existentes:
        columnas_insert.append("b0")
    if "raiz1" in columnas_existentes:
        columnas_insert.append("raiz1")
    if "raiz2" in columnas_existentes:
        columnas_insert.append("raiz2")

    placeholders = ",".join(["%s"] * len(columnas_insert))
    sql = f"INSERT INTO metodo_bairstow ({','.join(columnas_insert)}) VALUES ({placeholders})"

    for it, r, s, dr, ds, ea in filas:
        valores = [ejercicio, it, r, s, dr, ds, ea]
        if "factor" in columnas_existentes:
            valores.append(0)
        if "grado" in columnas_existentes:
            valores.append(2)
        if "b1" in columnas_existentes:
            valores.append(0.0)
        if "b0" in columnas_existentes:
            valores.append(0.0)
        if "raiz1" in columnas_existentes:
            valores.append("")
        if "raiz2" in columnas_existentes:
            valores.append("")
        cur.execute(sql, tuple(valores))
    conn.commit()
    cur.close()
    conn.close()


def _graficar(ejercicio: int, filas):
    its = [f[0] for f in filas]
    ea = [f[5] for f in filas]
    fig = go.Figure(
        data=[go.Scatter(x=its, y=ea, mode="lines+markers", name="Ea", line=dict(color="#3b82f6"))],
        layout=go.Layout(
            title="Convergencia — Método de Bairstow",
            xaxis=dict(title="Iteración", showgrid=True, gridcolor="lightgray"),
            yaxis=dict(title="Ea (%)", showgrid=True, gridcolor="lightgray"),
            plot_bgcolor="white",
            paper_bgcolor="white",
        ),
    )
    os.makedirs("static/imagenes", exist_ok=True)
    ruta = f"static/imagenes/bairstow_{ejercicio}.html"
    pio.write_html(fig, file=ruta, auto_open=False)
    return "/" + ruta


@bairstow_bp.route("/bairstow", methods=["POST"])
def ejecutar_bairstow():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        coef_raw = _campo_texto("coeficientes", "coeficientes del polinomio")
        r = _campo_float("r", "r inicial")
        s = _campo_float("s", "s inicial")
        es = _campo_float("es", "Es%")
        if es <= 0:
            raise ValueError("Es% debe ser mayor que 0.")

        a = _parse_coeficientes(coef_raw)
        filas = _bairstow(a, r, s, es)
        _guardar(ejercicio, filas)

        imagen = ""
        try:
            imagen = _graficar(ejercicio, filas)
        except Exception:
            imagen = ""
        return jsonify({"mensaje": "Bairstow guardado correctamente.", "imagen": imagen})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bairstow_bp.route("/resultados-bairstow")
def resultados_bairstow():
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ejercicio, iteracion, r, s, dr, ds, ea
            FROM metodo_bairstow
            ORDER BY ejercicio ASC, iteracion ASC
            """
        )
        filas = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bairstow_bp.route("/buscar_ejercicio_bairstow/<int:ejercicio>", methods=["GET"])
def buscar_ejercicio_bairstow(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ejercicio, iteracion, r, s, dr, ds, ea
            FROM metodo_bairstow
            WHERE ejercicio = %s
            ORDER BY iteracion ASC
            """,
            (ejercicio,),
        )
        filas = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bairstow_bp.route("/eliminar-bairstow/<int:ejercicio>", methods=["DELETE"])
def eliminar_bairstow(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute("DELETE FROM metodo_bairstow WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"mensaje": f"Registros del ejercicio #{ejercicio} eliminados correctamente."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bairstow_bp.route("/actualizar-bairstow", methods=["POST"])
def actualizar_bairstow():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM metodo_bairstow WHERE ejercicio = %s", (ejercicio,))
        existe = cur.fetchone()[0] > 0
        cur.close()
        conn.close()
        if not existe:
            return jsonify({"error": f"No existe el ejercicio #{ejercicio}. Primero use Calcular."}), 404
        request.form = request.form.copy()
        request.form["ejercicio"] = str(ejercicio)
        return ejecutar_bairstow()
    except ValueError:
        return jsonify({"error": "Ejercicio debe ser un número entero válido."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

