from flask import Blueprint, request, jsonify
import math
import re
import os
import mysql.connector
import plotly.graph_objs as go
import plotly.io as pio
import numpy as np


muller_bp = Blueprint("muller", __name__)
MAX_ITER = 100


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
        CREATE TABLE IF NOT EXISTS metodo_muller (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ejercicio INT NOT NULL,
            iteracion INT NOT NULL,
            x0 DOUBLE,
            x1 DOUBLE,
            x2 DOUBLE,
            x3 DOUBLE,
            fx3 DOUBLE,
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
    s = re.sub(r"(\d)([a-zA-Z\(])", r"\1*\2", s)
    s = re.sub(r"([a-zA-Z\)])(\d)", r"\1*\2", s)
    s = re.sub(r"([x\)])\(", r"\1*(", s)
    s = re.sub(r"\)([a-zA-Zx])", r")*\1", s)
    return s


def _compilar(expr: str, etiqueta: str):
    codigo = compile(_normalizar(expr), f"<{etiqueta}>", "eval")
    safe = {name: getattr(math, name) for name in dir(math) if not name.startswith("__")}

    def f(x: float) -> float:
        ctx = dict(safe)
        ctx["x"] = x
        val = eval(codigo, {"__builtins__": {}}, ctx)
        if isinstance(val, complex):
            if abs(val.imag) > 1e-10:
                raise ValueError(f"{etiqueta} produjo un valor no real.")
            val = val.real
        val = float(val)
        if not math.isfinite(val):
            raise ValueError(f"{etiqueta} produjo un valor no finito.")
        return val

    return f


def _iterar(ejercicio: int, f_expr: str, x0: float, x1: float, x2: float, es: float):
    f = _compilar(f_expr, "f(x)")
    filas = []
    a0, a1, a2 = x0, x1, x2

    for it in range(1, MAX_ITER + 1):
        f0 = f(a0)
        f1 = f(a1)
        f2 = f(a2)

        h0 = a1 - a0
        h1 = a2 - a1
        if abs(h0) < 1e-14 or abs(h1) < 1e-14:
            raise ValueError("Puntos demasiado cercanos para continuar (h≈0).")

        d0 = (f1 - f0) / h0
        d1 = (f2 - f1) / h1
        a = (d1 - d0) / (h1 + h0)
        b = a * h1 + d1
        c = f2

        disc = b * b - 4 * a * c
        if disc < 0:
            raise ValueError("Discriminante negativo (raíces complejas) en esta iteración.")
        sqrt_disc = math.sqrt(disc)
        denom1 = b + sqrt_disc
        denom2 = b - sqrt_disc
        denom = denom1 if abs(denom1) > abs(denom2) else denom2
        if abs(denom) < 1e-14:
            raise ValueError("Denominador cercano a cero en Müller.")

        dx = -2 * c / denom
        x3 = a2 + dx
        ea = 0.0 if it == 1 or x3 == 0 else abs(dx / x3) * 100.0
        fx3 = f(x3)
        filas.append((ejercicio, it, a0, a1, a2, x3, fx3, round(ea, 4)))

        if it > 1 and ea < es:
            break
        a0, a1, a2 = a1, a2, x3

    return filas


def _guardar(ejercicio: int, filas):
    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM metodo_muller WHERE ejercicio = %s", (ejercicio,))
    for fila in filas:
        cur.execute(
            """
            INSERT INTO metodo_muller (ejercicio, iteracion, x0, x1, x2, x3, fx3, ea)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            fila,
        )
    conn.commit()
    cur.close()
    conn.close()


def _graficar(ejercicio: int, f_expr: str, filas):
    f = _compilar(f_expr, "f(x)")
    x0 = float(filas[0][2])
    xs = np.linspace(x0 - 6.0, x0 + 6.0, 700)
    x_plot, y_plot = [], []
    for x in xs:
        try:
            y = f(float(x))
        except Exception:
            continue
        x_plot.append(float(x))
        y_plot.append(float(y))
    if len(x_plot) < 2:
        raise ValueError("No se pudo generar la gráfica para esta función en el rango actual.")

    xr = float(filas[-1][5])
    fig = go.Figure(
        data=[
            go.Scatter(x=x_plot, y=y_plot, mode="lines", name="f(x)", line=dict(color="#3b82f6")),
            go.Scatter(x=[xr], y=[0], mode="markers", name="aprox. raíz", marker=dict(size=10, color="#10b981")),
        ],
        layout=go.Layout(
            title="Gráfica del Método de Müller",
            xaxis=dict(title="x", showgrid=True, gridcolor="lightgray"),
            yaxis=dict(title="f(x)", showgrid=True, gridcolor="lightgray"),
            plot_bgcolor="white",
            paper_bgcolor="white",
        ),
    )
    os.makedirs("static/imagenes", exist_ok=True)
    ruta = f"static/imagenes/muller_{ejercicio}.html"
    pio.write_html(fig, file=ruta, auto_open=False)
    return "/" + ruta


@muller_bp.route("/muller", methods=["POST"])
def ejecutar_muller():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        f_expr = _campo_texto("funcion", "la función f(x)")
        x0 = _campo_float("x0", "x0")
        x1 = _campo_float("x1", "x1")
        x2 = _campo_float("x2", "x2")
        es = _campo_float("es", "Es%")
        if es <= 0:
            raise ValueError("Es% debe ser mayor que 0.")

        filas = _iterar(ejercicio, f_expr, x0, x1, x2, es)
        _guardar(ejercicio, filas)

        imagen = ""
        try:
            imagen = _graficar(ejercicio, f_expr, filas)
        except Exception:
            imagen = ""
        return jsonify({"mensaje": "Müller guardado correctamente.", "imagen": imagen})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@muller_bp.route("/resultados-muller")
def resultados_muller():
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ejercicio, iteracion, x0, x1, x2, x3, fx3, ea
            FROM metodo_muller
            ORDER BY ejercicio ASC, iteracion ASC
            """
        )
        filas = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@muller_bp.route("/buscar_ejercicio_muller/<int:ejercicio>", methods=["GET"])
def buscar_ejercicio_muller(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ejercicio, iteracion, x0, x1, x2, x3, fx3, ea
            FROM metodo_muller
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


@muller_bp.route("/eliminar-muller/<int:ejercicio>", methods=["DELETE"])
def eliminar_muller(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute("DELETE FROM metodo_muller WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"mensaje": f"Registros del ejercicio #{ejercicio} eliminados correctamente."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@muller_bp.route("/actualizar-muller", methods=["POST"])
def actualizar_muller():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM metodo_muller WHERE ejercicio = %s", (ejercicio,))
        existe = cur.fetchone()[0] > 0
        cur.close()
        conn.close()
        if not existe:
            return jsonify({"error": f"No existe el ejercicio #{ejercicio}. Primero use Calcular."}), 404
        request.form = request.form.copy()
        request.form["ejercicio"] = str(ejercicio)
        return ejecutar_muller()
    except ValueError:
        return jsonify({"error": "Ejercicio debe ser un número entero válido."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

