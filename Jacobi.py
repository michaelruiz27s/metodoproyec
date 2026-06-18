from flask import Blueprint, request, jsonify
import os
import numpy as np
import plotly.graph_objs as go
import plotly.io as pio
from database import get_connection


jacobi_bp = Blueprint("jacobi", __name__)
MAX_ITER = 100
N = 3


def _db():
    return get_connection()


def _asegurar_tabla():
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS metodo_jacobi (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ejercicio INT NOT NULL,
            iteracion INT NOT NULL,
            x1 DOUBLE,
            x2 DOUBLE,
            x3 DOUBLE,
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


def _parse_matriz(texto):
    filas = [f.strip() for f in texto.replace("\n", ";").split(";") if f.strip()]
    if len(filas) != N:
        raise ValueError(f"La matriz debe tener {N} filas separadas por punto y coma (;).")
    matriz = []
    for i, fila in enumerate(filas, start=1):
        cols = [c.strip() for c in fila.split(",") if c.strip() != ""]
        if len(cols) != N:
            raise ValueError(f"La fila {i} debe tener {N} coeficientes separados por coma.")
        try:
            matriz.append([float(c) for c in cols])
        except ValueError as exc:
            raise ValueError(f"Coeficiente inválido en la fila {i}.") from exc
    return np.array(matriz, dtype=float)


def _parse_vector(texto, etiqueta):
    vals = [v.strip() for v in texto.split(",") if v.strip() != ""]
    if len(vals) != N:
        raise ValueError(f"{etiqueta} debe tener {N} valores separados por coma.")
    try:
        return np.array([float(v) for v in vals], dtype=float)
    except ValueError as exc:
        raise ValueError(f"{etiqueta} contiene un valor no numérico.") from exc


def _es_diagonalmente_dominante(A):
    for i in range(N):
        diag = abs(A[i, i])
        suma = sum(abs(A[i, j]) for j in range(N) if j != i)
        if diag <= suma:
            return False
    return True


def _calcular_ea(x_nuevo, x_anterior):
    ea_max = 0.0
    for i in range(N):
        if x_nuevo[i] != 0:
            ea_i = abs((x_nuevo[i] - x_anterior[i]) / x_nuevo[i]) * 100
        else:
            ea_i = abs(x_nuevo[i] - x_anterior[i]) * 100
        ea_max = max(ea_max, ea_i)
    return round(ea_max, 6)


def _iterar_jacobi(A, b, x0, es):
    x = x0.astype(float).copy()
    filas = []

    for it in range(1, MAX_ITER + 1):
        x_nuevo = x.copy()
        for i in range(N):
            if A[i, i] == 0:
                raise ValueError(f"El elemento diagonal a{i + 1}{i + 1} es cero; Jacobi no puede continuar.")
            suma = b[i]
            for j in range(N):
                if j != i:
                    suma -= A[i, j] * x[j]
            x_nuevo[i] = suma / A[i, i]

        ea = 0.0 if it == 1 else _calcular_ea(x_nuevo, x)
        filas.append((it, float(x_nuevo[0]), float(x_nuevo[1]), float(x_nuevo[2]), ea))

        if it > 1 and ea < es:
            break
        x = x_nuevo.copy()

    return filas


def _guardar(ejercicio, filas):
    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM metodo_jacobi WHERE ejercicio = %s", (ejercicio,))
    for it, x1, x2, x3, ea in filas:
        cur.execute(
            """
            INSERT INTO metodo_jacobi (ejercicio, iteracion, x1, x2, x3, ea)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (ejercicio, it, x1, x2, x3, ea),
        )
    conn.commit()
    cur.close()
    conn.close()


def _graficar(ejercicio, filas):
    its = [f[0] for f in filas]
    x1s = [f[1] for f in filas]
    x2s = [f[2] for f in filas]
    x3s = [f[3] for f in filas]
    eas = [f[4] for f in filas]

    fig = go.Figure(
        data=[
            go.Scatter(x=its, y=x1s, mode="lines+markers", name="x₁", line=dict(color="#3b82f6")),
            go.Scatter(x=its, y=x2s, mode="lines+markers", name="x₂", line=dict(color="#f59e0b")),
            go.Scatter(x=its, y=x3s, mode="lines+markers", name="x₃", line=dict(color="#10b981")),
            go.Scatter(x=its, y=eas, mode="lines+markers", name="Ea (%)", line=dict(color="#ef4444", dash="dot"), yaxis="y2"),
        ],
        layout=go.Layout(
            title="Convergencia — Método de Jacobi",
            xaxis=dict(title="Iteración", showgrid=True, gridcolor="lightgray"),
            yaxis=dict(title="Valor de incógnitas", showgrid=True, gridcolor="lightgray"),
            yaxis2=dict(title="Ea (%)", overlaying="y", side="right", showgrid=False),
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend=dict(orientation="h", y=-0.2),
        ),
    )

    os.makedirs("static/imagenes", exist_ok=True)
    ruta = f"static/imagenes/jacobi_{ejercicio}.html"
    pio.write_html(fig, file=ruta, auto_open=False)
    return "/" + ruta


@jacobi_bp.route("/jacobi", methods=["POST"])
def ejecutar_jacobi():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        matriz_txt = _campo_texto("matriz", "la matriz de coeficientes")
        b_txt = _campo_texto("b", "el vector de términos independientes")
        x0_txt = _campo_texto("x0", "el vector inicial x⁽⁰⁾")
        es = _campo_float("es", "Es%")
        if es <= 0:
            raise ValueError("Es% debe ser mayor que 0.")

        A = _parse_matriz(matriz_txt)
        b = _parse_vector(b_txt, "El vector b")
        x0 = _parse_vector(x0_txt, "El vector x0")

        dominante = _es_diagonalmente_dominante(A)
        filas = _iterar_jacobi(A, b, x0, es)
        _guardar(ejercicio, filas)

        imagen = ""
        try:
            imagen = _graficar(ejercicio, filas)
        except Exception:
            imagen = ""

        aviso = ""
        if not dominante:
            aviso = " Advertencia: la matriz no es estrictamente diagonalmente dominante; la convergencia no está garantizada."

        return jsonify({
            "mensaje": f"Método de Jacobi guardado correctamente.{aviso}",
            "imagen": imagen,
            "iteraciones": len(filas),
            "dominante": dominante,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Error interno: {str(e)}"}), 500


@jacobi_bp.route("/resultados-jacobi")
def resultados_jacobi():
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ejercicio, iteracion, x1, x2, x3, ea
            FROM metodo_jacobi
            ORDER BY ejercicio ASC, iteracion ASC
            """
        )
        filas = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@jacobi_bp.route("/buscar_ejercicio_jacobi/<int:ejercicio>", methods=["GET"])
def buscar_ejercicio_jacobi(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ejercicio, iteracion, x1, x2, x3, ea
            FROM metodo_jacobi
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


@jacobi_bp.route("/eliminar-jacobi/<int:ejercicio>", methods=["DELETE"])
def eliminar_jacobi(ejercicio):
    try:
        _asegurar_tabla()
        conn = _db()
        cur = conn.cursor()
        cur.execute("DELETE FROM metodo_jacobi WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"mensaje": f"Registros del ejercicio #{ejercicio} eliminados correctamente."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@jacobi_bp.route("/actualizar-jacobi", methods=["POST"])
def actualizar_jacobi():
    try:
        _asegurar_tabla()
        ejercicio = int(_campo_texto("ejercicio", "el número de ejercicio"))
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM metodo_jacobi WHERE ejercicio = %s", (ejercicio,))
        existe = cur.fetchone()[0] > 0
        cur.close()
        conn.close()
        if not existe:
            return jsonify({"error": f"No existe el ejercicio #{ejercicio}. Primero use Calcular."}), 404
        request.form = request.form.copy()
        request.form["ejercicio"] = str(ejercicio)
        return ejecutar_jacobi()
    except ValueError:
        return jsonify({"error": "Ejercicio debe ser un número entero válido."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
