from flask import Blueprint, request, jsonify
import math
import re
import mysql.connector
import plotly.graph_objs as go
import plotly.io as pio
import numpy as np
import os


biseccion_bp = Blueprint('biseccion', __name__)


def _texto_requerido(campo, etiqueta):
    v = (request.form.get(campo) or "").strip()
    if not v:
        raise ValueError(f"Complete {etiqueta} (no puede estar vacío).")
    return v


def _float_requerido(campo, etiqueta):
    s = _texto_requerido(campo, etiqueta)
    try:
        return float(s)
    except ValueError as exc:
        raise ValueError(f"{etiqueta} debe ser un número válido.") from exc


@biseccion_bp.route('/biseccion', methods=['POST'])
def ejecutar_biseccion():
    try:
        funcion = _texto_requerido("funcion", "la función f(x)")
        xa = _float_requerido("xa", "X^a (límite inferior)")
        xb = _float_requerido("xb", "X^b (límite superior)")
        xa_original = xa
        xb_original = xb
        es = _float_requerido("es", "Es% (tolerancia)")
        ejercicio = _texto_requerido("ejercicio", "el número de ejercicio")
        try:
            int(ejercicio)
        except ValueError as exc:
            raise ValueError("Ejercicio debe ser un número entero.") from exc
        max_iter = 100

        def aplicar_reemplazos(s):
            s = s.replace("raiz", "sqrt")
            s = s.replace("ln", "log_ln_")
            s = s.replace("log(", "log10(")
            s = s.replace("log_ln_", "log")
            s = s.replace("sen", "sin")
            s = s.replace("^", "**")
            # Soporta multiplicaciones implícitas comunes: 4x, 2(x+1), x(x-1), )(.
            s = re.sub(r'(\d)([a-zA-Z\(])', r'\1*\2', s)
            s = re.sub(r'([a-zA-Z\)])(\d)', r'\1*\2', s)
            s = re.sub(r'([x\)])\(', r'\1*(', s)
            s = re.sub(r'\)([a-zA-Zx])', r')*\1', s)
            s = re.sub(r'e\*\*(\(?[^\)\+\-\*/]+?\)?)', r'exp(\1)', s)
            return s

        funcion = aplicar_reemplazos(funcion)

        allowed_names = {name: getattr(math, name) for name in dir(math) if not name.startswith("__")}
        allowed_names["x"] = 0

        def f(x):
            allowed_names["x"] = x
            return eval(funcion, {"__builtins__": None}, allowed_names)

        resultados = []
        Xr_anterior = 0
        i = 1

        fXa = f(xa)
        fXb = f(xb)
        if fXa == 0:
            resultados.append((int(ejercicio), 1, xa, xb, fXa, fXb, xa, fXa, 0))
        elif fXb == 0:
            resultados.append((int(ejercicio), 1, xa, xb, fXa, fXb, xb, fXb, 0))
        elif fXa * fXb > 0:
            raise ValueError("Bisección requiere un intervalo inicial con cambio de signo.")

        if not resultados:
            while i <= max_iter:
                fXa = f(xa)
                fXb = f(xb)
                xr = (xa + xb) / 2
                fXr = f(xr)
                ea = 0 if i == 1 or xr == 0 else abs((xr - Xr_anterior) / xr) * 100
                resultados.append((int(ejercicio), i, xa, xb, fXa, fXb, xr, fXr, round(ea, 4)))

                if fXr == 0:
                    break
                if ea < es and i > 1:
                    break

                Xr_anterior = xr
                if fXa * fXr < 0:
                    xb = xr
                else:
                    xa = xr
                i += 1

        # Guardar resultados en MySQL
        conn = mysql.connector.connect(host="127.0.0.1", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM metodo_biseccion WHERE ejercicio = %s", (ejercicio,))
        for fila in resultados:
            cursor.execute("""
                INSERT INTO metodo_biseccion (ejercicio, iteracion, xa, xb, fxa, fxb, xr, fxr, ea)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, fila)
        conn.commit()
        cursor.close()
        conn.close()
       # 📈 Gráfica estilo GeoGebra con eje manual


        try:  
            
            x_vals = np.linspace(-55, 125, 1000)
            y_vals = [f(x) for x in x_vals]

            trace_func = go.Scatter(x=x_vals, y=y_vals, mode='lines', name=f"f(x) = {funcion}", line=dict(color='blue'))
            trace_A = go.Scatter(x=[xa_original], y=[f(xa_original)], mode='markers',  name=f"A = ({xa_original:.2f}, {f(xa_original):.3f})", marker=dict(color='red', size=10), text=[f"A = ({xa_original}, {f(xa_original):.3f})"], textposition="top center")
            trace_B = go.Scatter(x=[xb_original], y=[f(xb_original)], mode='markers',  name=f"B = ({xb_original:.2f}, {f(xb_original):.3f})", marker=dict(color='green', size=10), text=[f"B = ({xb_original}, {f(xb_original):.3f})"], textposition="top center")
            xc = (xa_original + xb_original) / 2
            trace_C = go.Scatter(
                x=[xc],
                y=[f(xc)],
                mode='markers',
                name=f"C = ({xc:.2f}, {f(xc):.3f})",
                marker=dict(color='blue', size=10)
            )            
                        
            layout = go.Layout(
                title='Gráfica del Método de Bisección',
                plot_bgcolor='white',      
                paper_bgcolor='white',    
                xaxis=dict(
                    title='x',
                    range=[-55, 125],
                    showgrid=True,
                    gridcolor='lightgray',  
                    zeroline=True,
                    zerolinecolor='black',
                    zerolinewidth=2
                ),
                yaxis=dict(
                    title='f(x)',
                    range=[-66, 81],
                    showgrid=True,
                    gridcolor='lightgray',
                    zeroline=True,
                    zerolinecolor='black',
                    zerolinewidth=2
                ),
                shapes=[
                    # Línea vertical en x = 0
                    dict(type='line', x0=0, y0=-1000, x1=0, y1=1000,
                        line=dict(color='black', width=2)),
                    # Línea horizontal en y = 0
                    dict(type='line', x0=-1000, y0=0, x1=1000, y1=0,
                        line=dict(color='black', width=2))
                ],
                showlegend=True,
                hovermode='closest'
            )



            fig = go.Figure(data=[trace_func, trace_A, trace_B, trace_C], layout=layout)

            os.makedirs("static/imagenes", exist_ok=True)
            html_path = f"static/imagenes/biseccion_{ejercicio}.html"
            pio.write_html(fig, file=html_path, auto_open=False)

        except Exception as err:
            print("Error generando grafica biseccion:", err)
            html_path = ""


        return jsonify({
            "mensaje": "Bisección guardada correctamente.",
            "imagen": "/" + html_path if html_path else ""
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@biseccion_bp.route('/resultados-biseccion')
def resultados_biseccion():
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ejercicio, iteracion, xa, xb, fxa, fxb, xr, fxr, ea
            FROM metodo_biseccion
            ORDER BY ejercicio ASC, iteracion ASC
        """)
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@biseccion_bp.route('/eliminar-biseccion/<int:ejercicio>', methods=['DELETE'])
def eliminar_biseccion(ejercicio):
    try:
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        
        # Elimina todas las filas que pertenezcan a ese ejercicio
        cursor.execute("DELETE FROM metodo_biseccion WHERE ejercicio = %s", (ejercicio,))
        
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"mensaje": "Ejercicio eliminado correctamente."})
    except Exception as e:
        return jsonify({"error": f"Error al eliminar: {str(e)}"}), 500
@biseccion_bp.route('/actualizar-biseccion', methods=['POST'])
def actualizar_biseccion():
    try:
        ej_s = (request.form.get("ejercicio") or "").strip()
        if not ej_s:
            return jsonify({"error": "Indique el número de ejercicio."}), 400
        ejercicio = int(ej_s)
        conn = mysql.connector.connect(host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM metodo_biseccion WHERE ejercicio = %s", (ejercicio,))
        existe = cursor.fetchone()[0] > 0
        cursor.close()
        conn.close()
        if not existe:
            return jsonify({"error": f"No existe el ejercicio #{ejercicio}. Primero use Calcular."}), 404

        # Vuelve a ejecutar el cálculo
        request.form = request.form.copy()
        request.form['ejercicio'] = str(ejercicio)

        return ejecutar_biseccion()

    except ValueError:
        return jsonify({"error": "Ejercicio debe ser un número entero válido."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500





@biseccion_bp.route('/buscar_ejercicio/<int:ejercicio>', methods=['GET'])
def buscar_ejercicio(ejercicio):
    try:
        conn = mysql.connector.connect(
            host="localhost", user="root", password="david98", database="metodos_numericos")
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT ejercicio, iteracion, xa, xb, fxa AS fx_xa, fxb AS fx_xb, xr, fxr AS fx_xr, ea
            FROM metodo_biseccion
            WHERE ejercicio = %s
            ORDER BY iteracion ASC
        """, (ejercicio,))
        
        resultados = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify(resultados)
    except Exception as e:
        return jsonify({"error": str(e)}), 500



