from flask import Blueprint, request, jsonify, send_from_directory
import mysql.connector
import json
import os
import numpy as np
import plotly.graph_objects as go

horner_bp = Blueprint('horner', __name__)


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="david98",
        database="metodos_numericos"
    )


def horner(coef, x):
    resultado = coef[0]
    for i in range(1, len(coef)):
        resultado = resultado * x + coef[i]
    return resultado


def generar_grafica_horner(coef, x_valor, ejercicio):
    try:
        x = np.linspace(-10, 10, 400)
        y = np.polyval(coef, x)

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode='lines',
            name='Polinomio'
        ))

        punto = np.polyval(coef, x_valor)

        fig.add_trace(go.Scatter(
            x=[x_valor],
            y=[punto],
            mode='markers+text',
            marker=dict(color='red', size=10),
            text=[f"P({x_valor}) = {punto:.6f}"],
            textposition="top center",
            name="Evaluación"
        ))

        fig.update_layout(
            title=f"Horner - Ejercicio {ejercicio}",
            xaxis_title="x",
            yaxis_title="P(x)",
            template="plotly_white"
        )

        os.makedirs("static/imagenes", exist_ok=True)
        fig.write_html(f"static/imagenes/horner_{ejercicio}.html")

    except Exception as e:
        print("Error gráfica:", e)


@horner_bp.route('/horner', methods=['POST'])
def ejecutar_horner():
    try:
        ejercicio = request.form.get('ejercicio')
        polinomio = request.form.get('polinomio')
        x = float(request.form.get('x'))
        es = float(request.form.get('es'))

        coef = [float(c.strip()) for c in polinomio.split(',')]
        resultado = horner(coef, x)
        coef_json = json.dumps(coef)

        conn = get_db_connection()
        cursor = conn.cursor()

        # 🚫 evitar repetidos
        cursor.execute("SELECT COUNT(*) FROM metodo_horner WHERE ejercicio=%s", (ejercicio,))
        if cursor.fetchone()[0] > 0:
            return jsonify({"error": "Ejercicio ya existe"}), 400

        cursor.execute("""
            INSERT INTO metodo_horner
            (ejercicio, iteracion, coeficientes, x, es, resultado)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (ejercicio, 1, coef_json, x, es, resultado))

        conn.commit()
        cursor.close()
        conn.close()

        generar_grafica_horner(coef, x, ejercicio)

        return jsonify({
            "mensaje": "Horner ejecutado correctamente",
            "resultado": resultado,
            "ejercicio": ejercicio
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@horner_bp.route('/resultados-horner')
def obtener_resultados():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ejercicio, iteracion, coeficientes, x, es, resultado
            FROM metodo_horner
            ORDER BY ejercicio, iteracion
        """)

        data = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@horner_bp.route('/buscar-horner/<ejercicio>')
def buscar_horner(ejercicio):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ejercicio, iteracion, coeficientes, x, es, resultado
            FROM metodo_horner
            WHERE ejercicio=%s
            ORDER BY iteracion
        """, (ejercicio,))

        data = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@horner_bp.route('/actualizar-horner', methods=['POST'])
def actualizar_horner():
    try:
        ejercicio = request.form.get('ejercicio')
        polinomio = request.form.get('polinomio')
        x = float(request.form.get('x'))
        es = float(request.form.get('es'))

        coef_list = [float(c.strip()) for c in polinomio.split(',')]
        coef_json = json.dumps(coef_list)

        resultado = horner(coef_list, x)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE metodo_horner
            SET coeficientes=%s, x=%s, es=%s, resultado=%s
            WHERE ejercicio=%s
        """, (coef_json, x, es, resultado, ejercicio))

        conn.commit()
        cursor.close()
        conn.close()

        generar_grafica_horner(coef_list, x, ejercicio)

        return jsonify({
            "mensaje": "Actualizado correctamente",
            "resultado": resultado,
            "ejercicio": ejercicio
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@horner_bp.route('/eliminar-horner/<ejercicio>', methods=['DELETE'])
def eliminar_horner(ejercicio):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM metodo_horner WHERE ejercicio=%s", (ejercicio,))

        conn.commit()
        cursor.close()
        conn.close()

        return "Eliminado correctamente", 200

    except Exception as e:
        return str(e), 500



@horner_bp.route('/static/imagenes/<path:filename>')
def servir_grafica(filename):
    return send_from_directory('static/imagenes', filename)