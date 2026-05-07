// Exportación Excel (fallback si XLSX falla) — Bisección, Falsa Posición y Punto Fijo
(function () {
  function avisar(mensaje, tipo) {
    if (typeof window.mostrarNotificacion === 'function') {
      window.mostrarNotificacion(mensaje, tipo || 'info');
    } else {
      alert(mensaje);
    }
  }

  function normalizarFilas(filas) {
    if (!Array.isArray(filas)) return [];
    return filas.map(fila => Array.isArray(fila) ? fila : Object.values(fila));
  }

  function generarMatrizConEncabezados(tablaId, filas) {
    const tabla = document.getElementById(tablaId);
    if (!tabla) return [];

    const headers = Array.from(tabla.querySelectorAll('thead th'))
      .map(th => th.innerText.trim());
    const data = normalizarFilas(filas);
    return [headers, ...data];
  }

  async function obtenerDatosCompletos() {
    const [resBiseccion, resFalsa, resPuntoFijo, resNewtonCla, resNewtonMod, resNewtonNum, resNewtonSis, resSecante, resMuller, resBairstow] = await Promise.all([
      fetch('/resultados-biseccion'),
      fetch('/resultados-falsa-posicion'),
      fetch('/resultados-punto-fijo'),
      fetch('/resultados-newton/CLA'),
      fetch('/resultados-newton/MOD'),
      fetch('/resultados-newton/NUM'),
      fetch('/resultados-newton-sistemas'),
      fetch('/resultados-secante'),
      fetch('/resultados-muller'),
      fetch('/resultados-bairstow')
    ]);

    if (!resBiseccion.ok || !resFalsa.ok || !resPuntoFijo.ok || !resNewtonCla.ok || !resNewtonMod.ok || !resNewtonNum.ok || !resNewtonSis.ok || !resSecante.ok || !resMuller.ok || !resBairstow.ok) {
      throw new Error('No se pudieron consultar los datos almacenados.');
    }

    const [biseccion, falsa, puntoFijo, newtonCla, newtonMod, newtonNum, newtonSis, secante, muller, bairstow] = await Promise.all([
      resBiseccion.json(),
      resFalsa.json(),
      resPuntoFijo.json(),
      resNewtonCla.json(),
      resNewtonMod.json(),
      resNewtonNum.json(),
      resNewtonSis.json(),
      resSecante.json(),
      resMuller.json(),
      resBairstow.json()
    ]);

    return {
      biseccion: normalizarFilas(biseccion),
      falsa: normalizarFilas(falsa),
      puntoFijo: normalizarFilas(puntoFijo),
      newtonCla: normalizarFilas(newtonCla),
      newtonMod: normalizarFilas(newtonMod),
      newtonNum: normalizarFilas(newtonNum),
      newtonSis: normalizarFilas(newtonSis),
      secante: normalizarFilas(secante),
      muller: normalizarFilas(muller),
      bairstow: normalizarFilas(bairstow)
    };
  }

  window.exportarTabla = function (idTabla, nombreArchivo, nombreHoja) {
    const tabla = document.getElementById(idTabla);
    if (!tabla) {
      avisar('No se encontró la tabla a exportar.', 'warning');
      return;
    }

    if (window.XLSX && XLSX.utils) {
      const wb = XLSX.utils.table_to_book(tabla, { sheet: nombreHoja });
      XLSX.writeFile(wb, nombreArchivo);
      return;
    }

    const html = `\ufeff<html><head><meta charset="UTF-8"></head><body>${tabla.outerHTML}</body></html>`;
    const blob = new Blob([html], { type: 'application/vnd.ms-excel' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = nombreArchivo.replace(/\.xlsx$/i, '.xls');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  };

  window.exportarTodo = async function () {
    let datos;
    try {
      datos = await obtenerDatosCompletos();
    } catch (error) {
      avisar(error.message || 'No se pudo exportar el Excel completo.', 'error');
      return;
    }

    const hojas = [
      {
        id: 'tabla-resultados',
        nombre: 'Biseccion',
        filas: datos.biseccion
      },
      {
        id: 'tabla-resultados-falsa',
        nombre: 'FalsaPosicion',
        filas: datos.falsa
      },
      {
        id: 'tabla-resultados-puntofijo',
        nombre: 'PuntoFijo',
        filas: datos.puntoFijo
      },
      {
        id: 'tabla-resultados-newton',
        nombre: 'Newton_CLA',
        filas: datos.newtonCla
      },
      {
        id: 'tabla-resultados-newton',
        nombre: 'Newton_MOD',
        filas: datos.newtonMod
      },
      {
        id: 'tabla-resultados-newton',
        nombre: 'Newton_NUM',
        filas: datos.newtonNum
      },
      {
        id: 'tabla-resultados-newton-sistemas',
        nombre: 'Newton_Sistemas',
        filas: datos.newtonSis
      },
      {
        id: 'tabla-resultados-secante',
        nombre: 'Secante',
        filas: datos.secante
      },
      {
        id: 'tabla-resultados-muller',
        nombre: 'Muller',
        filas: datos.muller
      },
      {
        id: 'tabla-resultados-bairstow',
        nombre: 'Bairstow',
        filas: datos.bairstow
      }
    ];

    if (window.XLSX && XLSX.utils) {
      const wb = XLSX.utils.book_new();
      hojas.forEach(({ id, nombre, filas }) => {
        const matriz = generarMatrizConEncabezados(id, filas);
        if (matriz.length === 0) return;
        const ws = XLSX.utils.aoa_to_sheet(matriz);
        XLSX.utils.book_append_sheet(wb, ws, nombre);
      });
      XLSX.writeFile(wb, 'metodos_numericos_completo.xlsx');
      return;
    }

    let contenido = '\ufeff<html><head><meta charset="UTF-8"></head><body>';
    hojas.forEach(({ id, nombre, filas }) => {
      const matriz = generarMatrizConEncabezados(id, filas);
      if (matriz.length > 0) {
        const [headers, ...rows] = matriz;
        contenido += `<h2>${nombre}</h2><table border="1"><thead><tr>`;
        headers.forEach(h => {
          contenido += `<th>${h}</th>`;
        });
        contenido += '</tr></thead><tbody>';
        rows.forEach(row => {
          contenido += '<tr>';
          row.forEach(value => {
            contenido += `<td>${value ?? ''}</td>`;
          });
          contenido += '</tr>';
        });
        contenido += '</tbody></table><br/>';
      }
    });
    contenido += '</body></html>';

    const blob = new Blob([contenido], { type: 'application/vnd.ms-excel' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'metodos_numericos_completo.xls';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  };
})();
