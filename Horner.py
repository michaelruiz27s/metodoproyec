
from flask import Blueprint, request, jsonify
import math
import re
import mysql.connector
import plotly.graph_objs as go
import plotly.io as pio
import numpy as np
import os

horner_bp = Blueprint('horner', __name__)

def _aplicar_reemplazos(expresion):
    expresion = expresion.replace("raiz", "sqrt")
    expresion = expresion.replace("sen", "sin")
    expresion = expresion.replace("ln", "log_ln_")
    expresion = expresion.replace("log(", "log10(")
    expresion = expresion.replace("log_ln_", "log")
    expresion = expresion.replace("^", "**")
    expresion = re.sub(r'e\*\*(\(?[^\)\+\-\*/]+?\)?)', r'exp(\1)', expresion)
    return expresion

def evaluar_polinomio(coeficientes, x):
    """Evaluación usando método de Horner"""
    resultado = coeficientes[0]
    for coef in coeficientes[1:]:
        resultado = resultado * x + coef
    return resultado

@horner_bp.route('/horner', methods=['POST'])
def ejecutar_horner():
    try:
        ejercicio = int(request.form['ejercicio'])
        polinomio_str = request.form['polinomio']          # Ej: "x^3 - 6x^2 + 11x - 6"
        x0 = float(request.form['x0'])
        es = float(request.form['es'])
        max_iter = 100

        # Convertir polinomio a coeficientes (de mayor a menor grado)
        # Ej: "x^3 - 6x^2 + 11x - 6" → [1, -6, 11, -6]
        def polinomio_a_coeficientes(expr):
            expr = _aplicar_reemplazos(expr.replace(" ", ""))
            # Reemplazar x^ n por pow
            expr = re.sub(r'x\^(\d+)', r'x**\1', expr)
            # Usamos sympy para obtener coeficientes de forma robusta
            from sympy import symbols, Poly, sympify
            x = symbols('x')
            poly = Poly(sympify(expr), x)
            return poly.all_coeffs()  # coeficientes de mayor a menor grado

        coeficientes = polinomio_a_coeficientes(polinomio_str)

        resultados = []
        xi = x0
        i = 1

        while i <= max_iter:
            fxi = evaluar_polinomio(coeficientes, xi)
            
            # Derivada aproximada (también con Horner)
            # Derivada numérica simple o analítica básica
            h = 1e-8
            dfxi = (evaluar_polinomio(coeficientes, xi + h) - fxi) / h

            if abs(dfxi) < 1e-12:
                raise ValueError("Derivada cercana a cero. Prueba otro valor inicial.")

            xi_nuevo = xi - fxi / dfxi
            ea = abs((xi_nuevo - xi) / xi_nuevo) * 100 if xi_nuevo != 0 else 0

            resultados.append((
                ejercicio, i, xi, fxi, dfxi, xi_nuevo, round(ea, 6)
            ))

            if ea < es and i > 1:
                break

            xi = xi_nuevo
            i += 1

        # Guardar en BD
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM metodo_horner WHERE ejercicio = %s", (ejercicio,))
        
        for fila in resultados:
            cursor.execute("""
                INSERT INTO metodo_horner 
                (ejercicio, iteracion, xi, fxi, dfxi, xi_nuevo, ea)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, fila)

        conn.commit()
        cursor.close()
        conn.close()

        # Gráfica
        try:
            x_vals = np.linspace(min(coeficientes)-2, max(coeficientes)+2, 1000) if len(coeficientes) > 1 else np.linspace(-10, 10, 1000)
            y_vals = [evaluar_polinomio(coeficientes, x) for x in x_vals]

            raiz = resultados[-1][5]

            trace = go.Scatter(x=x_vals, y=y_vals, mode='lines', name=f'P(x) = {polinomio_str}', line=dict(color='blue'))
            raiz_point = go.Scatter(x=[raiz], y=[evaluar_polinomio(coeficientes, raiz)], 
                                  mode='markers', name=f'Raíz ≈ {raiz:.6f}', 
                                  marker=dict(color='red', size=12))

            fig = go.Figure(data=[trace, raiz_point])
            fig.update_layout(
                title=f'Método de Horner - Ejercicio {ejercicio}',
                xaxis_title='x', yaxis_title='P(x)',
                plot_bgcolor='white', paper_bgcolor='white'
            )

            os.makedirs("static/imagenes", exist_ok=True)
            html_path = f"static/imagenes/horner_{ejercicio}.html"
            pio.write_html(fig, file=html_path, auto_open=False)
        except:
            html_path = ""

        return jsonify({
            "mensaje": "✅ Método de Horner ejecutado correctamente.",
            "imagen": "/" + html_path
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== RUTAS AUXILIARES ====================

@horner_bp.route('/resultados-horner')
def ver_resultados_horner():
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM metodo_horner ORDER BY ejercicio ASC, iteracion ASC")
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@horner_bp.route('/eliminar-horner/<int:ejercicio>', methods=['DELETE'])
def eliminar_horner(ejercicio):
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM metodo_horner WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Registros del ejercicio #{ejercicio} eliminados correctamente."
    except Exception as e:
        return f"Error: {str(e)}", 500


@horner_bp.route('/actualizar-horner', methods=['POST'])
def actualizar_horner():
    ejercicio = int(request.form['ejercicio'])
    conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM metodo_horner WHERE ejercicio = %s", (ejercicio,))
    conn.commit()
    cursor.close()
    conn.close()
    
    request.form = request.form.copy()
    request.form['ejercicio'] = str(ejercicio)
    return ejecutar_horner()




