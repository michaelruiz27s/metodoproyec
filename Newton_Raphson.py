from flask import Blueprint, request, jsonify
import math
import re
import os
import mysql.connector
import plotly.graph_objs as go
import plotly.io as pio
import numpy as np


newton_bp = Blueprint("newton", __name__)
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
        CREATE TABLE IF NOT EXISTS metodo_newton_raphson (
            ejercicio INT NOT NULL,
            tipo VARCHAR(16) NOT NULL,
            iteracion INT NOT NULL,
            xi DOUBLE,
            fxi DOUBLE,
            dfxi DOUBLE,
            xi1 DOUBLE,
            ea DOUBLE
        )
        """
    )
    # Si la tabla ya existía con esquema antiguo, añade columnas faltantes.
    cur.execute("SHOW COLUMNS FROM metodo_newton_raphson")
    cols = {row[0].lower() for row in cur.fetchall()}
    if "tipo" not in cols:
        cur.execute("ALTER TABLE metodo_newton_raphson ADD COLUMN tipo VARCHAR(16) NOT NULL DEFAULT 'CLA' AFTER ejercicio")
        cur.execute("UPDATE metodo_newton_raphson SET tipo = 'CLA' WHERE tipo IS NULL OR tipo = ''")
    if "dfxi" not in cols:
        cur.execute("ALTER TABLE metodo_newton_raphson ADD COLUMN dfxi DOUBLE NULL")
    if "xi1" not in cols:
        cur.execute("ALTER TABLE metodo_newton_raphson ADD COLUMN xi1 DOUBLE NULL")
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
    # Normaliza signos comunes copiados desde Word/PDF (unicode)
    s = s.replace("−", "-")  # U+2212 minus
    s = s.replace("–", "-")  # en dash
    s = s.replace("—", "-")  # em dash
    s = s.replace("×", "*")
    s = s.replace("·", "*")
    s = s.replace(" ", "")
    s = s.replace("raiz", "sqrt")
    s = s.replace("sen", "sin")
    s = s.replace("^", "**")
    s = s.replace("ln", "log")
    # multiplicación implícita: 4x, 2(x+1), x(x-1)
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
                raise ValueError(f"{etiqueta} produjo un valor no real.")
            val = val.real
        val = float(val)
        if not math.isfinite(val):
            raise ValueError(f"{etiqueta} produjo un valor no finito.")
        return val

    return fn


def _derivada_central(f, x: float) -> float:
    # paso relativo robusto
    h = max(1e-6, abs(x) * 1e-4)
    return (f(x + h) - f(x - h)) / (2.0 * h)


def _segunda_derivada_central(f, x: float) -> float:
    h = max(1e-5, abs(x) * 1e-3)
    return (f(x + h) - 2.0 * f(x) + f(x - h)) / (h * h)


def _iterar(tipo: str, ejercicio: int, f_expr: str, xi: float, es: float, df_expr: str | None):
    f = _compilar(f_expr, "f(x)")
    df = _compilar(df_expr, "f'(x)") if df_expr else None

    filas = []
    actual = xi

    for it in range(1, MAX_ITER + 1):
        fxi = f(actual)

        if tipo == "NUM":
            dfxi = _derivada_central(f, actual)
        else:
            if not df:
                raise ValueError("Para Newton clásico/modificado, indique f'(x).")
            dfxi = df(actual)

        if abs(dfxi) < 1e-14:
            raise ValueError("Derivada cercana a cero: el método no puede continuar.")

        if tipo == "MOD":
            # Newton modificado para raíces múltiples (forma estándar usando f'')
            # x_{k+1} = x_k - f f' / ( (f')^2 - f f'' )
            dd = _segunda_derivada_central(f, actual)
            denom = (dfxi * dfxi) - (fxi * dd)
            if abs(denom) < 1e-14:
                raise ValueError("Denominador cercano a cero en Newton modificado.")
            siguiente = actual - (fxi * dfxi) / denom
        else:
            siguiente = actual - (fxi / dfxi)

        ea = 0.0 if it == 1 or siguiente == 0 else abs((siguiente - actual) / siguiente) * 100.0
        filas.append((ejercicio, tipo, it, actual, fxi, dfxi, siguiente, round(ea, 4)))

        if it > 1 and ea < es:
            break
        actual = siguiente

    return filas


def _guardar(ejercicio: int, tipo: str, filas):
    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM metodo_newton_raphson WHERE ejercicio = %s AND tipo = %s", (ejercicio, tipo))
    for fila in filas:
        cur.execute(
            """
            INSERT INTO metodo_newton_raphson (ejercicio, tipo, iteracion, xi, fxi, dfxi, xi1, ea)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            fila,
        )
    conn.commit()
    cur.close()
    conn.close()


def _graficar(ejercicio: int, tipo: str, f_expr: str, filas):
    f = _compilar(f_expr, "f(x)")
    x0 = float(filas[0][3])
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

    ultimo = filas[-1]
    xr = float(ultimo[6])
    fig = go.Figure(
        data=[
            go.Scatter(x=x_plot, y=y_plot, mode="lines", name="f(x)", line=dict(color="#3b82f6")),
            go.Scatter(x=[xr], y=[0], mode="markers", name="aprox. raíz", marker=dict(size=10, color="#10b981")),
        ],
        layout=go.Layout(
            title="Gráfica del Método de Newton-Raphson",
            xaxis=dict(title="x", showgrid=True, gridcolor="lightgray"),
            yaxis=dict(title="f(x)", showgrid=True, gridcolor="lightgray"),
            plot_bgcolor="white",
            paper_bgcolor="white",
        ),
    )
    os.makedirs("static/imagenes", exist_ok=True)
    ruta = f"static/imagenes/newton_{tipo.lower()}_{ejercicio}.html"
    pio.write_html(fig, file=ruta, auto_open=False)
    return "/" + ruta


def _ejecutar(tipo: str):
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        f_expr = _campo_texto("funcion", "la función f(x)")
        xi = _campo_float("xi", "Xi")
        es = _campo_float("es", "Es%")
        if es <= 0:
            raise ValueError("Es% debe ser mayor que 0.")

        df_expr = (request.form.get("derivada") or "").strip()
        df_expr = df_expr if df_expr else None

        filas = _iterar(tipo, ejercicio, f_expr, xi, es, df_expr)
        _guardar(ejercicio, tipo, filas)

        imagen = ""
        try:
            imagen = _graficar(ejercicio, tipo, f_expr, filas)
        except Exception:
            imagen = ""

        nombre = {"CLA": "clásico", "MOD": "modificado", "NUM": "con derivada numérica"}[tipo]
        return jsonify({"mensaje": f"Newton-Raphson ({nombre}) guardado correctamente.", "imagen": imagen})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        # En debug, ayuda a diagnosticar errores de cálculo/parseo.
        print("Error Newton-Raphson:", repr(e))
        return jsonify({"error": str(e)}), 500


@newton_bp.route("/newton-clasico", methods=["POST"])
def newton_clasico():
    return _ejecutar("CLA")


@newton_bp.route("/newton-modificado", methods=["POST"])
def newton_modificado():
    return _ejecutar("MOD")


@newton_bp.route("/newton-numerico", methods=["POST"])
def newton_numerico():
    return _ejecutar("NUM")


@newton_bp.route("/resultados-newton/<tipo>")
def resultados_newton(tipo):
    try:
        _asegurar_tabla()
        tipo_u = (tipo or "").strip().upper()
        if tipo_u not in ("CLA", "MOD", "NUM"):
            return jsonify({"error": "Tipo inválido."}), 400
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ejercicio, iteracion, xi, fxi, dfxi, xi1, ea
            FROM metodo_newton_raphson
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


@newton_bp.route("/buscar_ejercicio_newton/<tipo>/<int:ejercicio>", methods=["GET"])
def buscar_ejercicio_newton(tipo, ejercicio):
    try:
        _asegurar_tabla()
        tipo_u = (tipo or "").strip().upper()
        if tipo_u not in ("CLA", "MOD", "NUM"):
            return jsonify({"error": "Tipo inválido."}), 400
        conn = _db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ejercicio, iteracion, xi, fxi, dfxi, xi1, ea
            FROM metodo_newton_raphson
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


@newton_bp.route("/eliminar-newton/<tipo>/<int:ejercicio>", methods=["DELETE"])
def eliminar_newton(tipo, ejercicio):
    try:
        _asegurar_tabla()
        tipo_u = (tipo or "").strip().upper()
        if tipo_u not in ("CLA", "MOD", "NUM"):
            return jsonify({"error": "Tipo inválido."}), 400
        conn = _db()
        cur = conn.cursor()
        cur.execute("DELETE FROM metodo_newton_raphson WHERE tipo = %s AND ejercicio = %s", (tipo_u, ejercicio))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"mensaje": f"Registros del ejercicio #{ejercicio} eliminados correctamente."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@newton_bp.route("/actualizar-newton/<tipo>", methods=["POST"])
def actualizar_newton(tipo):
    try:
        _asegurar_tabla()
        tipo_u = (tipo or "").strip().upper()
        if tipo_u not in ("CLA", "MOD", "NUM"):
            return jsonify({"error": "Tipo inválido."}), 400
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM metodo_newton_raphson WHERE tipo = %s AND ejercicio = %s",
            (tipo_u, ejercicio),
        )
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
