from flask import Flask, send_file, send_from_directory

from Biseccion import biseccion_bp
from Falsa_Posicion import falsa_bp
from Punto_Fijo import puntofijo_bp
from Newton_Raphson import newton_bp
from Secante import secante_bp
from Muller import muller_bp
from Newton_Raphson_SENL import newton_senl_bp
from Horner import horner_bp


app = Flask(__name__)


@app.route('/')
def index():
    return send_file("index.html")


@app.route('/style.css')
def estilo():
    return send_from_directory('.', 'style.css')


@app.route('/Funciones.js')
def funciones():
    return send_from_directory('.', 'Funciones.js')


@app.route('/Funciones_fix.js')
def funciones_fix():
    return send_from_directory('.', 'Funciones_fix.js')


app.register_blueprint(biseccion_bp)
app.register_blueprint(falsa_bp)
app.register_blueprint(puntofijo_bp)
app.register_blueprint(newton_bp)
app.register_blueprint(secante_bp)
app.register_blueprint(muller_bp)
app.register_blueprint(newton_senl_bp)
app.register_blueprint(horner_bp)



if __name__ == '__main__':
    app.run(debug=True)