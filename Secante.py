from flask import Blueprint, request, jsonify
import math
import re
import os
import mysql.connector
import plotly.graph_objs as go
import plotly.io as pio
import numpy as np


secante_bp = Blueprint("secante", __name__)
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
        CREATE TABLE IF NOT EXISTS metodo_secante (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ejercicio INT NOT NULL,
            iteracion INT NOT NULL,
            xi_1 DOUBLE,
            xi DOUBLE,
            fxi_1 DOUBLE,
            fxi DOUBLE,
            xi_t DOUBLE,
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


def _iterar(ejercicio: int, f_expr: str, xi_1: float, xi: float, es: float):
    f = _compilar(f_expr, "f(x)")
    filas = []
    actual_1 = xi_1
    actual = xi

    for it in range(1, MAX_ITER + 1):
        f1 = f(actual_1)
        f0 = f(actual)
        denom = (f0 - f1)
        if abs(denom) < 1e-14:
            raise ValueError("División por cero: f(xi) - f(xi-1) es muy pequeño.")
        xt = actual - f0 * (actual - actual_1) / denom
        ea = 0.0 if it == 1 or xt == 0 else abs((xt - actual) / xt) * 100.0
        filas.append((ejercicio, it, actual_1, actual, f1, f0, xt, round(ea, 4)))
        if it > 1 and ea < es:
            break
        actual_1, actual = actual, xt
    return filas


def _guardar(ejercicio: int, filas):
    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM metodo_secante WHERE ejercicio = %s", (ejercicio,))
    for fila in filas:
        cur.execute(
            """
            INSERT INTO metodo_secante (ejercicio, iteracion, xi_1, xi, fxi_1, fxi, xi_t, ea)
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

    xr = float(filas[-1][6])
    fig = go.Figure(
        data=[
            go.Scatter(x=x_plot, y=y_plot, mode="lines", name="f(x)", line=dict(color="#3b82f6")),
            go.Scatter(x=[xr], y=[0], mode="markers", name="aprox. raíz", marker=dict(size=10, color="#10b981")),
        ],
        layout=go.Layout(
            title="Gráfica del Método de la Secante",
            xaxis=dict(title="x", showgrid=True, gridcolor="lightgray"),
            yaxis=dict(title="f(x)", showgrid=True, gridcolor="lightgray"),
            plot_bgcolor="white",
            paper_bgcolor="white",
        ),
    )
    os.makedirs("static/imagenes", exist_ok=True)
    ruta = f"static/imagenes/secante_{ejercicio}.html"
    pio.write_html(fig, file=ruta, auto_open=False)
    return "/" + ruta


@secante_bp.route("/secante", methods=["POST"])
def ejecutar_secante():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        f_expr = _campo_texto("funcion", "la función f(x)")
        xi_1 = _campo_float("xi_1", "Xi-1")
        xi = _campo_float("xi", "Xi")
        es = _campo_float("es", "Es%")
        if es <= 0:
            raise ValueError("Es% debe ser mayor que 0.")

        filas = _iterar(ejercicio, f_expr, xi_1, xi, es)
        _guardar(ejercicio, filas)

        imagen = ""
        try:
            imagen = _graficar(ejercicio, f_expr, filas)
        except Exception:
            imagen = ""
        return jsonify({"mensaje": "Secante guardado correctamente.", "imagen": imagen})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@secante_bp.route("/resultados-secante")
def resultados_secante():
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ejercicio, iteracion, xi_1, xi, fxi_1, fxi, xi_t, ea
            FROM metodo_secante
            ORDER BY ejercicio ASC, iteracion ASC
            """
        )
        filas = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@secante_bp.route("/buscar_ejercicio_secante/<int:ejercicio>", methods=["GET"])
def buscar_ejercicio_secante(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ejercicio, iteracion, xi_1, xi, fxi_1, fxi, xi_t, ea
            FROM metodo_secante
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


@secante_bp.route("/eliminar-secante/<int:ejercicio>", methods=["DELETE"])
def eliminar_secante(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute("DELETE FROM metodo_secante WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"mensaje": f"Registros del ejercicio #{ejercicio} eliminados correctamente."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@secante_bp.route("/actualizar-secante", methods=["POST"])
def actualizar_secante():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM metodo_secante WHERE ejercicio = %s", (ejercicio,))
        existe = cur.fetchone()[0] > 0
        cur.close()
        conn.close()
        if not existe:
            return jsonify({"error": f"No existe el ejercicio #{ejercicio}. Primero use Calcular."}), 404
        request.form = request.form.copy()
        request.form["ejercicio"] = str(ejercicio)
        return ejecutar_secante()
    except ValueError:
        return jsonify({"error": "Ejercicio debe ser un número entero válido."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

