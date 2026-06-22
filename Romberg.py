from flask import Blueprint, request, jsonify
import math
import re
import os
from database import get_connection
import plotly.graph_objs as go
import plotly.io as pio
import numpy as np


romberg_bp = Blueprint("romberg", __name__)


def _db():
    return get_connection()


def _asegurar_tabla():
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS metodo_romberg (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ejercicio INT NOT NULL,
            nivel INT NOT NULL,
            columna INT NOT NULL,
            valor DOUBLE,
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


def _campo_int(nombre, etiqueta):
    raw = _campo_texto(nombre, etiqueta)
    try:
        v = int(raw)
        if v < 1:
            raise ValueError()
        return v
    except ValueError as exc:
        raise ValueError(f"{etiqueta} debe ser un entero positivo.") from exc


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

    def fn(x: float) -> float:
        ctx = dict(safe)
        ctx["x"] = x
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


def _trapecio(f, a, b, n):
    """Regla del trapecio compuesta con n subintervalos."""
    h = (b - a) / n
    total = f(a) + f(b)
    for i in range(1, n):
        total += 2.0 * f(a + i * h)
    return total * h / 2.0


def _romberg(f, a, b, max_nivel):
    """
    Construye la tabla de Romberg.
    R[i][j] = resultado en nivel i (número de segmentos = 2^i), columna j de Richardson.
    Retorna la tabla completa y las filas para guardar en BD.
    """
    n_max = max_nivel + 1
    R = [[0.0] * n_max for _ in range(n_max)]

    # Primera columna: trapecio compuesto con 2^i segmentos
    for i in range(n_max):
        n = 2 ** i
        R[i][0] = _trapecio(f, a, b, n)

    # Extrapolaciones de Richardson
    for j in range(1, n_max):
        for i in range(j, n_max):
            factor = 4 ** j
            R[i][j] = (factor * R[i][j - 1] - R[i - 1][j - 1]) / (factor - 1)

    # Armar filas: (nivel, columna, valor, ea)
    filas = []
    for i in range(n_max):
        for j in range(i + 1):
            val = R[i][j]
            # Ea respecto al valor anterior en la misma columna
            if i > 0 and j <= i - 1:
                prev = R[i - 1][j] if j < i else R[i][j - 1]
                ea = abs((val - prev) / val * 100) if val != 0 else 0.0
            else:
                ea = 0.0
            filas.append((i + 1, j + 1, round(val, 10), round(ea, 6)))

    return R, filas


def _guardar(ejercicio: int, filas):
    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM metodo_romberg WHERE ejercicio = %s", (ejercicio,))
    for nivel, columna, valor, ea in filas:
        cur.execute(
            """
            INSERT INTO metodo_romberg (ejercicio, nivel, columna, valor, ea)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (ejercicio, nivel, columna, valor, ea),
        )
    conn.commit()
    cur.close()
    conn.close()


def _graficar(ejercicio: int, R, f_expr: str, a: float, b: float, f):
    n_max = len(R)

    # Gráfica 1: función en el intervalo
    xs = np.linspace(a, b, 500)
    ys_plot, xs_plot = [], []
    for xv in xs:
        try:
            yv = f(float(xv))
            xs_plot.append(float(xv))
            ys_plot.append(yv)
        except Exception:
            continue

    # Gráfica 2: convergencia de la diagonal (R[i][i])
    niveles  = list(range(1, n_max + 1))
    diagonal = [R[i][i] for i in range(n_max)]

    fig = go.Figure()

    # Área bajo la curva
    fig.add_trace(go.Scatter(
        x=xs_plot, y=ys_plot,
        mode="lines",
        name=f"f(x) = {f_expr}",
        line=dict(color="#3b82f6", width=2),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.1)",
    ))

    fig2 = go.Figure(
        data=[
            go.Scatter(
                x=niveles, y=diagonal,
                mode="lines+markers",
                name="R[i][i] — mejor estimación por nivel",
                line=dict(color="#f59e0b", width=2),
                marker=dict(size=8, color="#f59e0b"),
            )
        ],
        layout=go.Layout(
            title="Convergencia de la diagonal de Romberg",
            xaxis=dict(title="Nivel", showgrid=True, gridcolor="lightgray", dtick=1),
            yaxis=dict(title="Valor integral", showgrid=True, gridcolor="lightgray"),
            plot_bgcolor="white",
            paper_bgcolor="white",
        ),
    )

    fig.update_layout(
        title=f"Integración de f(x) = {f_expr} en [{a}, {b}]",
        xaxis=dict(title="x", showgrid=True, gridcolor="lightgray"),
        yaxis=dict(title="f(x)", showgrid=True, gridcolor="lightgray"),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    os.makedirs("static/imagenes", exist_ok=True)

    ruta_func = f"static/imagenes/romberg_func_{ejercicio}.html"
    ruta_conv = f"static/imagenes/romberg_conv_{ejercicio}.html"
    pio.write_html(fig,  file=ruta_func, auto_open=False)
    pio.write_html(fig2, file=ruta_conv, auto_open=False)

    return "/" + ruta_func, "/" + ruta_conv


@romberg_bp.route("/romberg", methods=["POST"])
def ejecutar_romberg():
    try:
        _asegurar_tabla()
        ejercicio  = int(_campo_texto("ejercicio", "el número de ejercicio"))
        f_expr     = _campo_texto("funcion", "f(x)")
        a          = _campo_float("a", "límite inferior a")
        b          = _campo_float("b", "límite superior b")
        max_nivel  = _campo_int("niveles", "número de niveles")

        if b <= a:
            raise ValueError("El límite superior b debe ser mayor que a.")
        if max_nivel > 10:
            raise ValueError("Máximo 10 niveles para evitar cálculos excesivos.")

        f = _compilar(f_expr, "f(x)")
        R, filas = _romberg(f, a, b, max_nivel)
        _guardar(ejercicio, filas)

        img_func, img_conv = "", ""
        try:
            img_func, img_conv = _graficar(ejercicio, R, f_expr, a, b, f)
        except Exception:
            pass

        resultado = R[max_nivel][max_nivel]
        return jsonify({
            "mensaje": f"Romberg guardado. Resultado: I ≈ {round(resultado, 10)}",
            "imagen_func": img_func,
            "imagen_conv": img_conv,
            "resultado": resultado,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Error interno: {str(e)}"}), 500


@romberg_bp.route("/resultados-romberg")
def resultados_romberg():
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ejercicio, nivel, columna, valor, ea
            FROM metodo_romberg
            ORDER BY ejercicio ASC, nivel ASC, columna ASC
            """
        )
        filas = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@romberg_bp.route("/buscar_ejercicio_romberg/<int:ejercicio>", methods=["GET"])
def buscar_ejercicio_romberg(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ejercicio, nivel, columna, valor, ea
            FROM metodo_romberg
            WHERE ejercicio = %s
            ORDER BY nivel ASC, columna ASC
            """,
            (ejercicio,),
        )
        filas = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@romberg_bp.route("/eliminar-romberg/<int:ejercicio>", methods=["DELETE"])
def eliminar_romberg(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute("DELETE FROM metodo_romberg WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"mensaje": f"Registros del ejercicio #{ejercicio} eliminados."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@romberg_bp.route("/actualizar-romberg", methods=["POST"])
def actualizar_romberg():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM metodo_romberg WHERE ejercicio = %s", (ejercicio,))
        existe = cur.fetchone()[0] > 0
        cur.close()
        conn.close()
        if not existe:
            return jsonify({"error": f"No existe el ejercicio #{ejercicio}. Primero use Calcular."}), 404
        request.form = request.form.copy()
        request.form["ejercicio"] = str(ejercicio)
        return ejecutar_romberg()
    except ValueError:
        return jsonify({"error": "Ejercicio debe ser un número entero válido."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
