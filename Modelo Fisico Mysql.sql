-- Esquema alineado con la app actual (Bisección, Falsa Posición y Punto Fijo).
-- Incluye Newton-Raphson (clásico/modificado/derivada numérica) en una sola tabla con campo tipo.
-- Incluye Secante, Müller, Newton para sistemas (3 variables) y Bairstow.
-- Base de datos: metodos_numericos (ajusta el nombre si usas otro).

CREATE DATABASE IF NOT EXISTS metodos_numericos;
USE metodos_numericos;

CREATE TABLE IF NOT EXISTS metodo_biseccion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ejercicio INT,
    iteracion INT,
    xa DOUBLE,
    xb DOUBLE,
    fxa DOUBLE,
    fxb DOUBLE,
    xr DOUBLE,
    fxr DOUBLE,
    ea DOUBLE
);

CREATE TABLE IF NOT EXISTS metodo_falsa_posicion (
    Id INT AUTO_INCREMENT PRIMARY KEY,
    Ejercicio INT NOT NULL,
    Iteracion INT NOT NULL,
    Xa DOUBLE,
    Xb DOUBLE,
    FXa DOUBLE,
    FXb DOUBLE,
    Xr DOUBLE,
    FXr DOUBLE,
    Ea DOUBLE
);

CREATE TABLE IF NOT EXISTS metodo_punto_fijo (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ejercicio INT NOT NULL,
    iteracion INT NOT NULL,
    xi DOUBLE,
    gxi DOUBLE,
    ea DOUBLE
);

CREATE TABLE IF NOT EXISTS metodo_newton_raphson (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ejercicio INT NOT NULL,
    tipo VARCHAR(16) NOT NULL,
    iteracion INT NOT NULL,
    xi DOUBLE,
    fxi DOUBLE,
    dfxi DOUBLE,
    xi1 DOUBLE,
    ea DOUBLE
);

CREATE TABLE IF NOT EXISTS metodo_secante (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ejercicio INT NOT NULL,
    iteracion INT NOT NULL,
    xi_1 DOUBLE,
    xi DOUBLE,
    fxi_1 DOUBLE,
    fxi DOUBLE,
    xi_t DOUBLE,
    ea DOUBLE
);

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
);

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
    ex DOUBLE,
    ey DOUBLE,
    ez DOUBLE
);

CREATE TABLE IF NOT EXISTS metodo_bairstow (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ejercicio INT NOT NULL,
    iteracion INT NOT NULL,
    r DOUBLE,
    s DOUBLE,
    dr DOUBLE,
    ds DOUBLE,
    ea DOUBLE
);
