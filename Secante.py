from flask import Blueprint, request, jsonify
import math
import re
import mysql.connector
import plotly.graph_objs as go
import plotly.io as pio
import numpy as np
import os

secante_bp = Blueprint('secante', __name__)


@secante_bp.route('/secante', methods=['POST'])
def ejecutar_secante():
    try:
        funcion = request.form['funcion']
        x_actual = float(request.form['x0'])
        x_anterior = float(request.form['x1'])
        es = float(request.form['es'])
        ejercicio = request.form['ejercicio']
        max_iter = 100

        def aplicar_reemplazos(f_str):
            f_str = f_str.replace("sen", "sin")
            f_str = f_str.replace("raiz", "sqrt")
            f_str = f_str.replace("ln", "log_ln_")
            f_str = f_str.replace("log(", "log10(")
            f_str = f_str.replace("log_ln_", "log")
            f_str = f_str.replace("arctan", "atan")
            f_str = f_str.replace("arcsin", "asin")
            f_str = f_str.replace("arccos", "acos")
            f_str = f_str.replace("^", "**")
            f_str = re.sub(r'e\*\*(\(?[^\)\+\-\*/]+?\)?)', r'exp(\1)', f_str)
            return f_str

        funcion = aplicar_reemplazos(funcion)

        allowed_names = {name: getattr(math, name) for name in dir(math) if not name.startswith("__")}
        allowed_names["x"] = 0

        def f(x):
            allowed_names["x"] = x
            return eval(funcion, {"__builtins__": None}, allowed_names)

        resultados = []
        i = 1

        while i <= max_iter:
            f_anterior = f(x_anterior)
            f_actual = f(x_actual)

            if (f_actual - f_anterior) == 0:
                raise ValueError("Division por cero detectada durante el calculo.")

            x_siguiente = x_actual - f_actual * (x_actual - x_anterior) / (f_actual - f_anterior)
            ea = 0 if i == 1 else (abs((x_siguiente - x_actual) / x_siguiente) * 100 if x_siguiente != 0 else 0)

            resultados.append((
                int(ejercicio), i, x_actual, x_anterior, f_actual, f_anterior, x_siguiente, round(ea, 6)
            ))

            if ea < es and i > 1:
                break

            x_anterior = x_actual
            x_actual = x_siguiente
            i += 1

        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM metodo_secante WHERE ejercicio = %s", (ejercicio,))
        for fila in resultados:
            cursor.execute(
                """
                INSERT INTO metodo_secante
                (ejercicio, iteracion, xi, xi_1, fxi, fxi_1, xi_t, ea)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                fila
            )

        conn.commit()
        cursor.close()
        conn.close()

        try:
            x_actual_original = float(request.form['x0'])
            x_anterior_original = float(request.form['x1'])
            f_anterior_original = f(x_anterior_original)
            f_actual_original = f(x_actual_original)
            x2_geo = x_actual_original - f_actual_original * (x_actual_original - x_anterior_original) / (f_actual_original - f_anterior_original)

            x_vals = np.linspace(-2000, 2000, 20000)
            x_vals_filtrados = []
            y_vals_filtrados = []

            for x in x_vals:
                try:
                    y = f(x)
                    x_vals_filtrados.append(x)
                    y_vals_filtrados.append(y if math.isfinite(y) else None)
                except Exception:
                    x_vals_filtrados.append(x)
                    y_vals_filtrados.append(None)

            trace_func = go.Scatter(
                x=x_vals_filtrados,
                y=y_vals_filtrados,
                mode='lines',
                name=f"f(x) = {funcion}",
                line=dict(color='blue')
            )
            trace_A = go.Scatter(
                x=[x_anterior_original],
                y=[f(x_anterior_original)],
                mode='markers',
                name=f"A = ({x_anterior_original:.2f}, {f(x_anterior_original):.3f})",
                marker=dict(color='red', size=10),
                text=['x(i-1)'],
                textposition="top center"
            )
            trace_B = go.Scatter(
                x=[x_actual_original],
                y=[f(x_actual_original)],
                mode='markers',
                name=f"B = ({x_actual_original:.2f}, {f(x_actual_original):.3f})",
                marker=dict(color='green', size=10),
                text=['x(i)'],
                textposition="top center"
            )
            trace_C = go.Scatter(
                x=[x2_geo],
                y=[f(x2_geo)],
                mode='markers',
                name=f"C = ({x2_geo:.2f})",
                marker=dict(color='orange', size=10),
                text=['x(i+1)'],
                textposition="top center"
            )

            layout = go.Layout(
                title='Grafica del Metodo de la Secante',
                plot_bgcolor='white',
                paper_bgcolor='white',
                xaxis=dict(
                    title='x',
                    range=[-10, 10],
                    showgrid=True,
                    gridcolor='lightgray',
                    zeroline=True,
                    zerolinecolor='black',
                    zerolinewidth=2
                ),
                yaxis=dict(
                    title='f(x)',
                    range=[-10, 10],
                    showgrid=True,
                    gridcolor='lightgray',
                    zeroline=True,
                    zerolinecolor='black',
                    zerolinewidth=2
                ),
                shapes=[
                    dict(type='line', x0=0, y0=-1000, x1=0, y1=1000, line=dict(color='black', width=2)),
                    dict(type='line', x0=-1000, y0=0, x1=1000, y1=0, line=dict(color='black', width=2))
                ],
                showlegend=True,
                hovermode='closest'
            )

            fig = go.Figure(data=[trace_func, trace_A, trace_B, trace_C], layout=layout)
            os.makedirs("static/imagenes", exist_ok=True)
            html_path = f"static/imagenes/secante_{ejercicio}.html"
            pio.write_html(fig, file=html_path, auto_open=False)
        except Exception as err:
            print("Error generando grafica Secante:", err)
            html_path = ""

        return jsonify({
            "mensaje": "Calculos de la secante realizados y guardados correctamente.",
            "imagen": "/" + html_path
        })

    except Exception as err:
        return jsonify({"error": str(err)}), 500


@secante_bp.route('/resultados-secante')
def ver_resultados_secante():
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ejercicio, iteracion, xi, xi_1, fxi, fxi_1, xi_t, ea
            FROM metodo_secante
            ORDER BY ejercicio ASC, iteracion ASC
            """
        )

        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@secante_bp.route('/eliminar-secante/<int:ejercicio>', methods=['DELETE'])
def eliminar_secante(ejercicio):
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM metodo_secante WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Registros del ejercicio #{ejercicio} eliminados correctamente."
    except Exception as e:
        return f"Error: {str(e)}", 500


@secante_bp.route('/actualizar-secante', methods=['POST'])
def actualizar_secante():
    ejercicio = int(request.form['ejercicio'])

    conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM metodo_secante WHERE ejercicio = %s", (ejercicio,))
    conn.commit()
    cursor.close()
    conn.close()

    request.form = request.form.copy()
    request.form['ejercicio'] = str(ejercicio)

    return ejecutar_secante()


@secante_bp.route('/buscar_ejercicio_secante/<int:ejercicio>', methods=['GET'])
def buscar_ejercicio_secante(ejercicio):
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT ejercicio, iteracion, xi, xi_1, fxi, fxi_1, xi_t, ea
            FROM metodo_secante
            WHERE ejercicio = %s
            ORDER BY iteracion ASC
            """,
            (ejercicio,)
        )

        resultados = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify(resultados)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
