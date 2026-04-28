from flask import Blueprint, request, jsonify
import math
import re
import mysql.connector
import plotly.graph_objs as go
import plotly.io as pio
import numpy as np
import os

muller_bp = Blueprint('muller', __name__)


def _aplicar_reemplazos(expresion):
    expresion = expresion.replace("sen", "sin")
    expresion = expresion.replace("raiz", "sqrt")
    expresion = expresion.replace("ln", "log_ln_")
    expresion = expresion.replace("log(", "log10(")
    expresion = expresion.replace("log_ln_", "log")
    expresion = expresion.replace("arctan", "atan")
    expresion = expresion.replace("arcsin", "asin")
    expresion = expresion.replace("arccos", "acos")
    expresion = expresion.replace("^", "**")
    expresion = re.sub(r"e\*\*(\(?[^\)\+\-\*/]+?\)?)", r"exp(\1)", expresion)
    return expresion


def _asegurar_tabla_muller(cursor):
    cursor.execute(
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


@muller_bp.route('/muller', methods=['POST'])
def ejecutar_muller():
    try:
        funcion_usuario = request.form['funcion']
        funcion = _aplicar_reemplazos(funcion_usuario)
        x0 = float(request.form['x0'])
        x1 = float(request.form['x1'])
        x2 = float(request.form['x2'])
        es = float(request.form['es'])
        ejercicio = int(request.form['ejercicio'])
        max_iter = 100

        allowed_names = {name: getattr(math, name) for name in dir(math) if not name.startswith("__")}
        allowed_names["x"] = 0

        def f(x):
            allowed_names["x"] = x
            return eval(funcion, {"__builtins__": None}, allowed_names)

        resultados = []
        iteracion = 1
        ea = 0.0

        while iteracion <= max_iter:
            f0 = f(x0)
            f1 = f(x1)
            f2 = f(x2)

            h0 = x1 - x0
            h1 = x2 - x1
            if h0 == 0 or h1 == 0:
                raise ValueError("Los valores iniciales deben ser diferentes entre sí.")

            d0 = (f1 - f0) / h0
            d1 = (f2 - f1) / h1
            a = (d1 - d0) / (h1 + h0)
            b = a * h1 + d1
            c = f2

            discriminante = (b ** 2) - 4 * a * c
            if discriminante < 0:
                raise ValueError("El discriminante fue negativo. Prueba otros valores iniciales.")

            denominador_base = math.sqrt(discriminante)
            if abs(b + denominador_base) > abs(b - denominador_base):
                denominador = b + denominador_base
            else:
                denominador = b - denominador_base

            if denominador == 0:
                raise ZeroDivisionError("Se produjo división por cero en el cálculo de Müller.")

            x3 = x2 + (-2 * c / denominador)
            ea = abs((x3 - x2) / x3) * 100 if x3 != 0 else 0

            resultados.append((ejercicio, iteracion, x0, x1, x2, x3, f(x3), round(ea, 6)))

            if iteracion > 1 and ea < es:
                break

            x0, x1, x2 = x1, x2, x3
            iteracion += 1

        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        _asegurar_tabla_muller(cursor)
        cursor.execute("DELETE FROM metodo_muller WHERE ejercicio = %s", (ejercicio,))
        for fila in resultados:
            cursor.execute(
                """
                INSERT INTO metodo_muller
                (ejercicio, iteracion, x0, x1, x2, x3, fx3, ea)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                fila
            )

        conn.commit()
        cursor.close()
        conn.close()

        try:
            x_vals = np.linspace(min(x0, x1, x2) - 10, max(x0, x1, x2) + 10, 1200)
            y_vals = []
            for valor in x_vals:
                try:
                    y = f(valor)
                    y_vals.append(y if math.isfinite(y) else None)
                except Exception:
                    y_vals.append(None)

            ultimo = resultados[-1]
            xr = ultimo[5]
            fxr = ultimo[6]

            trazo_funcion = go.Scatter(
                x=x_vals,
                y=y_vals,
                mode='lines',
                name=f"f(x) = {funcion_usuario}",
                line=dict(color='blue')
            )

            punto_raiz = go.Scatter(
                x=[xr],
                y=[fxr],
                mode='markers',
                name=f"xr = {xr:.6f}",
                marker=dict(color='orange', size=10)
            )

            fig = go.Figure(data=[trazo_funcion, punto_raiz])
            fig.update_layout(
                title=f'Método de Müller - Ejercicio {ejercicio}',
                xaxis_title='x',
                yaxis_title='f(x)',
                plot_bgcolor='white',
                paper_bgcolor='white',
                shapes=[
                    dict(type='line', x0=min(x_vals), x1=max(x_vals), y0=0, y1=0, line=dict(color='black', width=1)),
                    dict(type='line', x0=0, x1=0, y0=-10, y1=10, line=dict(color='black', width=1))
                ]
            )

            os.makedirs("static/imagenes", exist_ok=True)
            html_path = f"static/imagenes/muller_{ejercicio}.html"
            pio.write_html(fig, file=html_path, auto_open=False)
        except Exception as error_grafica:
            print("Error generando gráfica de Müller:", error_grafica)
            html_path = ""

        return jsonify({
            "mensaje": "Cálculos de Müller realizados y guardados correctamente.",
            "imagen": "/" + html_path
        })
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@muller_bp.route('/resultados-muller')
def ver_resultados_muller():
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        _asegurar_tabla_muller(cursor)
        cursor.execute(
            """
            SELECT ejercicio, iteracion, x0, x1, x2, x3, fx3, ea
            FROM metodo_muller
            ORDER BY ejercicio ASC, iteracion ASC
            """
        )
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(filas)
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@muller_bp.route('/eliminar-muller/<int:ejercicio>', methods=['DELETE'])
def eliminar_muller(ejercicio):
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        _asegurar_tabla_muller(cursor)
        cursor.execute("DELETE FROM metodo_muller WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Registros del ejercicio #{ejercicio} eliminados correctamente."
    except Exception as error:
        return f"Error: {str(error)}", 500


@muller_bp.route('/actualizar-muller', methods=['POST'])
def actualizar_muller():
    ejercicio = int(request.form['ejercicio'])
    conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
    cursor = conn.cursor()
    _asegurar_tabla_muller(cursor)
    cursor.execute("DELETE FROM metodo_muller WHERE ejercicio = %s", (ejercicio,))
    conn.commit()
    cursor.close()
    conn.close()
    request.form = request.form.copy()
    request.form['ejercicio'] = str(ejercicio)
    return ejecutar_muller()


@muller_bp.route('/buscar_ejercicio_muller/<int:ejercicio>', methods=['GET'])
def buscar_ejercicio_muller(ejercicio):
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor(dictionary=True)
        _asegurar_tabla_muller(cursor)
        cursor.execute(
            """
            SELECT ejercicio, iteracion, x0, x1, x2, x3, fx3, ea
            FROM metodo_muller
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
