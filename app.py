import os
from flask import Flask, send_file, send_from_directory
from Biseccion import biseccion_bp
from Falsa_Posicion import falsa_bp
from Punto_Fijo import punto_fijo_bp
from Newton_Raphson import newton_bp
from Secante import secante_bp
from Muller import muller_bp
from Newton_Sistemas import newton_sis_bp
from Bairstow import bairstow_bp
from Horner import horner_bp

basedir = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

# Rutas estáticas
@app.route('/')
def index():
    return send_file(os.path.join(basedir, "index.html"))

@app.route('/style.css')
def estilo():
    return send_from_directory(basedir, 'style.css')

@app.route('/Funciones.js')
def funciones():
    return send_from_directory(basedir, 'Funciones.js')

@app.route('/Funciones_fix.js')
def funciones_fix():
    return send_from_directory(basedir, 'Funciones_fix.js')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(basedir, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Registrar blueprints
app.register_blueprint(biseccion_bp)
app.register_blueprint(falsa_bp)
app.register_blueprint(punto_fijo_bp)
app.register_blueprint(newton_bp)
app.register_blueprint(secante_bp)
app.register_blueprint(muller_bp)
app.register_blueprint(newton_sis_bp)
app.register_blueprint(bairstow_bp)
app.register_blueprint(horner_bp)   



if __name__ == '__main__':
    app.run(debug=True)
