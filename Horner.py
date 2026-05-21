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
    """Normaliza la expresión para que sea válida en Python"""
    expresion = expresion.replace(" ", "")
    
    # Reemplazos básicos
    expresion = expresion.replace("raiz", "sqrt")
    expresion = expresion.replace("sen", "sin")
    expresion = expresion.replace("ln", "log_ln_")
    expresion = expresion.replace("log(", "log10(")
    expresion = expresion.replace("log_ln_", "log")
    expresion = expresion.replace("^", "**")
    
    # Manejo de exponenciales
    expresion = re.sub(r'e\*\*(\(?[^\)\+\-\*/]+?\)?)', r'exp(\1)', expresion)
    
    # Agregar multiplicaciones implícitas
    # Entre número y variable: 6x → 6*x
    expresion = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expresion)
    
    # Entre variable/paréntesis y paréntesis: x( → x*(
    expresion = re.sub(r'([a-zA-Z\)])(\()', r'\1*\2', expresion)
    
    # Entre paréntesis/variable y variable: )x o x x
    expresion = re.sub(r'(\))([a-zA-Z])', r'\1*\2', expresion)
    
    return expresion


def polinomio_a_coeficientes(expr):
    """
    Convierte una expresión polinomial a lista de coeficientes (de mayor a menor grado).
    Ejemplo: "x^3 - 6x^2 + 11x - 6" → [1, -6, 11, -6]
    """
    try:
        expr_normalizada = _aplicar_reemplazos(expr)
        
        # Intentar con sympy primero (más robusto)
        try:
            from sympy import symbols, Poly, sympify, expand
            x = symbols('x')
            
            # Expandir y crear polinomio
            poly_expr = expand(sympify(expr_normalizada))
            poly = Poly(poly_expr, x)
            coeficientes = poly.all_coeffs()
            
            return [float(c) for c in coeficientes]
        
        except (ImportError, SyntaxError, Exception) as e:
            # Fallback si sympy falla: método manual
            print(f"Sympy falló, usando método manual. Error: {str(e)}")
            return polinomio_a_coeficientes_manual(expr_normalizada)
    
    except Exception as e:
        raise ValueError(f"Error al parsear polinomio: {str(e)}")


def polinomio_a_coeficientes_manual(expr):
    """
    Método manual para extraer coeficientes si sympy no está disponible.
    Evalúa el polinomio en varios puntos y resuelve un sistema de ecuaciones.
    """
    try:
        # Compilar la expresión
        code = compile(expr, '<expr>', 'eval')
        
        # Evaluar en varios puntos para determinar el grado
        grado = 0
        for test_x in [0, 1, -1, 2, -2]:
            try:
                val = eval(code, {"__builtins__": {}}, {"x": test_x, "sqrt": math.sqrt, "sin": math.sin, "log": math.log, "exp": math.exp})
                if val != 0:
                    grado += 1
            except:
                pass
        
        if grado == 0:
            grado = 1
        
        # Evaluar en grado+1 puntos para obtener coeficientes
        puntos = []
        for i in range(grado + 1):
            x_val = i
            y_val = eval(code, {"__builtins__": {}}, {"x": x_val, "sqrt": math.sqrt, "sin": math.sin, "log": math.log, "exp": math.exp})
            puntos.append((x_val, y_val))
        
        # Sistema de ecuaciones para extraer coeficientes
        A = np.array([[puntos[i][0]**j for j in range(grado, -1, -1)] for i in range(grado + 1)])
        b = np.array([puntos[i][1] for i in range(grado + 1)])
        
        try:
            coeficientes = np.linalg.solve(A, b)
            return coeficientes.tolist()
        except:
            raise ValueError("No se pueden extraer los coeficientes del polinomio")
    
    except Exception as e:
        raise ValueError(f"Error en método manual de coeficientes: {str(e)}")


def evaluar_polinomio(coeficientes, x):
    """Evaluación usando método de Horner"""
    resultado = coeficientes[0]
    for coef in coeficientes[1:]:
        resultado = resultado * x + coef
    return resultado


def derivada_polinomio(coeficientes, x):
    """
    Calcula la derivada del polinomio en x usando el método de Horner.
    Derivada analítica: d/dx de suma(c_i * x^(n-i)) = suma(c_i * (n-i) * x^(n-i-1))
    """
    n = len(coeficientes)
    
    # Coeficientes de la derivada
    coef_derivada = [coeficientes[i] * (n - 1 - i) for i in range(n - 1)]
    
    if len(coef_derivada) == 0:
        return 0
    
    return evaluar_polinomio(coef_derivada, x)


@horner_bp.route('/horner', methods=['POST'])
def ejecutar_horner():
    try:
        # Validación de entrada
        try:
            ejercicio = int(request.form.get('ejercicio', 0))
            if ejercicio <= 0:
                raise ValueError("El número de ejercicio debe ser un entero positivo")
        except (ValueError, TypeError) as e:
            return jsonify({"error": "Ejercicio inválido: debe ser un número positivo"}), 400
        
        polinomio_str = request.form.get('polinomio', "").strip()
        if not polinomio_str:
            return jsonify({"error": "El polinomio no puede estar vacío"}), 400
        
        try:
            x0 = float(request.form.get('x0', 0))
        except (ValueError, TypeError):
            return jsonify({"error": "x0 debe ser un número válido"}), 400
        
        try:
            es = float(request.form.get('es', 0.001))
            if es <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            return jsonify({"error": "Es (tolerancia) debe ser un número positivo"}), 400
        
        max_iter = 100

        # Convertir polinomio a coeficientes
        try:
            coeficientes = polinomio_a_coeficientes(polinomio_str)
        except Exception as e:
            return jsonify({"error": f"Error al parsear polinomio: {str(e)}"}), 400

        resultados = []
        xi = x0
        i = 1

        while i <= max_iter:
            try:
                fxi = evaluar_polinomio(coeficientes, xi)
                dfxi = derivada_polinomio(coeficientes, xi)
            except Exception as e:
                return jsonify({"error": f"Error evaluando polinomio en iteración {i}: {str(e)}"}), 400

            # Verificar que la derivada no sea cero
            if abs(dfxi) < 1e-12:
                return jsonify({"error": f"Derivada cercana a cero en iteración {i}. Prueba otro valor inicial."}), 400

            # Método de Newton
            xi_nuevo = xi - fxi / dfxi
            
            # Error absoluto relativo
            ea = abs((xi_nuevo - xi) / xi_nuevo) * 100 if xi_nuevo != 0 else abs(xi_nuevo - xi) * 100

            resultados.append((
                ejercicio, i, xi, fxi, dfxi, xi_nuevo, round(ea, 8)
            ))

            # Criterio de parada
            if ea < es and i > 1:
                break

            xi = xi_nuevo
            i += 1

        if len(resultados) == 0:
            return jsonify({"error": "No se pudo calcular ninguna iteración"}), 400

        # Guardar en BD
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="metodos_numericos"
        )
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
        html_path = ""
        try:
            # Determinar rango mejor basado en la raíz encontrada
            raiz = resultados[-1][5]
            x_min = raiz - 5
            x_max = raiz + 5
            x_vals = np.linspace(x_min, x_max, 500)
            
            y_vals = []
            for x_val in x_vals:
                try:
                    y_val = evaluar_polinomio(coeficientes, x_val)
                    # Limitar valores muy grandes para mejor visualización
                    if abs(y_val) > 1e6:
                        y_val = np.sign(y_val) * 1e6
                    y_vals.append(y_val)
                except:
                    y_vals.append(np.nan)

            y_vals = np.array(y_vals)

            trace = go.Scatter(
                x=x_vals, 
                y=y_vals, 
                mode='lines', 
                name=f'P(x)', 
                line=dict(color='blue', width=2)
            )
            
            raiz_valor = evaluar_polinomio(coeficientes, raiz)
            raiz_point = go.Scatter(
                x=[raiz], 
                y=[raiz_valor], 
                mode='markers+text',
                name=f'Raíz ≈ {raiz:.8f}',
                marker=dict(color='red', size=12, symbol='star'),
                text=[f'{raiz:.8f}'],
                textposition='top center'
            )

            fig = go.Figure(data=[trace, raiz_point])
            fig.update_layout(
                title=f'Método de Horner - Ejercicio {ejercicio} (Raíz: {raiz:.8f})',
                xaxis_title='x',
                yaxis_title='P(x)',
                plot_bgcolor='white',
                paper_bgcolor='white',
                hovermode='x unified'
            )

            os.makedirs("static/imagenes", exist_ok=True)
            html_path = f"static/imagenes/horner_{ejercicio}.html"
            pio.write_html(fig, file=html_path, auto_open=False)
            html_path = "/" + html_path
        except Exception as e:
            print(f"Error al graficar: {str(e)}")
            html_path = ""

        return jsonify({
            "mensaje": "✅ Método de Horner ejecutado correctamente.",
            "imagen": html_path,
            "iteraciones": len(resultados),
            "raiz": round(resultados[-1][5], 10)
        })

    except Exception as e:
        print(f"Error en ejecutar_horner: {str(e)}")
        return jsonify({"error": f"Error interno: {str(e)}"}), 500


# ==================== RUTAS AUXILIARES ====================

@horner_bp.route('/resultados-horner')
def ver_resultados_horner():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="metodos_numericos"
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                ejercicio,
                iteracion,
                ROUND(xi, 10) as xi,
                ROUND(fxi, 10) as fxi,
                ROUND(dfxi, 10) as dfxi,
                ROUND(xi_nuevo, 10) as xi_nuevo,
                ROUND(ea, 8) as ea
            FROM metodo_horner 
            ORDER BY ejercicio ASC, iteracion ASC
        """)
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@horner_bp.route('/buscar_ejercicio_horner/<int:ejercicio>', methods=['GET'])
def buscar_ejercicio_horner(ejercicio):
    """Obtener resultados de un ejercicio específico"""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="metodos_numericos"
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                ejercicio,
                iteracion,
                ROUND(xi, 10) as xi,
                ROUND(fxi, 10) as fxi,
                ROUND(dfxi, 10) as dfxi,
                ROUND(xi_nuevo, 10) as xi_nuevo,
                ROUND(ea, 8) as ea
            FROM metodo_horner 
            WHERE ejercicio = %s 
            ORDER BY iteracion ASC
        """, (ejercicio,))
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not filas:
            return jsonify({"error": f"No se encontraron resultados para el ejercicio {ejercicio}"}), 404
        
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@horner_bp.route('/eliminar-horner/<int:ejercicio>', methods=['DELETE'])
def eliminar_horner(ejercicio):
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="metodos_numericos"
        )
        cursor = conn.cursor()
        cursor.execute("DELETE FROM metodo_horner WHERE ejercicio = %s", (ejercicio,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"mensaje": f"Registros del ejercicio #{ejercicio} eliminados correctamente."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@horner_bp.route('/actualizar-horner', methods=['POST'])
def actualizar_horner():
    try:
        try:
            ejercicio = int(request.form.get('ejercicio', 0))
            if ejercicio <= 0:
                return jsonify({"error": "Ejercicio debe ser un número positivo"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Ejercicio debe ser un número entero válido"}), 400
        
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="metodos_numericos"
        )
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM metodo_horner WHERE ejercicio = %s", (ejercicio,))
        existe = cursor.fetchone()[0] > 0
        cursor.close()
        conn.close()
        
        if not existe:
            return jsonify({"error": f"No existe el ejercicio #{ejercicio}. Primero usa 'Calcular'."}), 404
        
        # Ejecutar nuevamente con los datos del formulario
        return ejecutar_horner()
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500