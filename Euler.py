from flask import Blueprint, request, jsonify
import math
import re
import os
from database import get_connection
import plotly.graph_objs as go
import plotly.io as pio
import numpy as np


euler_bp = Blueprint("euler", __name__)
MAX_ITER = 1000


def _db():
    return get_connection()


def _asegurar_tabla():
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS metodo_euler (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ejercicio INT NOT NULL,
            tipo VARCHAR(8) NOT NULL,
            iteracion INT NOT NULL,
            x DOUBLE,
            y DOUBLE,
            fxy DOUBLE,
            y_nuevo DOUBLE,
            ea DOUBLE
        )
        """
    )
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
    # Multiplicación implícita
    s = re.sub(r"(\d)([a-zA-Z\(])", r"\1*\2", s)
    s = re.sub(r"([a-zA-Z\)])(\d)", r"\1*\2", s)
    s = re.sub(r"([xy\)])\(", r"\1*(", s)
    s = re.sub(r"\)([a-zA-Zxy])", r")*\1", s)
    return s


def _compilar(expr: str, etiqueta: str):
    codigo = compile(_normalizar(expr), f"<{etiqueta}>", "eval")
    safe = {name: getattr(math, name) for name in dir(math) if not name.startswith("__")}

    def fn(x: float, y: float) -> float:
        ctx = dict(safe)
        ctx["x"] = x
        ctx["y"] = y
        val = eval(codigo, {"__builtins__": {}}, ctx)
        if isinstance(val, complex):
            if abs(val.imag) > 1e-10:
                raise ValueError(f"{etiqueta} produjo valor no real.")
            val = val.real
        val = float(val)
        if not math.isfinite(val):
            raise ValueError(f"{etiqueta} produjo valor no finito.")
        return val

    return fn


# ── Euler Simple ──────────────────────────────────────────────────────────────
def _euler_simple(f, x0, y0, xf, h):
    filas = []
    x, y = x0, y0
    it = 1
    while x < xf - 1e-12:
        fxy = f(x, y)
        y_nuevo = y + h * fxy
        ea = abs((y_nuevo - y) / y_nuevo * 100) if y_nuevo != 0 else 0.0
        filas.append((it, round(x, 10), round(y, 10), round(fxy, 10), round(y_nuevo, 10), round(ea, 6)))
        x = round(x + h, 10)
        y = y_nuevo
        it += 1
        if it > MAX_ITER:
            break
    return filas


# ── Euler Modificado (Heun) ───────────────────────────────────────────────────
def _euler_modificado(f, x0, y0, xf, h):
    filas = []
    x, y = x0, y0
    it = 1
    while x < xf - 1e-12:
        k1 = f(x, y)
        y_pred = y + h * k1          # predictor
        k2 = f(x + h, y_pred)
        y_nuevo = y + h * (k1 + k2) / 2.0   # corrector
        ea = abs((y_nuevo - y) / y_nuevo * 100) if y_nuevo != 0 else 0.0
        filas.append((it, round(x, 10), round(y, 10), round(k1, 10), round(y_nuevo, 10), round(ea, 6)))
        x = round(x + h, 10)
        y = y_nuevo
        it += 1
        if it > MAX_ITER:
            break
    return filas


def _guardar(ejercicio: int, tipo: str, filas):
    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM metodo_euler WHERE ejercicio = %s AND tipo = %s", (ejercicio, tipo))
    for it, x, y, fxy, y_nuevo, ea in filas:
        cur.execute(
            """
            INSERT INTO metodo_euler (ejercicio, tipo, iteracion, x, y, fxy, y_nuevo, ea)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (ejercicio, tipo, it, x, y, fxy, y_nuevo, ea),
        )
    conn.commit()
    cur.close()
    conn.close()


def _graficar(ejercicio: int, tipo: str, filas, f_expr: str):
    xs  = [f[1] for f in filas]
    ys  = [f[2] for f in filas]
    yns = [f[4] for f in filas]

    nombre = "Euler Simple" if tipo == "SIM" else "Euler Modificado (Heun)"

    fig = go.Figure(
        data=[
            go.Scatter(x=xs, y=ys,  mode="lines+markers", name="y(x) inicio paso",
                       line=dict(color="#3b82f6")),
            go.Scatter(x=xs, y=yns, mode="lines+markers", name="y(x) fin paso",
                       line=dict(color="#f59e0b", dash="dot")),
        ],
        layout=go.Layout(
            title=f"Método de {nombre} — f(x,y) = {f_expr}",
            xaxis=dict(title="x", showgrid=True, gridcolor="lightgray"),
            yaxis=dict(title="y", showgrid=True, gridcolor="lightgray"),
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend=dict(orientation="h", y=-0.2),
        ),
    )
    os.makedirs("static/imagenes", exist_ok=True)
    ruta = f"static/imagenes/euler_{tipo.lower()}_{ejercicio}.html"
    pio.write_html(fig, file=ruta, auto_open=False)
    return "/" + ruta


def _ejecutar(tipo: str):
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        f_expr = _campo_texto("funcion", "f(x,y)")
        x0 = _campo_float("x0", "x0")
        y0 = _campo_float("y0", "y0")
        xf = _campo_float("xf", "xf (límite superior)")
        h  = _campo_float("h",  "h (tamaño de paso)")

        if h <= 0:
            raise ValueError("h debe ser mayor que 0.")
        if xf <= x0:
            raise ValueError("xf debe ser mayor que x0.")
        if h > (xf - x0):
            raise ValueError("h no puede ser mayor que el intervalo [x0, xf].")

        f = _compilar(f_expr, "f(x,y)")

        filas = _euler_simple(f, x0, y0, xf, h) if tipo == "SIM" else _euler_modificado(f, x0, y0, xf, h)
        _guardar(ejercicio, tipo, filas)

        imagen = ""
        try:
            imagen = _graficar(ejercicio, tipo, filas, f_expr)
        except Exception:
            imagen = ""

        nombre = "Simple" if tipo == "SIM" else "Modificado (Heun)"
        return jsonify({"mensaje": f"Euler {nombre} guardado correctamente.", "imagen": imagen})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Error interno: {str(e)}"}), 500


@euler_bp.route("/euler-simple", methods=["POST"])
def euler_simple():
    return _ejecutar("SIM")


@euler_bp.route("/euler-modificado", methods=["POST"])
def euler_modificado():
    return _ejecutar("MOD")


@euler_bp.route("/resultados-euler/<tipo>")
def resultados_euler(tipo):
    try:
        _asegurar_tabla()
        tipo_u = (tipo or "").strip().upper()
        if tipo_u not in ("SIM", "MOD"):
            return jsonify({"error": "Tipo inválido. Use SIM o MOD."}), 400
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ejercicio, iteracion, x, y, fxy, y_nuevo, ea
            FROM metodo_euler
            WHERE tipo = %s
            ORDER BY ejercicio ASC, iteracion ASC
            """,
            (tipo_u,),
        )
        filas = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@euler_bp.route("/buscar_ejercicio_euler/<tipo>/<int:ejercicio>", methods=["GET"])
def buscar_ejercicio_euler(tipo, ejercicio):
    try:
        _asegurar_tabla()
        tipo_u = (tipo or "").strip().upper()
        if tipo_u not in ("SIM", "MOD"):
            return jsonify({"error": "Tipo inválido."}), 400
        conn = _db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ejercicio, iteracion, x, y, fxy, y_nuevo, ea
            FROM metodo_euler
            WHERE tipo = %s AND ejercicio = %s
            ORDER BY iteracion ASC
            """,
            (tipo_u, ejercicio),
        )
        filas = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@euler_bp.route("/eliminar-euler/<tipo>/<int:ejercicio>", methods=["DELETE"])
def eliminar_euler(tipo, ejercicio):
    try:
        _asegurar_tabla()
        tipo_u = (tipo or "").strip().upper()
        if tipo_u not in ("SIM", "MOD"):
            return jsonify({"error": "Tipo inválido."}), 400
        conn = _db()
        cur = conn.cursor()
        cur.execute("DELETE FROM metodo_euler WHERE tipo = %s AND ejercicio = %s", (tipo_u, ejercicio))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"mensaje": f"Registros del ejercicio #{ejercicio} eliminados."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@euler_bp.route("/actualizar-euler/<tipo>", methods=["POST"])
def actualizar_euler(tipo):
    try:
        _asegurar_tabla()
        tipo_u = (tipo or "").strip().upper()
        if tipo_u not in ("SIM", "MOD"):
            return jsonify({"error": "Tipo inválido."}), 400
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM metodo_euler WHERE tipo = %s AND ejercicio = %s", (tipo_u, ejercicio))
        existe = cur.fetchone()[0] > 0
        cur.close()
        conn.close()
        if not existe:
            return jsonify({"error": f"No existe el ejercicio #{ejercicio}. Primero use Calcular."}), 404
        request.form = request.form.copy()
        request.form["ejercicio"] = str(ejercicio)
        return _ejecutar(tipo_u)
    except ValueError:
        return jsonify({"error": "Ejercicio debe ser un número entero válido."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
