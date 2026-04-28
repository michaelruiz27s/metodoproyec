from flask import Blueprint, request, jsonify
import math
import os
import re

import mysql.connector
import numpy as np
import plotly.graph_objs as go
import plotly.io as pio

newton_senl_bp = Blueprint('newton_senl', __name__)


def _aplicar_reemplazos(expresion):
    expresion = expresion.lower().replace(" ", "")
    expresion = expresion.replace("sen", "sin")
    expresion = expresion.replace("raiz", "sqrt")
    expresion = expresion.replace("ln", "log_ln_")
    expresion = expresion.replace("log(", "log10(")
    expresion = expresion.replace("log_ln_", "log")
    expresion = expresion.replace("arctan", "atan")
    expresion = expresion.replace("arcsin", "asin")
    expresion = expresion.replace("arccos", "acos")
    expresion = expresion.replace("^", "**")
    if "=" in expresion:
        lados = expresion.split("=")
        if len(lados) != 2 or not lados[0] or not lados[1]:
            raise ValueError(f"Ecuacion invalida: {expresion}")
        expresion = f"({lados[0]})-({lados[1]})"

    expresion = re.sub(r"(\d)([xyz(])", r"\1*\2", expresion)
    expresion = re.sub(r"([xyz)])(\d)", r"\1*\2", expresion)
    expresion = re.sub(r"([xyz])(\()", r"\1*\2", expresion)
    expresion = re.sub(r"(\))([xyz])", r"\1*\2", expresion)
    expresion = re.sub(r"(\))(\()", r"\1*\2", expresion)
    expresion = re.sub(r"(\d)([a-df-z])", r"\1*\2", expresion)
    expresion = re.sub(r"e\*\*(\(?[^\)\+\-\*/]+?\)?)", r"exp(\1)", expresion)
    return expresion


def _asegurar_tabla(cursor):
    cursor.execute(
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
            j11 DOUBLE,
            j12 DOUBLE,
            j13 DOUBLE,
            j21 DOUBLE,
            j22 DOUBLE,
            j23 DOUBLE,
            j31 DOUBLE,
            j32 DOUBLE,
            j33 DOUBLE,
            delta_x DOUBLE,
            delta_y DOUBLE,
            delta_z DOUBLE,
            e1 DOUBLE,
            e2 DOUBLE,
            e3 DOUBLE
        )
        """
    )

    cursor.execute("SHOW COLUMNS FROM metodo_newton_sistemas")
    columnas_existentes = {fila[0] for fila in cursor.fetchall()}
    columnas_requeridas = {
        "z": "DOUBLE",
        "fz": "DOUBLE",
        "j13": "DOUBLE",
        "j23": "DOUBLE",
        "j31": "DOUBLE",
        "j32": "DOUBLE",
        "j33": "DOUBLE",
        "delta_z": "DOUBLE",
        "e3": "DOUBLE",
    }

    for nombre, tipo in columnas_requeridas.items():
        if nombre not in columnas_existentes:
            cursor.execute(f"ALTER TABLE metodo_newton_sistemas ADD COLUMN {nombre} {tipo}")


def _resolver_sistema(funciones, x_vec, max_iter, es):
    eps = 1e-6
    resultados = []

    for i in range(1, max_iter + 1):
        f_val = np.array([fn(*x_vec) for fn in funciones], dtype=float)

        jac = np.zeros((3, 3), dtype=float)
        for col in range(3):
            x_temp = x_vec.copy()
            x_temp[col] += eps
            f_eps = np.array([fn(*x_temp) for fn in funciones], dtype=float)
            jac[:, col] = (f_eps - f_val) / eps

        try:
            delta = np.linalg.solve(jac, -f_val)
        except np.linalg.LinAlgError:
            raise ValueError("Jacobiano singular. Cambia el vector inicial.")

        x_nuevo = x_vec + delta
        errores = np.zeros_like(x_nuevo, dtype=float)
        mascara = x_nuevo != 0
        errores[mascara] = np.abs((x_nuevo[mascara] - x_vec[mascara]) / x_nuevo[mascara]) * 100

        resultados.append({
            "iteracion": i,
            "x": float(x_vec[0]),
            "y": float(x_vec[1]),
            "z": float(x_vec[2]),
            "fx": float(f_val[0]),
            "fy": float(f_val[1]),
            "fz": float(f_val[2]),
            "j11": float(jac[0, 0]),
            "j12": float(jac[0, 1]),
            "j13": float(jac[0, 2]),
            "j21": float(jac[1, 0]),
            "j22": float(jac[1, 1]),
            "j23": float(jac[1, 2]),
            "j31": float(jac[2, 0]),
            "j32": float(jac[2, 1]),
            "j33": float(jac[2, 2]),
            "delta_x": float(delta[0]),
            "delta_y": float(delta[1]),
            "delta_z": float(delta[2]),
            "e1": float(errores[0]),
            "e2": float(errores[1]),
            "e3": float(errores[2]),
        })

        x_vec = x_nuevo
        if np.max(errores) < es:
            break

    return resultados


def _crear_grafica_senl(resultados, ejercicio):
    xs = [fila["x"] for fila in resultados]
    ys = [fila["y"] for fila in resultados]
    zs = [fila["z"] for fila in resultados]
    x_raiz = resultados[-1]["x"] + resultados[-1]["delta_x"]
    y_raiz = resultados[-1]["y"] + resultados[-1]["delta_y"]
    z_raiz = resultados[-1]["z"] + resultados[-1]["delta_z"]

    trazo_iteraciones = go.Scatter3d(
        x=xs,
        y=ys,
        z=zs,
        mode='lines+markers',
        name='Iteraciones',
        line=dict(color='deepskyblue', width=6),
        marker=dict(size=5, color=list(range(1, len(xs) + 1)), colorscale='Viridis')
    )
    punto_raiz = go.Scatter3d(
        x=[x_raiz],
        y=[y_raiz],
        z=[z_raiz],
        mode='markers',
        name='Raiz aproximada',
        marker=dict(size=9, color='orange', symbol='diamond')
    )

    fig = go.Figure(data=[trazo_iteraciones, punto_raiz])
    fig.update_layout(
        title=f'Newton-Raphson para Sistemas - Ejercicio {ejercicio}',
        scene=dict(xaxis_title='x', yaxis_title='y', zaxis_title='z'),
        paper_bgcolor='white'
    )

    os.makedirs("static/imagenes", exist_ok=True)
    html_path = f"static/imagenes/newton_senl_{ejercicio}.html"
    pio.write_html(fig, file=html_path, auto_open=False)
    return html_path


@newton_senl_bp.route('/newton-senl', methods=['POST'])
def ejecutar_newton_senl():
    try:
        ejercicio = int(request.form['ejercicio'])
        f1_txt = _aplicar_reemplazos(request.form['f1'])
        f2_txt = _aplicar_reemplazos(request.form['f2'])
        f3_txt = _aplicar_reemplazos(request.form['f3'])
        x0 = float(request.form['x0'])
        y0 = float(request.form['y0'])
        z0 = float(request.form['z0'])
        es = float(request.form['es'])
        max_iter = int(request.form.get('max_iter', 100))

        allowed_names = {name: getattr(math, name) for name in dir(math) if not name.startswith("__")}
        allowed_names.update({"x": 0, "y": 0, "z": 0})

        def f1(x, y, z):
            allowed_names.update({"x": x, "y": y, "z": z})
            return eval(f1_txt, {"__builtins__": None}, allowed_names)

        def f2(x, y, z):
            allowed_names.update({"x": x, "y": y, "z": z})
            return eval(f2_txt, {"__builtins__": None}, allowed_names)

        def f3(x, y, z):
            allowed_names.update({"x": x, "y": y, "z": z})
            return eval(f3_txt, {"__builtins__": None}, allowed_names)

        resultados = _resolver_sistema([f1, f2, f3], np.array([x0, y0, z0], dtype=float), max_iter, es)

        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        _asegurar_tabla(cursor)
        cursor.execute("DELETE FROM metodo_newton_sistemas WHERE ejercicio = %s", (ejercicio,))

        for fila in resultados:
            cursor.execute(
                """
                INSERT INTO metodo_newton_sistemas (
                    ejercicio, iteracion, x, y, z, fx, fy, fz,
                    j11, j12, j13, j21, j22, j23, j31, j32, j33,
                    delta_x, delta_y, delta_z, e1, e2, e3
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ejercicio, fila["iteracion"], fila["x"], fila["y"], fila["z"], fila["fx"], fila["fy"], fila["fz"],
                    fila["j11"], fila["j12"], fila["j13"], fila["j21"], fila["j22"], fila["j23"], fila["j31"], fila["j32"], fila["j33"],
                    fila["delta_x"], fila["delta_y"], fila["delta_z"], fila["e1"], fila["e2"], fila["e3"]
                )
            )

        conn.commit()
        cursor.close()
        conn.close()

        try:
            html_path = _crear_grafica_senl(resultados, ejercicio)
        except Exception as error_grafica:
            print("Error generando grafica SENL:", error_grafica)
            html_path = ""

        return jsonify({
            "mensaje": "Calculos de Newton-Raphson para sistemas realizados correctamente.",
            "imagen": "/" + html_path
        })
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@newton_senl_bp.route('/resultados-newton-senl')
def ver_resultados_newton_senl():
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        _asegurar_tabla(cursor)
        cursor.execute(
            """
            SELECT ejercicio, iteracion, x, y, z, fx, fy, fz, delta_x, delta_y, delta_z, e1, e2, e3
            FROM metodo_newton_sistemas
            ORDER BY ejercicio ASC, iteracion ASC
            """
        )
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(filas)
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@newton_senl_bp.route('/buscar_ejercicio_newton_senl/<int:ejercicio>')
def buscar_ejercicio_newton_senl(ejercicio):
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor(dictionary=True)
        _asegurar_tabla(cursor)
        cursor.execute(
            """
            SELECT ejercicio, iteracion, x, y, z, fx, fy, fz, delta_x, delta_y, delta_z, e1, e2, e3
            FROM metodo_newton_sistemas
            WHERE ejercicio = %s
            ORDER BY iteracion ASC
            """,
            (ejercicio,)
        )
        resultados = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(resultados)
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@newton_senl_bp.route('/eliminar-newton-senl/<int:ejercicio>', methods=['DELETE'])
def eliminar_newton_senl(ejercicio):
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        _asegurar_tabla(cursor)
        cursor.execute("DELETE FROM metodo_newton_sistemas WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Registros del ejercicio #{ejercicio} eliminados correctamente."
    except Exception as error:
        return f"Error: {str(error)}", 500


@newton_senl_bp.route('/actualizar-newton-senl', methods=['POST'])
def actualizar_newton_senl():
    return ejecutar_newton_senl()
