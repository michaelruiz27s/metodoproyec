from flask import Blueprint, request, jsonify
import math
import re
import os
import mysql.connector
import numpy as np
import plotly.graph_objs as go
import plotly.io as pio


newton_sis_bp = Blueprint("newton_sistemas", __name__)
MAX_ITER = 50


def _db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="david98",
        database="metodos_numericos",
    )


def _asegurar_tabla():
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS metodo_newton_sistemas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ejercicio INT NOT NULL,
            iteracion INT NOT NULL,
            x DOUBLE,
            y DOUBLE,
            z DOUBLE,
            fx DOUBLE,
            fy DOUBLE,
            fz DOUBLE,
            ex DOUBLE,
            ey DOUBLE,
            ez DOUBLE
        )
        """
    )
    # Compatibilidad con esquemas antiguos de la tabla.
    cur.execute("SHOW COLUMNS FROM metodo_newton_sistemas")
    cols = {row[0].lower() for row in cur.fetchall()}
    columnas_requeridas = {
        "x": "DOUBLE",
        "y": "DOUBLE",
        "z": "DOUBLE",
        "fx": "DOUBLE",
        "fy": "DOUBLE",
        "fz": "DOUBLE",
        "ex": "DOUBLE",
        "ey": "DOUBLE",
        "ez": "DOUBLE",
    }
    for nombre, tipo in columnas_requeridas.items():
        if nombre not in cols:
            cur.execute(f"ALTER TABLE metodo_newton_sistemas ADD COLUMN {nombre} {tipo} NULL")
    conn.commit()
    cur.close()
    conn.close()


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


def _normalizar(expr: str) -> str:
    s = (expr or "").strip().lower()
    s = s.replace("−", "-").replace("–", "-").replace("—", "-")
    s = s.replace("×", "*").replace("·", "*")
    s = s.replace(" ", "")
    s = s.replace("raiz", "sqrt")
    s = s.replace("sen", "sin")
    s = s.replace("^", "**")
    s = s.replace("ln", "log")
    # implícitas
    s = re.sub(r"(\d)([a-zA-Z\(])", r"\1*\2", s)
    s = re.sub(r"([a-zA-Z\)])(\d)", r"\1*\2", s)
    s = re.sub(r"([xyz\)])\(", r"\1*(", s)
    s = re.sub(r"\)([a-zA-Zxyz])", r")*\1", s)
    return s


def _compilar(expr: str, etiqueta: str):
    codigo = compile(_normalizar(expr), f"<{etiqueta}>", "eval")
    safe = {name: getattr(math, name) for name in dir(math) if not name.startswith("__")}

    def fn(x: float, y: float, z: float) -> float:
        ctx = dict(safe)
        ctx["x"] = x
        ctx["y"] = y
        ctx["z"] = z
        val = eval(codigo, {"__builtins__": {}}, ctx)
        if isinstance(val, complex):
            if abs(val.imag) > 1e-10:
                raise ValueError(f"{etiqueta} produjo un valor no real.")
            val = val.real
        val = float(val)
        if not math.isfinite(val):
            raise ValueError(f"{etiqueta} produjo un valor no finito.")
        return val

    return fn


def _jacobiano_num(F, x, y, z):
    h = 1e-5
    fx, fy, fz = F(x, y, z)
    fx_xp, fy_xp, fz_xp = F(x + h, y, z)
    fx_xm, fy_xm, fz_xm = F(x - h, y, z)
    fx_yp, fy_yp, fz_yp = F(x, y + h, z)
    fx_ym, fy_ym, fz_ym = F(x, y - h, z)
    fx_zp, fy_zp, fz_zp = F(x, y, z + h)
    fx_zm, fy_zm, fz_zm = F(x, y, z - h)

    j11 = (fx_xp - fx_xm) / (2 * h)
    j21 = (fy_xp - fy_xm) / (2 * h)
    j31 = (fz_xp - fz_xm) / (2 * h)

    j12 = (fx_yp - fx_ym) / (2 * h)
    j22 = (fy_yp - fy_ym) / (2 * h)
    j32 = (fz_yp - fz_ym) / (2 * h)

    j13 = (fx_zp - fx_zm) / (2 * h)
    j23 = (fy_zp - fy_zm) / (2 * h)
    j33 = (fz_zp - fz_zm) / (2 * h)

    return np.array([[j11, j12, j13], [j21, j22, j23], [j31, j32, j33]], dtype=float)


def _guardar(ejercicio: int, filas):
    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM metodo_newton_sistemas WHERE ejercicio = %s", (ejercicio,))
    for fila in filas:
        cur.execute(
            """
            INSERT INTO metodo_newton_sistemas (ejercicio, iteracion, x, y, z, fx, fy, fz, ex, ey, ez)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            fila,
        )
    conn.commit()
    cur.close()
    conn.close()


def _graficar(ejercicio: int, filas):
    its = [f[1] for f in filas]
    ex = [abs(f[8]) for f in filas]
    ey = [abs(f[9]) for f in filas]
    ez = [abs(f[10]) for f in filas]

    fig = go.Figure(
        data=[
            go.Scatter(x=its, y=ex, mode="lines+markers", name="|Δx|", line=dict(color="#3b82f6")),
            go.Scatter(x=its, y=ey, mode="lines+markers", name="|Δy|", line=dict(color="#f59e0b")),
            go.Scatter(x=its, y=ez, mode="lines+markers", name="|Δz|", line=dict(color="#10b981")),
        ],
        layout=go.Layout(
            title="Convergencia — Newton para sistemas (3 variables)",
            xaxis=dict(title="Iteración", showgrid=True, gridcolor="lightgray"),
            yaxis=dict(title="Magnitud del cambio", showgrid=True, gridcolor="lightgray"),
            plot_bgcolor="white",
            paper_bgcolor="white",
        ),
    )
    os.makedirs("static/imagenes", exist_ok=True)
    ruta = f"static/imagenes/newton_sistemas_{ejercicio}.html"
    pio.write_html(fig, file=ruta, auto_open=False)
    return "/" + ruta


@newton_sis_bp.route("/newton-sistemas", methods=["POST"])
def ejecutar_newton_sistemas():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        f1_expr = _campo_texto("f1", "F1(x,y,z)")
        f2_expr = _campo_texto("f2", "F2(x,y,z)")
        f3_expr = _campo_texto("f3", "F3(x,y,z)")
        x = _campo_float("x", "x inicial")
        y = _campo_float("y", "y inicial")
        z = _campo_float("z", "z inicial")
        es = _campo_float("es", "Es (tolerancia)")
        if es <= 0:
            raise ValueError("Es debe ser mayor que 0.")

        f1 = _compilar(f1_expr, "F1")
        f2 = _compilar(f2_expr, "F2")
        f3 = _compilar(f3_expr, "F3")

        def F(xx, yy, zz):
            return (f1(xx, yy, zz), f2(xx, yy, zz), f3(xx, yy, zz))

        filas = []
        for it in range(1, MAX_ITER + 1):
            fx, fy, fz = F(x, y, z)
            J = _jacobiano_num(F, x, y, z)
            b = -np.array([fx, fy, fz], dtype=float)
            try:
                delta = np.linalg.solve(J, b)
            except np.linalg.LinAlgError:
                raise ValueError("Jacobiano singular o mal condicionado en esta iteración.")

            dx, dy, dz = float(delta[0]), float(delta[1]), float(delta[2])
            x_new, y_new, z_new = x + dx, y + dy, z + dz
            filas.append((ejercicio, it, x, y, z, fx, fy, fz, dx, dy, dz))

            if it > 1 and max(abs(dx), abs(dy), abs(dz)) < es:
                x, y, z = x_new, y_new, z_new
                break

            x, y, z = x_new, y_new, z_new

        _guardar(ejercicio, filas)
        imagen = ""
        try:
            imagen = _graficar(ejercicio, filas)
        except Exception:
            imagen = ""
        return jsonify({"mensaje": "Newton para sistemas guardado correctamente.", "imagen": imagen})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print("Error Newton sistemas:", repr(e))
        return jsonify({"error": str(e)}), 500


@newton_sis_bp.route("/resultados-newton-sistemas")
def resultados_newton_sistemas():
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ejercicio, iteracion, x, y, z, fx, fy, fz, ex, ey, ez
            FROM metodo_newton_sistemas
            ORDER BY ejercicio ASC, iteracion ASC
            """
        )
        filas = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@newton_sis_bp.route("/buscar_ejercicio_newton_sistemas/<int:ejercicio>", methods=["GET"])
def buscar_ejercicio_newton_sistemas(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ejercicio, iteracion, x, y, z, fx, fy, fz, ex, ey, ez
            FROM metodo_newton_sistemas
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


@newton_sis_bp.route("/eliminar-newton-sistemas/<int:ejercicio>", methods=["DELETE"])
def eliminar_newton_sistemas(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute("DELETE FROM metodo_newton_sistemas WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"mensaje": f"Registros del ejercicio #{ejercicio} eliminados correctamente."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@newton_sis_bp.route("/actualizar-newton-sistemas", methods=["POST"])
def actualizar_newton_sistemas():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM metodo_newton_sistemas WHERE ejercicio = %s", (ejercicio,))
        existe = cur.fetchone()[0] > 0
        cur.close()
        conn.close()
        if not existe:
            return jsonify({"error": f"No existe el ejercicio #{ejercicio}. Primero use Calcular."}), 404
        request.form = request.form.copy()
        request.form["ejercicio"] = str(ejercicio)
        return ejecutar_newton_sistemas()
    except ValueError:
        return jsonify({"error": "Ejercicio debe ser un número entero válido."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

