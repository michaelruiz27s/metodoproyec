// Correcciones de exportación y gráficas para métodos numéricos
(function () {
  function renderizarTablaSenl(data) {
    const tabla = document.getElementById('tabla-resultados-newton-sistemas')?.getElementsByTagName('tbody')[0];
    if (!tabla) return;
    tabla.innerHTML = '';
    data.forEach(fila => {
      const nuevaFila = tabla.insertRow();
      fila.forEach(valor => {
        const celda = nuevaFila.insertCell();
        celda.textContent = valor;
      });
    });
  }

  window.actualizarSelectSenl = function (dataExistente) {
    const procesar = (data) => {
      const ejerciciosUnicos = [...new Set(data.map(row => row[0]))];
      const select = document.getElementById('ejercicioSelectSenl');
      const iframe = document.getElementById('grafica-interactiva-senl');
      if (!select || !iframe) return;

      select.innerHTML = '';
      ejerciciosUnicos.forEach(ej => {
        const option = document.createElement('option');
        option.value = ej;
        option.textContent = `Ejercicio ${ej}`;
        select.appendChild(option);
      });

      if (ejerciciosUnicos.length > 0) {
        select.value = ejerciciosUnicos[ejerciciosUnicos.length - 1];
        window.cargarGraficaSenl();
      } else {
        iframe.src = '';
      }
    };

    if (Array.isArray(dataExistente)) {
      procesar(dataExistente);
      return;
    }

    fetch('/resultados-newton-senl')
      .then(res => res.json())
      .then(procesar)
      .catch(error => console.error('Error cargando select de SENL:', error));
  };

  window.cargarGraficaSenl = function () {
    const select = document.getElementById('ejercicioSelectSenl');
    const iframe = document.getElementById('grafica-interactiva-senl');
    if (!select || !iframe || !select.value) return;
    iframe.src = `/static/imagenes/newton_senl_${select.value}.html?t=${Date.now()}`;
  };

  window.cargarResultadosSenl = function () {
    fetch('http://127.0.0.1:5000/resultados-newton-senl')
      .then(response => response.json())
      .then(data => {
        renderizarTablaSenl(data);
        window.actualizarSelectSenl(data);
      })
      .catch(error => console.error('Error cargando resultados SENL:', error));
  };

  window.exportarTabla = function (idTabla, nombreArchivo, nombreHoja) {
    const tabla = document.getElementById(idTabla);
    if (!tabla) {
      alert('No se encontró la tabla a exportar.');
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

  window.exportarTodo = function () {
    const tablas = [
      { id: 'tabla-resultados', nombre: 'Biseccion' },
      { id: 'tabla-resultados-falsa', nombre: 'FalsaPosicion' },
      { id: 'tabla-resultados-puntofijo', nombre: 'PuntoFijo' },
      { id: 'tabla-resultados-newton', nombre: 'NewtonRaphson' },
      { id: 'tabla-resultados-secante', nombre: 'Secante' },
      { id: 'tabla-resultados-muller', nombre: 'Muller' },
      { id: 'tabla-resultados-newton-sistemas', nombre: 'NR SENL' }
    ];

    if (window.XLSX && XLSX.utils) {
      const wb = XLSX.utils.book_new();
      tablas.forEach(tablaInfo => {
        const tabla = document.getElementById(tablaInfo.id);
        if (!tabla) return;
        const ws = XLSX.utils.table_to_sheet(tabla);
        XLSX.utils.book_append_sheet(wb, ws, tablaInfo.nombre);
      });
      XLSX.writeFile(wb, 'metodos_numericos_completo.xlsx');
      return;
    }

    let contenido = '\ufeff<html><head><meta charset="UTF-8"></head><body>';
    tablas.forEach(tablaInfo => {
      const tabla = document.getElementById(tablaInfo.id);
      if (tabla) {
        contenido += `<h2>${tablaInfo.nombre}</h2>${tabla.outerHTML}<br/>`;
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

  const formSenl = document.querySelector('form[action="http://127.0.0.1:5000/newton-senl"]');
  if (formSenl) {
    formSenl.addEventListener('submit', function (event) {
      event.preventDefault();
      event.stopImmediatePropagation();

      const formData = new FormData(formSenl);
      fetch('http://127.0.0.1:5000/newton-senl', {
        method: 'POST',
        body: formData
      })
        .then(async response => {
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.error || 'Error en Newton-SENL.');
          return payload;
        })
        .then(data => {
          alert(data.mensaje || 'Calculo completado.');
          window.cargarResultadosSenl();
        })
        .catch(error => {
          console.error('Error SENL:', error);
          alert('No se pudo calcular SENL: ' + error.message);
        });
    }, true);
  }
})();
