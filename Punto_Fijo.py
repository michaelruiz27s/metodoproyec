from flask import Blueprint, request, jsonify
import math
import re
import os
import mysql.connector
import plotly.graph_objs as go
import plotly.io as pio
import numpy as np


punto_fijo_bp = Blueprint("punto_fijo", __name__)
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
        CREATE TABLE IF NOT EXISTS metodo_punto_fijo (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ejercicio INT NOT NULL,
            iteracion INT NOT NULL,
            xi DOUBLE,
            gxi DOUBLE,
            ea DOUBLE
        )
        """
    )
    conn.commit()
    cur.close()
    conn.close()


def _campo_texto(nombre, etiqueta):
    val = (request.form.get(nombre) or "").strip()
    if not val:
        raise ValueError(f"Complete {etiqueta}.")
    return val


def _campo_float(nombre, etiqueta):
    raw = _campo_texto(nombre, etiqueta)
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{etiqueta} debe ser un número válido.") from exc


def _normalizar(expr):
    s = expr.lower().replace(" ", "")
    s = s.replace("raiz", "sqrt")
    s = s.replace("sen", "sin")
    s = s.replace("^", "**")
    s = s.replace("ln", "log")
    s = re.sub(r"(\d)([a-zA-Z\(])", r"\1*\2", s)
    s = re.sub(r"([a-zA-Z\)])(\d)", r"\1*\2", s)
    s = re.sub(r"([x\)])\(", r"\1*(", s)
    s = re.sub(r"\)([a-zA-Zx])", r")*\1", s)
    return s


def _compilar_g(expr):
    codigo = compile(_normalizar(expr), "<g(x)>", "eval")
    safe = {name: getattr(math, name) for name in dir(math) if not name.startswith("__")}

    def g(x):
        ctx = dict(safe)
        ctx["x"] = x
        return eval(codigo, {"__builtins__": {}}, ctx)

    return g


def _real_finito(valor):
    if isinstance(valor, complex):
        if abs(valor.imag) > 1e-10:
            return None
        valor = valor.real
    if not isinstance(valor, (int, float)) or not math.isfinite(float(valor)):
        return None
    return float(valor)


def _iterar_punto_fijo(g, xi, es):
    filas = []
    actual = xi
    for it in range(1, MAX_ITER + 1):
        siguiente = _real_finito(g(actual))
        if siguiente is None:
            raise ValueError("La iteración produjo un valor no real o no finito.")
        ea = 0.0 if it == 1 or siguiente == 0 else abs((siguiente - actual) / siguiente) * 100
        filas.append((it, actual, siguiente, round(ea, 4)))
        if it > 1 and ea < es:
            break
        actual = siguiente
    return filas


def _guardar_resultados(ejercicio, filas):
    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM metodo_punto_fijo WHERE ejercicio = %s", (ejercicio,))
    for it, xi, gxi, ea in filas:
        cur.execute(
            """
            INSERT INTO metodo_punto_fijo (ejercicio, iteracion, xi, gxi, ea)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (ejercicio, it, xi, gxi, ea),
        )
    conn.commit()
    cur.close()
    conn.close()


def _graficar(ejercicio, g, filas):
    xi0 = filas[0][1]
    xs = np.linspace(xi0 - 4.0, xi0 + 4.0, 500)
    gx, gy = [], []
    for x in xs:
        y = _real_finito(g(float(x)))
        if y is None:
            continue
        gx.append(float(x))
        gy.append(y)
    if len(gx) < 2:
        raise ValueError("No hay suficientes puntos reales para graficar g(x).")

    ultimo = filas[-1]
    fig = go.Figure(
        data=[
            go.Scatter(x=gx, y=gy, mode="lines", name="g(x)", line=dict(color="#3b82f6")),
            go.Scatter(x=gx, y=gx, mode="lines", name="y = x", line=dict(color="#f59e0b", dash="dash")),
            go.Scatter(
                x=[ultimo[1], ultimo[2]],
                y=[ultimo[1], ultimo[2]],
                mode="markers",
                name=f"Xi final ~ {ultimo[2]:.6f}",
                marker=dict(size=9, color="#10b981"),
            ),
        ],
        layout=go.Layout(
            title="Gráfica del Método de Punto Fijo",
            xaxis=dict(title="x", showgrid=True, gridcolor="lightgray"),
            yaxis=dict(title="y", showgrid=True, gridcolor="lightgray"),
            plot_bgcolor="white",
            paper_bgcolor="white",
        ),
    )

    os.makedirs("static/imagenes", exist_ok=True)
    ruta = f"static/imagenes/punto_fijo_{ejercicio}.html"
    pio.write_html(fig, file=ruta, auto_open=False)
    return "/" + ruta


@punto_fijo_bp.route("/punto-fijo", methods=["POST"])
def ejecutar_punto_fijo():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        g_expr = _campo_texto("funcion", "la función g(x)")
        xi = _campo_float("xi", "Xi")
        es = _campo_float("es", "Es%")
        if es <= 0:
            raise ValueError("Es% debe ser mayor que 0.")

        g = _compilar_g(g_expr)
        filas = _iterar_punto_fijo(g, xi, es)
        _guardar_resultados(ejercicio, filas)

        imagen = ""
        try:
            imagen = _graficar(ejercicio, g, filas)
        except Exception:
            imagen = ""

        return jsonify({"mensaje": "Cálculo de punto fijo guardado correctamente.", "imagen": imagen})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@punto_fijo_bp.route("/resultados-punto-fijo")
def resultados_punto_fijo():
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ejercicio, iteracion, xi, gxi, ea
            FROM metodo_punto_fijo
            ORDER BY ejercicio ASC, iteracion ASC
            """
        )
        filas = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@punto_fijo_bp.route("/buscar_ejercicio_punto_fijo/<int:ejercicio>", methods=["GET"])
def buscar_ejercicio_punto_fijo(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ejercicio, iteracion, xi, gxi, ea
            FROM metodo_punto_fijo
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


@punto_fijo_bp.route("/eliminar-punto-fijo/<int:ejercicio>", methods=["DELETE"])
def eliminar_punto_fijo(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute("DELETE FROM metodo_punto_fijo WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"mensaje": f"Registros del ejercicio #{ejercicio} eliminados correctamente."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@punto_fijo_bp.route("/actualizar-punto-fijo", methods=["POST"])
def actualizar_punto_fijo():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM metodo_punto_fijo WHERE ejercicio = %s", (ejercicio,))
        existe = cur.fetchone()[0] > 0
        cur.close()
        conn.close()
        if not existe:
            return jsonify({"error": f"No existe el ejercicio #{ejercicio}. Primero use Calcular."}), 404
        request.form = request.form.copy()
        request.form["ejercicio"] = str(ejercicio)
        return ejecutar_punto_fijo()
    except ValueError:
        return jsonify({"error": "Ejercicio debe ser un número entero válido."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
