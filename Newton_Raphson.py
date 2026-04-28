from flask import Blueprint, request, jsonify
import math
import re
import mysql.connector
import plotly.graph_objs as go
import plotly.io as pio
import numpy as np
import os

newton_bp = Blueprint('newton_raphson', __name__)

@newton_bp.route('/newton-raphson', methods=['POST'])
def ejecutar_newton_raphson():
    try:
        funcion = request.form['funcion']
        derivada = request.form['derivada']
        x0 = float(request.form['x0'])
        es = float(request.form['es'])
        ejercicio = request.form['ejercicio']
        max_iter = 100

        def aplicar_reemplazos(s):
            s = s.replace("raiz", "sqrt")
            s = s.replace("ln", "log_ln_")
            s = s.replace("log(", "log10(")
            s = s.replace("log_ln_", "log")
            s = s.replace("sen", "sin")
            s = s.replace("arctan", "atan")
            s = s.replace("arcsin", "asin")
            s = s.replace("arccos", "acos")
            s = s.replace("^", "**")
            s = re.sub(r'e\*\*(\(?[^\)\+\-\*/]+?\)?)', r'exp(\1)', s)
            return s

        funcion = aplicar_reemplazos(funcion)
        derivada = aplicar_reemplazos(derivada)

        allowed_names = {name: getattr(math, name) for name in dir(math) if not name.startswith("__")}
        allowed_names["x"] = 0

        def f(x):
            allowed_names["x"] = x
            return eval(funcion, {"__builtins__": None}, allowed_names)

        def df(x):
            allowed_names["x"] = x
            return eval(derivada, {"__builtins__": None}, allowed_names)

        resultados = []
        i = 1
        xi = x0
        ea = 0
        fxi = f(xi)
        dfxi = df(xi)
        if dfxi == 0:
            raise ZeroDivisionError(f"Derivada es cero en x = {xi}")
        xi1 = xi - fxi / dfxi
        resultados.append((int(ejercicio), i, xi, fxi, dfxi, xi1, ea))

        i += 1
        while i <= max_iter:
            xi = xi1
            fxi = f(xi)
            dfxi = df(xi)

            if dfxi == 0:
                raise ZeroDivisionError(f"Derivada es cero en x = {xi}")

            xi1 = xi - fxi / dfxi
            ea = abs((xi1 - xi) / xi1) * 100 if xi1 != 0 else 0
            resultados.append((int(ejercicio), i, xi, fxi, dfxi, xi1, round(ea, 6)))

            if ea < es:
                break
            i += 1

        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM metodo_newton_raphson WHERE ejercicio = %s", (ejercicio,))
        for fila in resultados:
            cursor.execute("""
                INSERT INTO metodo_newton_raphson 
                (ejercicio, iteracion, xi, fxi, dfxi, xi1, ea)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, fila)

        conn.commit()
        cursor.close()
        conn.close()

        try:
            x_vals = np.linspace(x0 - 10, x0 + 10, 1200)
            y_vals = []
            for x_val in x_vals:
                try:
                    y = f(x_val)
                    y_vals.append(y if math.isfinite(y) else None)
                except Exception:
                    y_vals.append(None)

            xr = resultados[-1][5]
            fxr = f(xr)

            trazo_funcion = go.Scatter(
                x=x_vals,
                y=y_vals,
                mode='lines',
                name=f"f(x) = {request.form['funcion']}",
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
                title=f'Método de Newton-Raphson - Ejercicio {ejercicio}',
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
            html_path = f"static/imagenes/newton_{ejercicio}.html"
            pio.write_html(fig, file=html_path, auto_open=False)
        except Exception as err:
            print("❌ Error generando gráfica de Newton-Raphson:", err)
            html_path = ""

        return jsonify({
            "mensaje": "✅ Cálculos de Newton-Raphson realizados y guardados correctamente.",
            "imagen": "/" + html_path
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@newton_bp.route('/resultados-newton-raphson')
def ver_resultados_newton_raphson():
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ejercicio, iteracion, xi, fxi, dfxi, xi1, ea
            FROM metodo_newton_raphson
            ORDER BY ejercicio ASC, iteracion ASC
        """)
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@newton_bp.route('/eliminar-newton-raphson/<int:ejercicio>', methods=['DELETE'])
def eliminar_newton_raphson(ejercicio):
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM metodo_newton_raphson WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cursor.close()
        conn.close()
        return f"✅ Registros del ejercicio #{ejercicio} eliminados correctamente."
    except Exception as e:
        return f"❌ Error: {str(e)}", 500


@newton_bp.route('/actualizar-newton-raphson', methods=['POST'])
def actualizar_newton_raphson():
    ejercicio = int(request.form['ejercicio'])

    conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM metodo_newton_raphson WHERE ejercicio = %s", (ejercicio,))
    conn.commit()
    cursor.close()
    conn.close()

    request.form = request.form.copy()
    request.form['ejercicio'] = str(ejercicio)

    return ejecutar_newton_raphson()
