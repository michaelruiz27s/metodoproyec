function toggleSubmenu(id) {
  const submenu = document.getElementById(id);
  const isVisible = submenu.style.display === 'block';

  submenu.style.display = isVisible ? 'none' : 'block';
}

function mostrarNotificacion(mensaje, tipo = "info") {
  let host = document.getElementById("notificaciones-app");
  if (!host) {
    host = document.createElement("div");
    host.id = "notificaciones-app";
    host.className = "toast-host";
    document.body.appendChild(host);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${tipo}`;
  toast.textContent = mensaje;
  host.appendChild(toast);

  setTimeout(() => toast.classList.add("toast-visible"), 10);
  setTimeout(() => {
    toast.classList.remove("toast-visible");
    setTimeout(() => toast.remove(), 220);
  }, 3600);
}

function confirmarAccion(titulo, mensaje) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";

    const modal = document.createElement("div");
    modal.className = "modal-confirmacion";
    modal.innerHTML = `
      <h3>${titulo}</h3>
      <p>${mensaje}</p>
      <div class="modal-acciones">
        <button type="button" class="btn-modal btn-modal-cancelar">Cancelar</button>
        <button type="button" class="btn-modal btn-modal-confirmar">Confirmar</button>
      </div>
    `;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const cerrar = (valor) => {
      overlay.remove();
      resolve(valor);
    };

    overlay.querySelector(".btn-modal-cancelar").addEventListener("click", () => cerrar(false));
    overlay.querySelector(".btn-modal-confirmar").addEventListener("click", () => cerrar(true));
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) cerrar(false);
    });
  });
}

async function leerRespuestaServidor(response) {
  const ct = response.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return { ok: response.ok, payload: await response.json() };
  }
  const texto = await response.text();
  return { ok: response.ok, payload: texto };
}

function mensajeUsuarioActualizacion(payload) {
  if (payload && typeof payload === "object" && payload.mensaje) {
    return payload.mensaje;
  }
  if (typeof payload === "string") {
    try {
      const o = JSON.parse(payload);
      if (o && o.mensaje) return o.mensaje;
    } catch (e) { /* no es JSON */ }
    if (payload.trim().startsWith("{")) return "Datos actualizados correctamente.";
    return payload;
  }
  return "Datos actualizados correctamente.";
}

// Bisección
function cargarResultados() {
  fetch("http://127.0.0.1:5000/resultados-biseccion")
    .then(response => response.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados tbody");
      if (!tbody) return;
      tbody.innerHTML = "";
      const filas = Array.isArray(data) ? data : [];
      filas.forEach(fila => {
        const tr = document.createElement("tr");
        fila.forEach(celda => {
          const td = document.createElement("td");
          td.textContent = celda;
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    })
    .catch(error => {
      console.error("Error cargando los datos:", error);
    });
  actualizarSelect();
}

function buscarPorEjercicio(event) {
  event.preventDefault();

  const ejercicio = document.getElementById("ejercicio").value;

  if (!ejercicio) {
    mostrarNotificacion("Ingrese el número de ejercicio para buscar.", "warning");
    return;
  }

  fetch(`/buscar_ejercicio/${ejercicio}`)
    .then(response => response.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados tbody");
      tbody.innerHTML = "";

      if (data.length === 0) {
        tbody.innerHTML = "<tr><td colspan='9' style='text-align:center;'>No se encontraron resultados</td></tr>";
        return;
      }

      data.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${row.ejercicio}</td>
            <td>${row.iteracion}</td>
            <td>${row.xa}</td>
            <td>${row.xb}</td>
            <td>${row.fx_xa}</td>
            <td>${row.fx_xb}</td>
            <td>${row.xr}</td>
            <td>${row.fx_xr}</td>
            <td>${row.ea}</td>
        `;
        tbody.appendChild(tr);
      });
      const ultima = data[data.length - 1];
      document.getElementById("xa").value = ultima.xa;
      document.getElementById("xb").value = ultima.xb;
    })
    .catch(error => {
      console.error("Error al buscar el ejercicio:", error);
    });
}

document.addEventListener("DOMContentLoaded", function () {
  cargarResultados();

  const form = document.querySelector('form[action="http://127.0.0.1:5000/biseccion"]');
  if (!form) return;
  form.addEventListener("submit", function (event) {
    event.preventDefault();

    const formData = new FormData(form);
    fetch("http://127.0.0.1:5000/biseccion", {
      method: "POST",
      body: formData
    })
      .then(async response => {
        const { ok, payload } = await leerRespuestaServidor(response);
        if (!ok) {
          const mensaje = typeof payload === "string" ? payload : (payload.error || "Error en cálculo de bisección.");
          throw new Error(mensaje);
        }
        return payload;
      })
      .then(data => {
        cargarResultados();
        actualizarSelect();
        mostrarNotificacion(
          (data && data.mensaje) ? data.mensaje : "Cálculo de bisección realizado correctamente.",
          "success"
        );
      })
      .catch(error => {
        console.error("Error al enviar los datos:", error);
        mostrarNotificacion(`No se pudo calcular bisección: ${error.message}`, "error");
      });
  });
});

async function eliminarEjercicio() {
  const ejercicio = document.getElementById("ejercicio").value;

  if (!ejercicio) {
    mostrarNotificacion("Ingrese el número de ejercicio que desea eliminar.", "warning");
    return;
  }

  const confirmado = await confirmarAccion(
    "Confirmar eliminación",
    `Se eliminarán todos los registros del ejercicio #${ejercicio}. Esta acción no se puede deshacer.`
  );
  if (!confirmado) {
    return;
  }

  fetch(`http://127.0.0.1:5000/eliminar-biseccion/${ejercicio}`, {
    method: "DELETE"
  })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) {
        const msg = typeof payload === "object" && payload.error ? payload.error : "No se pudo eliminar el ejercicio.";
        throw new Error(msg);
      }
      const msg = typeof payload === "object" && payload.mensaje
        ? payload.mensaje
        : (typeof payload === "string" ? payload : "Ejercicio eliminado correctamente.");
      mostrarNotificacion(msg, "success");
      cargarResultados();
      actualizarSelect();
    })
    .catch(error => {
      console.error("Error al eliminar:", error);
      mostrarNotificacion(error.message || "No se pudieron eliminar los datos.", "error");
    });
}

function actualizarEjercicio(event) {
  if (event && event.preventDefault) event.preventDefault();
  const form = document.querySelector('form[action="http://127.0.0.1:5000/biseccion"]');
  if (!form) return;
  const formData = new FormData(form);

  fetch("http://127.0.0.1:5000/actualizar-biseccion", {
    method: "POST",
    body: formData
  })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) {
        const msg = typeof payload === "object" && payload.error ? payload.error : String(payload);
        throw new Error(msg);
      }
      mostrarNotificacion(mensajeUsuarioActualizacion(payload), "success");
      cargarResultados();
      actualizarSelect();
    })
    .catch(error => {
      console.error("Error al actualizar:", error);
      mostrarNotificacion(error.message || "No se pudo actualizar el ejercicio.", "error");
    });
}

function actualizarSelect() {
  fetch('/resultados-biseccion')
    .then(res => res.json())
    .then(data => {
      const filas = Array.isArray(data) ? data : [];
      const ejerciciosUnicos = [...new Set(filas.map(row => row[0]))];
      const select = document.getElementById('ejercicioSelect');
      if (!select) return;
      select.innerHTML = '';

      ejerciciosUnicos.forEach(ej => {
        const option = document.createElement('option');
        option.value = ej;
        option.textContent = `Ejercicio ${ej}`;
        select.appendChild(option);
      });

      if (ejerciciosUnicos.length > 0) {
        select.value = ejerciciosUnicos[ejerciciosUnicos.length - 1];
        cargarGrafica();
      } else {
        limpiarGraficaBiseccion();
      }
    })
    .catch(err => console.error("Error actualizando select bisección:", err));
}

function limpiarGraficaBiseccion() {
  const frame = document.getElementById('grafica-interactiva');
  if (!frame) return;
  frame.srcdoc = `
    <html><body style="margin:0;display:flex;align-items:center;justify-content:center;height:100%;background:#161b27;color:#8492a6;font-family:Arial,sans-serif;">
      No hay datos disponibles para mostrar la gráfica.
    </body></html>
  `;
}

function cargarGrafica() {
  const ejercicio = document.getElementById('ejercicioSelect').value;
  if (!ejercicio) {
    limpiarGraficaBiseccion();
    return;
  }
  const frame = document.getElementById('grafica-interactiva');
  frame.removeAttribute('srcdoc');
  document.getElementById('grafica-interactiva').src = `/static/imagenes/biseccion_${ejercicio}.html?t=${Date.now()}`;
}

// Falsa posición
function cargarResultadosFalsa() {
  fetch('http://127.0.0.1:5000/resultados-falsa-posicion')
    .then(response => response.json())
    .then(data => {
      const tabla = document.getElementById('tabla-resultados-falsa').getElementsByTagName('tbody')[0];
      tabla.innerHTML = '';

      data.forEach(fila => {
        const nuevaFila = tabla.insertRow();
        fila.forEach(valor => {
          const celda = nuevaFila.insertCell();
          celda.textContent = valor;
        });
      });
    })
    .catch(error => console.error('Error cargando resultados:', error));
  actualizarSelectFalsa();
}

document.addEventListener("DOMContentLoaded", function () {
  cargarResultadosFalsa();
});

document.addEventListener("DOMContentLoaded", function () {
  cargarResultadosPuntoFijo();
});

async function eliminarEjercicioFalsa(event) {
  event.preventDefault();
  const ejercicio = document.getElementById('ejercicio-falsa').value;

  if (!ejercicio) {
    mostrarNotificacion("Ingrese el número de ejercicio que desea eliminar.", "warning");
    return;
  }

  const confirmado = await confirmarAccion(
    "Confirmar eliminación",
    `Se eliminarán todos los registros del ejercicio #${ejercicio}. Esta acción no se puede deshacer.`
  );
  if (!confirmado) {
    return;
  }

  fetch(`http://127.0.0.1:5000/eliminar-falsa-posicion/${ejercicio}`, {
    method: 'DELETE'
  })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) {
        const msg = typeof payload === "object" && payload.error ? payload.error : "No se pudo eliminar el ejercicio.";
        throw new Error(msg);
      }
      const msg = typeof payload === "object" && payload.mensaje
        ? payload.mensaje
        : (typeof payload === "string" ? payload : "Ejercicio eliminado correctamente.");
      mostrarNotificacion(msg, "success");
      cargarResultadosFalsa();
      actualizarSelectFalsa();
    })
    .catch(error => {
      console.error('Error al eliminar ejercicio:', error);
      mostrarNotificacion(error.message || "No se pudieron eliminar los datos.", "error");
    });
}

function actualizarEjercicioFalsa(event) {
  event.preventDefault();
  const formData = new FormData();
  formData.append('ejercicio', document.getElementById('ejercicio-falsa').value);
  formData.append('funcion', document.getElementById('funcion-falsa').value);
  formData.append('xa', document.getElementById('xa-falsa').value);
  formData.append('xb', document.getElementById('xb-falsa').value);
  formData.append('es', document.getElementById('es-falsa').value);

  fetch('http://127.0.0.1:5000/actualizar-falsa-posicion', {
    method: 'POST',
    body: formData
  })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) {
        const msg = typeof payload === "object" && payload.error ? payload.error : String(payload);
        throw new Error(msg);
      }
      mostrarNotificacion(mensajeUsuarioActualizacion(payload), "success");
      cargarResultadosFalsa();
      actualizarSelectFalsa();
    })
    .catch(error => mostrarNotificacion(error.message || "No se pudo actualizar el ejercicio.", "error"));
}

function buscarPorEjercicioFalsa(event) {
  event.preventDefault();
  const ejercicio = document.getElementById("ejercicio-falsa").value;

  if (!ejercicio) {
    mostrarNotificacion("Ingrese el número de ejercicio para buscar.", "warning");
    return;
  }

  fetch(`/buscar_ejercicio_falsa/${ejercicio}`)
    .then(response => response.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-falsa tbody");
      tbody.innerHTML = "";

      if (data.length === 0) {
        tbody.innerHTML = "<tr><td colspan='9' style='text-align:center;'>No se encontraron resultados</td></tr>";
        return;
      }

      data.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.ejercicio}</td>
          <td>${row.iteracion}</td>
          <td>${row.xa}</td>
          <td>${row.xb}</td>
          <td>${row.fxa}</td>
          <td>${row.fxb}</td>
          <td>${row.xr}</td>
          <td>${row.fxr}</td>
          <td>${row.ea}</td>
        `;
        tbody.appendChild(tr);
      });
      const ultima = data[data.length - 1];
      document.getElementById("xa-falsa").value = ultima.xa;
      document.getElementById("xb-falsa").value = ultima.xb;
    });
}

function actualizarSelectFalsa() {
  fetch('/resultados-falsa-posicion')
    .then(res => res.json())
    .then(data => {
      const ejerciciosUnicos = [...new Set(data.map(row => row[0]))];
      const select = document.getElementById('ejercicioSelectFalsa');
      select.innerHTML = '';

      ejerciciosUnicos.forEach(ej => {
        const option = document.createElement('option');
        option.value = ej;
        option.textContent = `Ejercicio ${ej}`;
        select.appendChild(option);
      });

      if (ejerciciosUnicos.length > 0) {
        select.value = ejerciciosUnicos[ejerciciosUnicos.length - 1];
        cargarGraficaFalsa();
      } else {
        limpiarGraficaFalsa();
      }
    });
}

function limpiarGraficaFalsa() {
  const frame = document.getElementById('grafica-interactiva-falsa');
  if (!frame) return;
  frame.srcdoc = `
    <html><body style="margin:0;display:flex;align-items:center;justify-content:center;height:100%;background:#161b27;color:#8492a6;font-family:Arial,sans-serif;">
      No hay datos disponibles para mostrar la gráfica.
    </body></html>
  `;
}

function cargarGraficaFalsa() {
  const ejercicio = document.getElementById('ejercicioSelectFalsa').value;
  if (!ejercicio) {
    limpiarGraficaFalsa();
    return;
  }
  const frame = document.getElementById('grafica-interactiva-falsa');
  frame.removeAttribute('srcdoc');
  document.getElementById('grafica-interactiva-falsa').src = `/static/imagenes/falsa_posicion_${ejercicio}.html?t=${Date.now()}`;
}

// Punto fijo
function cargarResultadosPuntoFijo() {
  fetch('http://127.0.0.1:5000/resultados-punto-fijo')
    .then(response => response.json())
    .then(data => {
      const tabla = document.getElementById('tabla-resultados-puntofijo').getElementsByTagName('tbody')[0];
      tabla.innerHTML = '';
      data.forEach(fila => {
        const nuevaFila = tabla.insertRow();
        fila.forEach(valor => {
          const celda = nuevaFila.insertCell();
          celda.textContent = valor;
        });
      });
    })
    .catch(error => console.error('Error cargando resultados de punto fijo:', error));
  actualizarSelectPuntoFijo();
}

function buscarPorEjercicioPuntoFijo(event) {
  event.preventDefault();
  const ejercicio = document.getElementById("ejercicio-pf").value;
  if (!ejercicio) {
    mostrarNotificacion("Ingrese el número de ejercicio para buscar.", "warning");
    return;
  }

  fetch(`/buscar_ejercicio_punto_fijo/${ejercicio}`)
    .then(response => response.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-puntofijo tbody");
      tbody.innerHTML = "";
      if (data.length === 0) {
        tbody.innerHTML = "<tr><td colspan='5' style='text-align:center;'>No se encontraron resultados</td></tr>";
        return;
      }
      data.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.ejercicio}</td>
          <td>${row.iteracion}</td>
          <td>${row.xi}</td>
          <td>${row.gxi}</td>
          <td>${row.ea}</td>
        `;
        tbody.appendChild(tr);
      });
      const ultima = data[data.length - 1];
      document.getElementById("xi-pf").value = ultima.xi;
    })
    .catch(error => {
      console.error("Error al buscar ejercicio de punto fijo:", error);
      mostrarNotificacion("No se pudo buscar el ejercicio de punto fijo.", "error");
    });
}

async function eliminarEjercicioPuntoFijo(event) {
  event.preventDefault();
  const ejercicio = document.getElementById('ejercicio-pf').value;
  if (!ejercicio) {
    mostrarNotificacion("Ingrese el número de ejercicio que desea eliminar.", "warning");
    return;
  }
  const confirmado = await confirmarAccion(
    "Confirmar eliminación",
    `Se eliminarán todos los registros del ejercicio #${ejercicio}. Esta acción no se puede deshacer.`
  );
  if (!confirmado) return;

  fetch(`http://127.0.0.1:5000/eliminar-punto-fijo/${ejercicio}`, { method: 'DELETE' })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) {
        const msg = typeof payload === "object" && payload.error ? payload.error : "No se pudo eliminar el ejercicio.";
        throw new Error(msg);
      }
      const msg = typeof payload === "object" && payload.mensaje
        ? payload.mensaje
        : (typeof payload === "string" ? payload : "Ejercicio eliminado correctamente.");
      mostrarNotificacion(msg, "success");
      cargarResultadosPuntoFijo();
      actualizarSelectPuntoFijo();
    })
    .catch(error => mostrarNotificacion(error.message || "No se pudieron eliminar los datos.", "error"));
}

function actualizarEjercicioPuntoFijo(event) {
  event.preventDefault();
  const formData = new FormData();
  formData.append('ejercicio', document.getElementById('ejercicio-pf').value);
  formData.append('funcion', document.getElementById('funcion-pf').value);
  formData.append('xi', document.getElementById('xi-pf').value);
  formData.append('es', document.getElementById('es-pf').value);

  fetch('http://127.0.0.1:5000/actualizar-punto-fijo', {
    method: 'POST',
    body: formData
  })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) {
        const msg = typeof payload === "object" && payload.error ? payload.error : String(payload);
        throw new Error(msg);
      }
      mostrarNotificacion(mensajeUsuarioActualizacion(payload), "success");
      cargarResultadosPuntoFijo();
      actualizarSelectPuntoFijo();
    })
    .catch(error => mostrarNotificacion(error.message || "No se pudo actualizar el ejercicio.", "error"));
}

function actualizarSelectPuntoFijo() {
  fetch('/resultados-punto-fijo')
    .then(res => res.json())
    .then(data => {
      const ejerciciosUnicos = [...new Set(data.map(row => row[0]))];
      const select = document.getElementById('ejercicioSelectPuntoFijo');
      select.innerHTML = '';

      ejerciciosUnicos.forEach(ej => {
        const option = document.createElement('option');
        option.value = ej;
        option.textContent = `Ejercicio ${ej}`;
        select.appendChild(option);
      });

      if (ejerciciosUnicos.length > 0) {
        select.value = ejerciciosUnicos[ejerciciosUnicos.length - 1];
        cargarGraficaPuntoFijo();
      } else {
        limpiarGraficaPuntoFijo();
      }
    });
}

function limpiarGraficaPuntoFijo() {
  const frame = document.getElementById('grafica-interactiva-puntofijo');
  if (!frame) return;
  frame.srcdoc = `
    <html><body style="margin:0;display:flex;align-items:center;justify-content:center;height:100%;background:#161b27;color:#8492a6;font-family:Arial,sans-serif;">
      No hay datos disponibles para mostrar la gráfica.
    </body></html>
  `;
}

function cargarGraficaPuntoFijo() {
  const ejercicio = document.getElementById('ejercicioSelectPuntoFijo').value;
  if (!ejercicio) {
    limpiarGraficaPuntoFijo();
    return;
  }
  const frame = document.getElementById('grafica-interactiva-puntofijo');
  frame.removeAttribute('srcdoc');
  frame.src = `/static/imagenes/punto_fijo_${ejercicio}.html?t=${Date.now()}`;
}

// Newton-Raphson
function obtenerTipoNewton() {
  const sel = document.getElementById("newtonTipo");
  return sel ? sel.value : "CLA";
}

function cambiarTipoNewton() {
  const tipo = obtenerTipoNewton();
  const form = document.getElementById("form-newton");
  const grupoDer = document.getElementById("grupo-derivada-newton");

  if (form) {
    const action = (tipo === "CLA")
      ? "http://127.0.0.1:5000/newton-clasico"
      : (tipo === "MOD"
        ? "http://127.0.0.1:5000/newton-modificado"
        : "http://127.0.0.1:5000/newton-numerico");
    form.setAttribute("action", action);
  }

  if (grupoDer) {
    grupoDer.style.display = (tipo === "NUM") ? "none" : "block";
  }

  cargarResultadosNewton();
}

function limpiarGraficaNewton() {
  const frame = document.getElementById('grafica-interactiva-newton');
  if (!frame) return;
  frame.srcdoc = `
    <html><body style="margin:0;display:flex;align-items:center;justify-content:center;height:100%;background:#161b27;color:#8492a6;font-family:Arial,sans-serif;">
      No hay datos disponibles para mostrar la gráfica.
    </body></html>
  `;
}

function cargarGraficaNewton() {
  const tipo = obtenerTipoNewton().toLowerCase();
  const ejercicio = document.getElementById('ejercicioSelectNewton')?.value;
  if (!ejercicio) {
    limpiarGraficaNewton();
    return;
  }
  const frame = document.getElementById('grafica-interactiva-newton');
  if (!frame) return;
  frame.removeAttribute('srcdoc');
  frame.src = `/static/imagenes/newton_${tipo}_${ejercicio}.html?t=${Date.now()}`;
}

function actualizarSelectNewton() {
  const tipo = obtenerTipoNewton();
  fetch(`/resultados-newton/${tipo}`)
    .then(res => res.json())
    .then(data => {
      const ejerciciosUnicos = [...new Set((data || []).map(row => row[0]))];
      const select = document.getElementById('ejercicioSelectNewton');
      if (!select) return;
      select.innerHTML = '';

      ejerciciosUnicos.forEach(ej => {
        const option = document.createElement('option');
        option.value = ej;
        option.textContent = `Ejercicio ${ej}`;
        select.appendChild(option);
      });

      if (ejerciciosUnicos.length > 0) {
        select.value = ejerciciosUnicos[ejerciciosUnicos.length - 1];
        cargarGraficaNewton();
      } else {
        limpiarGraficaNewton();
      }
    });
}

function cargarResultadosNewton() {
  const tipo = obtenerTipoNewton();
  fetch(`http://127.0.0.1:5000/resultados-newton/${tipo}`)
    .then(res => res.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-newton tbody");
      if (!tbody) return;
      tbody.innerHTML = "";
      (data || []).forEach(fila => {
        const tr = document.createElement("tr");
        fila.forEach(celda => {
          const td = document.createElement("td");
          td.textContent = celda;
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    })
    .catch(err => console.error("Error cargando Newton:", err));
  actualizarSelectNewton();
}

function buscarPorEjercicioNewton(event) {
  event.preventDefault();
  const tipo = obtenerTipoNewton();
  const ejercicio = document.getElementById("ejercicio-newton").value;
  if (!ejercicio) {
    mostrarNotificacion("Ingrese el número de ejercicio para buscar.", "warning");
    return;
  }

  fetch(`/buscar_ejercicio_newton/${tipo}/${ejercicio}`)
    .then(res => res.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-newton tbody");
      tbody.innerHTML = "";

      if (!Array.isArray(data) || data.length === 0) {
        tbody.innerHTML = "<tr><td colspan='7' style='text-align:center;'>No se encontraron resultados</td></tr>";
        return;
      }

      data.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.ejercicio}</td>
          <td>${row.iteracion}</td>
          <td>${row.xi}</td>
          <td>${row.fxi}</td>
          <td>${row.dfxi}</td>
          <td>${row.xi1}</td>
          <td>${row.ea}</td>
        `;
        tbody.appendChild(tr);
      });
    })
    .catch(err => {
      console.error("Error buscar Newton:", err);
      mostrarNotificacion("No se pudo buscar el ejercicio.", "error");
    });
}

async function eliminarEjercicioNewton(event) {
  event.preventDefault();
  const tipo = obtenerTipoNewton();
  const ejercicio = document.getElementById("ejercicio-newton").value;
  if (!ejercicio) {
    mostrarNotificacion("Ingrese el número de ejercicio que desea eliminar.", "warning");
    return;
  }

  const confirmado = await confirmarAccion(
    "Confirmar eliminación",
    `Se eliminarán todos los registros del ejercicio #${ejercicio}. Esta acción no se puede deshacer.`
  );
  if (!confirmado) return;

  fetch(`http://127.0.0.1:5000/eliminar-newton/${tipo}/${ejercicio}`, { method: "DELETE" })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) throw new Error(payload?.error || "No se pudo eliminar el ejercicio.");
      mostrarNotificacion(payload?.mensaje || "Ejercicio eliminado correctamente.", "success");
      cargarResultadosNewton();
    })
    .catch(err => mostrarNotificacion(err.message || "No se pudo eliminar.", "error"));
}

function actualizarEjercicioNewton(event) {
  event.preventDefault();
  const tipo = obtenerTipoNewton();
  const formData = new FormData();
  formData.append("ejercicio", document.getElementById("ejercicio-newton").value);
  formData.append("funcion", document.getElementById("funcion-newton").value);
  formData.append("derivada", document.getElementById("derivada-newton")?.value || "");
  formData.append("xi", document.getElementById("xi-newton").value);
  formData.append("es", document.getElementById("es-newton").value);

  fetch(`http://127.0.0.1:5000/actualizar-newton/${tipo}`, { method: "POST", body: formData })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) throw new Error(payload?.error || "No se pudo actualizar.");
      mostrarNotificacion(payload?.mensaje || "Actualización completada.", "success");
      cargarResultadosNewton();
    })
    .catch(err => mostrarNotificacion(err.message || "No se pudo actualizar.", "error"));
}

const formNewton = document.getElementById("form-newton");
if (formNewton) {
  formNewton.addEventListener("submit", function (event) {
    event.preventDefault();
    const tipo = obtenerTipoNewton();
    const endpoint = (tipo === "CLA")
      ? "http://127.0.0.1:5000/newton-clasico"
      : (tipo === "MOD"
        ? "http://127.0.0.1:5000/newton-modificado"
        : "http://127.0.0.1:5000/newton-numerico");

    const formData = new FormData(formNewton);
    fetch(endpoint, { method: "POST", body: formData })
      .then(leerRespuestaServidor)
      .then(({ ok, payload }) => {
        if (!ok) throw new Error(payload?.error || "No se pudo calcular.");
        mostrarNotificacion(payload?.mensaje || "Cálculo completado.", "success");
        cargarResultadosNewton();
      })
      .catch(err => mostrarNotificacion(err.message || "No se pudo calcular.", "error"));
  });
}

const formPuntoFijo = document.querySelector('form[action="http://127.0.0.1:5000/punto-fijo"]');
if (formPuntoFijo) {
  formPuntoFijo.addEventListener("submit", function (event) {
    event.preventDefault();
    const formData = new FormData(formPuntoFijo);
    fetch("http://127.0.0.1:5000/punto-fijo", {
      method: "POST",
      body: formData
    })
      .then(leerRespuestaServidor)
      .then(({ ok, payload }) => {
        if (!ok) {
          const msg = typeof payload === "object" && payload.error ? payload.error : "No se pudo calcular punto fijo.";
          throw new Error(msg);
        }
        mostrarNotificacion(
          (payload && payload.mensaje) ? payload.mensaje : "Cálculo de punto fijo realizado correctamente.",
          "success"
        );
        cargarResultadosPuntoFijo();
        actualizarSelectPuntoFijo();
      })
      .catch(error => mostrarNotificacion(error.message || "No se pudo calcular punto fijo.", "error"));
  });
}

// -------- Newton sistemas (3 variables)
function limpiarGraficaNewtonSistemas() {
  const frame = document.getElementById('grafica-interactiva-newton-sistemas');
  if (!frame) return;
  frame.srcdoc = `
    <html><body style="margin:0;display:flex;align-items:center;justify-content:center;height:100%;background:#161b27;color:#8492a6;font-family:Arial,sans-serif;">
      No hay datos disponibles para mostrar la gráfica.
    </body></html>
  `;
}

function cargarGraficaNewtonSistemas() {
  const ejercicio = document.getElementById('ejercicioSelectNewtonSistemas')?.value;
  if (!ejercicio) {
    limpiarGraficaNewtonSistemas();
    return;
  }
  const frame = document.getElementById('grafica-interactiva-newton-sistemas');
  if (!frame) return;
  frame.removeAttribute('srcdoc');
  frame.src = `/static/imagenes/newton_sistemas_${ejercicio}.html?t=${Date.now()}`;
}

function actualizarSelectNewtonSistemas() {
  fetch('/resultados-newton-sistemas')
    .then(r => r.json())
    .then(data => {
      const ejercicios = [...new Set((data || []).map(row => row[0]))];
      const sel = document.getElementById('ejercicioSelectNewtonSistemas');
      if (!sel) return;
      sel.innerHTML = '';
      ejercicios.forEach(ej => {
        const o = document.createElement('option');
        o.value = ej;
        o.textContent = `Ejercicio ${ej}`;
        sel.appendChild(o);
      });
      if (ejercicios.length > 0) {
        sel.value = ejercicios[ejercicios.length - 1];
        cargarGraficaNewtonSistemas();
      } else {
        limpiarGraficaNewtonSistemas();
      }
    });
}

function cargarResultadosNewtonSistemas() {
  fetch('http://127.0.0.1:5000/resultados-newton-sistemas')
    .then(r => r.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-newton-sistemas tbody");
      if (!tbody) return;
      tbody.innerHTML = "";
      (data || []).forEach(fila => {
        const tr = document.createElement("tr");
        fila.forEach(c => {
          const td = document.createElement("td");
          td.textContent = c;
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    })
    .catch(err => console.error("Error Newton sistemas:", err));
  actualizarSelectNewtonSistemas();
}

function buscarPorEjercicioNewtonSistemas(event) {
  event.preventDefault();
  const ejercicio = document.getElementById("ejercicio-ns")?.value;
  if (!ejercicio) {
    mostrarNotificacion("Ingrese el número de ejercicio para buscar.", "warning");
    return;
  }
  fetch(`/buscar_ejercicio_newton_sistemas/${ejercicio}`)
    .then(r => r.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-newton-sistemas tbody");
      tbody.innerHTML = "";
      if (!Array.isArray(data) || data.length === 0) {
        tbody.innerHTML = "<tr><td colspan='11' style='text-align:center;'>No se encontraron resultados</td></tr>";
        return;
      }
      data.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.ejercicio}</td><td>${row.iteracion}</td>
          <td>${row.x}</td><td>${row.y}</td><td>${row.z}</td>
          <td>${row.fx}</td><td>${row.fy}</td><td>${row.fz}</td>
          <td>${row.ex}</td><td>${row.ey}</td><td>${row.ez}</td>
        `;
        tbody.appendChild(tr);
      });
    })
    .catch(() => mostrarNotificacion("No se pudo buscar el ejercicio.", "error"));
}

async function eliminarEjercicioNewtonSistemas(event) {
  event.preventDefault();
  const ejercicio = document.getElementById("ejercicio-ns")?.value;
  if (!ejercicio) {
    mostrarNotificacion("Ingrese el número de ejercicio que desea eliminar.", "warning");
    return;
  }
  const ok = await confirmarAccion("Confirmar eliminación", `Se eliminarán los registros del ejercicio #${ejercicio}.`);
  if (!ok) return;
  fetch(`http://127.0.0.1:5000/eliminar-newton-sistemas/${ejercicio}`, { method: "DELETE" })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) throw new Error(payload?.error || "No se pudo eliminar.");
      mostrarNotificacion(payload?.mensaje || "Eliminado.", "success");
      cargarResultadosNewtonSistemas();
    })
    .catch(err => mostrarNotificacion(err.message || "No se pudo eliminar.", "error"));
}

function actualizarEjercicioNewtonSistemas(event) {
  event.preventDefault();
  const form = document.getElementById("form-newton-sistemas");
  if (!form) return;
  const formData = new FormData(form);
  fetch("http://127.0.0.1:5000/actualizar-newton-sistemas", { method: "POST", body: formData })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) throw new Error(payload?.error || "No se pudo actualizar.");
      mostrarNotificacion(payload?.mensaje || "Actualizado.", "success");
      cargarResultadosNewtonSistemas();
    })
    .catch(err => mostrarNotificacion(err.message || "No se pudo actualizar.", "error"));
}

const formNewtonSistemas = document.getElementById("form-newton-sistemas");
if (formNewtonSistemas) {
  formNewtonSistemas.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(formNewtonSistemas);
    fetch("http://127.0.0.1:5000/newton-sistemas", { method: "POST", body: formData })
      .then(leerRespuestaServidor)
      .then(({ ok, payload }) => {
        if (!ok) throw new Error(payload?.error || "No se pudo calcular.");
        mostrarNotificacion(payload?.mensaje || "Cálculo completado.", "success");
        cargarResultadosNewtonSistemas();
      })
      .catch(err => mostrarNotificacion(err.message || "No se pudo calcular.", "error"));
  });
}

// -------- Secante
function limpiarGraficaSecante() {
  const frame = document.getElementById('grafica-interactiva-secante');
  if (!frame) return;
  frame.srcdoc = `
    <html><body style="margin:0;display:flex;align-items:center;justify-content:center;height:100%;background:#161b27;color:#8492a6;font-family:Arial,sans-serif;">
      No hay datos disponibles para mostrar la gráfica.
    </body></html>
  `;
}

function cargarGraficaSecante() {
  const ejercicio = document.getElementById('ejercicioSelectSecante')?.value;
  if (!ejercicio) return limpiarGraficaSecante();
  const frame = document.getElementById('grafica-interactiva-secante');
  frame.removeAttribute('srcdoc');
  frame.src = `/static/imagenes/secante_${ejercicio}.html?t=${Date.now()}`;
}

function actualizarSelectSecante() {
  fetch('/resultados-secante')
    .then(r => r.json())
    .then(data => {
      const ejercicios = [...new Set((data || []).map(row => row[0]))];
      const sel = document.getElementById('ejercicioSelectSecante');
      if (!sel) return;
      sel.innerHTML = '';
      ejercicios.forEach(ej => {
        const o = document.createElement('option');
        o.value = ej; o.textContent = `Ejercicio ${ej}`;
        sel.appendChild(o);
      });
      if (ejercicios.length) { sel.value = ejercicios[ejercicios.length - 1]; cargarGraficaSecante(); }
      else limpiarGraficaSecante();
    });
}

function cargarResultadosSecante() {
  fetch('http://127.0.0.1:5000/resultados-secante')
    .then(r => r.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-secante tbody");
      if (!tbody) return;
      tbody.innerHTML = "";
      (data || []).forEach(fila => {
        const tr = document.createElement("tr");
        fila.forEach(c => { const td = document.createElement("td"); td.textContent = c; tr.appendChild(td); });
        tbody.appendChild(tr);
      });
    })
    .catch(err => console.error("Error Secante:", err));
  actualizarSelectSecante();
}

function buscarPorEjercicioSecante(event) {
  event.preventDefault();
  const ejercicio = document.getElementById("ej-sec")?.value;
  if (!ejercicio) return mostrarNotificacion("Ingrese el número de ejercicio para buscar.", "warning");
  fetch(`/buscar_ejercicio_secante/${ejercicio}`)
    .then(r => r.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-secante tbody");
      tbody.innerHTML = "";
      if (!Array.isArray(data) || data.length === 0) {
        tbody.innerHTML = "<tr><td colspan='8' style='text-align:center;'>No se encontraron resultados</td></tr>";
        return;
      }
      data.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.ejercicio}</td><td>${row.iteracion}</td>
          <td>${row.xi_1}</td><td>${row.xi}</td><td>${row.fxi_1}</td><td>${row.fxi}</td>
          <td>${row.xi_t}</td><td>${row.ea}</td>
        `;
        tbody.appendChild(tr);
      });
    })
    .catch(() => mostrarNotificacion("No se pudo buscar el ejercicio.", "error"));
}

async function eliminarEjercicioSecante(event) {
  event.preventDefault();
  const ejercicio = document.getElementById("ej-sec")?.value;
  if (!ejercicio) return mostrarNotificacion("Ingrese el número de ejercicio que desea eliminar.", "warning");
  const ok = await confirmarAccion("Confirmar eliminación", `Se eliminarán los registros del ejercicio #${ejercicio}.`);
  if (!ok) return;
  fetch(`http://127.0.0.1:5000/eliminar-secante/${ejercicio}`, { method: "DELETE" })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) throw new Error(payload?.error || "No se pudo eliminar.");
      mostrarNotificacion(payload?.mensaje || "Eliminado.", "success");
      cargarResultadosSecante();
    })
    .catch(err => mostrarNotificacion(err.message || "No se pudo eliminar.", "error"));
}

function actualizarEjercicioSecante(event) {
  event.preventDefault();
  const form = document.getElementById("form-secante");
  if (!form) return;
  const formData = new FormData(form);
  fetch("http://127.0.0.1:5000/actualizar-secante", { method: "POST", body: formData })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) throw new Error(payload?.error || "No se pudo actualizar.");
      mostrarNotificacion(payload?.mensaje || "Actualizado.", "success");
      cargarResultadosSecante();
    })
    .catch(err => mostrarNotificacion(err.message || "No se pudo actualizar.", "error"));
}

const formSecante = document.getElementById("form-secante");
if (formSecante) {
  formSecante.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(formSecante);
    fetch("http://127.0.0.1:5000/secante", { method: "POST", body: formData })
      .then(leerRespuestaServidor)
      .then(({ ok, payload }) => {
        if (!ok) throw new Error(payload?.error || "No se pudo calcular.");
        mostrarNotificacion(payload?.mensaje || "Cálculo completado.", "success");
        cargarResultadosSecante();
      })
      .catch(err => mostrarNotificacion(err.message || "No se pudo calcular.", "error"));
  });
}

// -------- Müller
function limpiarGraficaMuller() {
  const frame = document.getElementById('grafica-interactiva-muller');
  if (!frame) return;
  frame.srcdoc = `
    <html><body style="margin:0;display:flex;align-items:center;justify-content:center;height:100%;background:#161b27;color:#8492a6;font-family:Arial,sans-serif;">
      No hay datos disponibles para mostrar la gráfica.
    </body></html>
  `;
}

function cargarGraficaMuller() {
  const ejercicio = document.getElementById('ejercicioSelectMuller')?.value;
  if (!ejercicio) return limpiarGraficaMuller();
  const frame = document.getElementById('grafica-interactiva-muller');
  frame.removeAttribute('srcdoc');
  frame.src = `/static/imagenes/muller_${ejercicio}.html?t=${Date.now()}`;
}

function actualizarSelectMuller() {
  fetch('/resultados-muller')
    .then(r => r.json())
    .then(data => {
      const ejercicios = [...new Set((data || []).map(row => row[0]))];
      const sel = document.getElementById('ejercicioSelectMuller');
      if (!sel) return;
      sel.innerHTML = '';
      ejercicios.forEach(ej => {
        const o = document.createElement('option');
        o.value = ej; o.textContent = `Ejercicio ${ej}`;
        sel.appendChild(o);
      });
      if (ejercicios.length) { sel.value = ejercicios[ejercicios.length - 1]; cargarGraficaMuller(); }
      else limpiarGraficaMuller();
    });
}

function cargarResultadosMuller() {
  fetch('http://127.0.0.1:5000/resultados-muller')
    .then(r => r.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-muller tbody");
      if (!tbody) return;
      tbody.innerHTML = "";
      (data || []).forEach(fila => {
        const tr = document.createElement("tr");
        fila.forEach(c => { const td = document.createElement("td"); td.textContent = c; tr.appendChild(td); });
        tbody.appendChild(tr);
      });
    })
    .catch(err => console.error("Error Muller:", err));
  actualizarSelectMuller();
}

function buscarPorEjercicioMuller(event) {
  event.preventDefault();
  const ejercicio = document.getElementById("ej-mul")?.value;
  if (!ejercicio) return mostrarNotificacion("Ingrese el número de ejercicio para buscar.", "warning");
  fetch(`/buscar_ejercicio_muller/${ejercicio}`)
    .then(r => r.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-muller tbody");
      tbody.innerHTML = "";
      if (!Array.isArray(data) || data.length === 0) {
        tbody.innerHTML = "<tr><td colspan='8' style='text-align:center;'>No se encontraron resultados</td></tr>";
        return;
      }
      data.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.ejercicio}</td><td>${row.iteracion}</td>
          <td>${row.x0}</td><td>${row.x1}</td><td>${row.x2}</td><td>${row.x3}</td>
          <td>${row.fx3}</td><td>${row.ea}</td>
        `;
        tbody.appendChild(tr);
      });
    })
    .catch(() => mostrarNotificacion("No se pudo buscar el ejercicio.", "error"));
}

async function eliminarEjercicioMuller(event) {
  event.preventDefault();
  const ejercicio = document.getElementById("ej-mul")?.value;
  if (!ejercicio) return mostrarNotificacion("Ingrese el número de ejercicio que desea eliminar.", "warning");
  const ok = await confirmarAccion("Confirmar eliminación", `Se eliminarán los registros del ejercicio #${ejercicio}.`);
  if (!ok) return;
  fetch(`http://127.0.0.1:5000/eliminar-muller/${ejercicio}`, { method: "DELETE" })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) throw new Error(payload?.error || "No se pudo eliminar.");
      mostrarNotificacion(payload?.mensaje || "Eliminado.", "success");
      cargarResultadosMuller();
    })
    .catch(err => mostrarNotificacion(err.message || "No se pudo eliminar.", "error"));
}

function actualizarEjercicioMuller(event) {
  event.preventDefault();
  const form = document.getElementById("form-muller");
  if (!form) return;
  const formData = new FormData(form);
  fetch("http://127.0.0.1:5000/actualizar-muller", { method: "POST", body: formData })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) throw new Error(payload?.error || "No se pudo actualizar.");
      mostrarNotificacion(payload?.mensaje || "Actualizado.", "success");
      cargarResultadosMuller();
    })
    .catch(err => mostrarNotificacion(err.message || "No se pudo actualizar.", "error"));
}

const formMuller = document.getElementById("form-muller");
if (formMuller) {
  formMuller.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(formMuller);
    fetch("http://127.0.0.1:5000/muller", { method: "POST", body: formData })
      .then(leerRespuestaServidor)
      .then(({ ok, payload }) => {
        if (!ok) throw new Error(payload?.error || "No se pudo calcular.");
        mostrarNotificacion(payload?.mensaje || "Cálculo completado.", "success");
        cargarResultadosMuller();
      })
      .catch(err => mostrarNotificacion(err.message || "No se pudo calcular.", "error"));
  });
}

// -------- Bairstow
function limpiarGraficaBairstow() {
  const frame = document.getElementById('grafica-interactiva-bairstow');
  if (!frame) return;
  frame.srcdoc = `
    <html><body style="margin:0;display:flex;align-items:center;justify-content:center;height:100%;background:#161b27;color:#8492a6;font-family:Arial,sans-serif;">
      No hay datos disponibles para mostrar la gráfica.
    </body></html>
  `;
}

function cargarGraficaBairstow() {
  const ejercicio = document.getElementById('ejercicioSelectBairstow')?.value;
  if (!ejercicio) return limpiarGraficaBairstow();
  const frame = document.getElementById('grafica-interactiva-bairstow');
  frame.removeAttribute('srcdoc');
  frame.src = `/static/imagenes/bairstow_${ejercicio}.html?t=${Date.now()}`;
}

function actualizarSelectBairstow() {
  fetch('/resultados-bairstow')
    .then(r => r.json())
    .then(data => {
      const ejercicios = [...new Set((data || []).map(row => row[0]))];
      const sel = document.getElementById('ejercicioSelectBairstow');
      if (!sel) return;
      sel.innerHTML = '';
      ejercicios.forEach(ej => {
        const o = document.createElement('option');
        o.value = ej; o.textContent = `Ejercicio ${ej}`;
        sel.appendChild(o);
      });
      if (ejercicios.length) { sel.value = ejercicios[ejercicios.length - 1]; cargarGraficaBairstow(); }
      else limpiarGraficaBairstow();
    });
}

function cargarResultadosBairstow() {
  fetch('http://127.0.0.1:5000/resultados-bairstow')
    .then(r => r.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-bairstow tbody");
      if (!tbody) return;
      tbody.innerHTML = "";
      (data || []).forEach(fila => {
        const tr = document.createElement("tr");
        fila.forEach(c => { const td = document.createElement("td"); td.textContent = c; tr.appendChild(td); });
        tbody.appendChild(tr);
      });
    })
    .catch(err => console.error("Error Bairstow:", err));
  actualizarSelectBairstow();
}

function buscarPorEjercicioBairstow(event) {
  event.preventDefault();
  const ejercicio = document.getElementById("ej-bai")?.value;
  if (!ejercicio) return mostrarNotificacion("Ingrese el número de ejercicio para buscar.", "warning");
  fetch(`/buscar_ejercicio_bairstow/${ejercicio}`)
    .then(r => r.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-bairstow tbody");
      tbody.innerHTML = "";
      if (!Array.isArray(data) || data.length === 0) {
        tbody.innerHTML = "<tr><td colspan='7' style='text-align:center;'>No se encontraron resultados</td></tr>";
        return;
      }
      data.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.ejercicio}</td><td>${row.iteracion}</td><td>${row.r}</td><td>${row.s}</td>
          <td>${row.dr}</td><td>${row.ds}</td><td>${row.ea}</td>
        `;
        tbody.appendChild(tr);
      });
    })
    .catch(() => mostrarNotificacion("No se pudo buscar el ejercicio.", "error"));
}

async function eliminarEjercicioBairstow(event) {
  event.preventDefault();
  const ejercicio = document.getElementById("ej-bai")?.value;
  if (!ejercicio) return mostrarNotificacion("Ingrese el número de ejercicio que desea eliminar.", "warning");
  const ok = await confirmarAccion("Confirmar eliminación", `Se eliminarán los registros del ejercicio #${ejercicio}.`);
  if (!ok) return;
  fetch(`http://127.0.0.1:5000/eliminar-bairstow/${ejercicio}`, { method: "DELETE" })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) throw new Error(payload?.error || "No se pudo eliminar.");
      mostrarNotificacion(payload?.mensaje || "Eliminado.", "success");
      cargarResultadosBairstow();
    })
    .catch(err => mostrarNotificacion(err.message || "No se pudo eliminar.", "error"));
}

function actualizarEjercicioBairstow(event) {
  event.preventDefault();
  const form = document.getElementById("form-bairstow");
  if (!form) return;
  const formData = new FormData(form);
  fetch("http://127.0.0.1:5000/actualizar-bairstow", { method: "POST", body: formData })
    .then(leerRespuestaServidor)
    .then(({ ok, payload }) => {
      if (!ok) throw new Error(payload?.error || "No se pudo actualizar.");
      mostrarNotificacion(payload?.mensaje || "Actualizado.", "success");
      cargarResultadosBairstow();
    })
    .catch(err => mostrarNotificacion(err.message || "No se pudo actualizar.", "error"));
}

const formBairstow = document.getElementById("form-bairstow");
if (formBairstow) {
  formBairstow.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(formBairstow);
    fetch("http://127.0.0.1:5000/bairstow", { method: "POST", body: formData })
      .then(leerRespuestaServidor)
      .then(({ ok, payload }) => {
        if (!ok) throw new Error(payload?.error || "No se pudo calcular.");
        mostrarNotificacion(payload?.mensaje || "Cálculo completado.", "success");
        cargarResultadosBairstow();
      })
      .catch(err => mostrarNotificacion(err.message || "No se pudo calcular.", "error"));
  });
}

const formFalsa = document.querySelector('form[action="http://127.0.0.1:5000/falsa-posicion"]');
if (formFalsa) {
  formFalsa.addEventListener("submit", function (event) {
    event.preventDefault();

    const formData = new FormData(formFalsa);
    fetch("http://127.0.0.1:5000/falsa-posicion", {
      method: "POST",
      body: formData
    })
      .then(leerRespuestaServidor)
      .then(({ ok, payload }) => {
        if (!ok) {
          const msg = typeof payload === "object" && payload.error ? payload.error : "No se pudo calcular falsa posición.";
          throw new Error(msg);
        }
        mostrarNotificacion(
          (payload && payload.mensaje) ? payload.mensaje : "Cálculo de falsa posición realizado correctamente.",
          "success"
        );
        cargarResultadosFalsa();
        actualizarSelectFalsa();
      })
      .catch(error => {
        console.error("Error Falsa Posición:", error);
        mostrarNotificacion(error.message || "No se pudo calcular falsa posición.", "error");
      });
  });
}

function exportarTabla(idTabla, nombreArchivo, nombreHoja) {
  const tabla = document.getElementById(idTabla);
  const wb = XLSX.utils.table_to_book(tabla, { sheet: nombreHoja });
  XLSX.writeFile(wb, nombreArchivo);
}

async function exportarTodo() {
  try {
    const [resBiseccion, resFalsa, resPuntoFijo, resNewtonCla, resNewtonMod, resNewtonNum, resHorner] = await Promise.all([
      fetch('/resultados-biseccion'),
      fetch('/resultados-falsa-posicion'),
      fetch('/resultados-punto-fijo'),
      fetch('/resultados-newton/CLA'),
      fetch('/resultados-newton/MOD'),
      fetch('/resultados-newton/NUM'),
      fetch('/resultados-horner')
    ]);

    if (!resBiseccion.ok || !resFalsa.ok || !resPuntoFijo.ok || !resNewtonCla.ok || !resNewtonMod.ok || !resNewtonNum.ok || !resHorner.ok) {
      throw new Error('No se pudieron leer los datos almacenados.');
    }

    const [dataBiseccion, dataFalsa, dataPuntoFijo, dataNewtonCla, dataNewtonMod, dataNewtonNum, dataHorner] = await Promise.all([
      resBiseccion.json(),
      resFalsa.json(),
      resPuntoFijo.json(),
      resNewtonCla.json(),
      resNewtonMod.json(),
      resNewtonNum.json(),
      resHorner.json()
    ]);

    const wb = XLSX.utils.book_new();
    const tablas = [
      { id: 'tabla-resultados', nombre: 'Biseccion', filas: dataBiseccion },
      { id: 'tabla-resultados-falsa', nombre: 'FalsaPosicion', filas: dataFalsa },
      { id: 'tabla-resultados-puntofijo', nombre: 'PuntoFijo', filas: dataPuntoFijo },
      { id: 'tabla-resultados-newton', nombre: 'Newton_CLA', filas: dataNewtonCla },
      { id: 'tabla-resultados-newton', nombre: 'Newton_MOD', filas: dataNewtonMod },
      { id: 'tabla-resultados-newton', nombre: 'Newton_NUM', filas: dataNewtonNum },
      { id: 'tabla-resultados-horner', nombre: 'Horner', filas: dataHorner }
    ];

    tablas.forEach(({ id, nombre, filas }) => {
      const ths = document.querySelectorAll(`#${id} thead th`);
      const headers = Array.from(ths).map(th => th.innerText.trim());
      const rows = Array.isArray(filas) ? filas : [];
      const matriz = [headers, ...rows];
      const ws = XLSX.utils.aoa_to_sheet(matriz);
      XLSX.utils.book_append_sheet(wb, ws, nombre);
    });

    XLSX.writeFile(wb, 'metodos_numericos_completo.xlsx');
  } catch (error) {
    mostrarNotificacion(error.message || 'No se pudo exportar el archivo completo.', "error");
  }
}

// ==================== HORNER ====================
function cargarResultadosHorner() {
  fetch('http://127.0.0.1:5000/resultados-horner')
    .then(r => r.json())
    .then(data => {
      const tbody = document.querySelector("#tabla-resultados-horner tbody");
      if (!tbody) return;
      tbody.innerHTML = "";
      const filas = Array.isArray(data) ? data : [];
      filas.forEach(fila => {
        const tr = tbody.insertRow();
        const celdas = Array.isArray(fila) ? fila : Object.values(fila);
        celdas.forEach(valor => {
          const td = tr.insertCell();
          td.textContent = valor;
        });
      });
      actualizarSelectHorner(filas);
    })
    .catch(err => console.error("Error Horner:", err));
}

function actualizarSelectHorner(data) {
  const filas = Array.isArray(data) ? data : [];
  const ejercicios = [...new Set(filas.map(r => r[0]))];
  const select = document.getElementById('ejercicioSelectHorner');
  if (!select) return;
  select.innerHTML = '';
  ejercicios.forEach(ej => {
    const opt = document.createElement('option');
    opt.value = ej;
    opt.textContent = `Ejercicio ${ej}`;
    select.appendChild(opt);
  });
  if (ejercicios.length) {
    select.value = ejercicios[ejercicios.length - 1];
    cargarGraficaHorner();
  }
}

function cargarGraficaHorner() {
  const select = document.getElementById('ejercicioSelectHorner');
  const frame = document.getElementById('grafica-interactiva-horner');
  if (!select || !frame) return;
  const ej = select.value;
  if (!ej) return;
  frame.src = `/static/imagenes/horner_${ej}.html?t=${Date.now()}`;
}

function eliminarEjercicioHorner(e) {
  e.preventDefault();
  const ej = document.getElementById('ejercicio-horner').value;
  if (!ej) return mostrarNotificacion("Ingresa número de ejercicio", "warning");
  fetch(`http://127.0.0.1:5000/eliminar-horner/${ej}`, { method: 'DELETE' })
    .then(r => r.text())
    .then(msg => {
      mostrarNotificacion(msg, "success");
      cargarResultadosHorner();
    })
    .catch(() => mostrarNotificacion("No se pudo eliminar.", "error"));
}

function actualizarEjercicioHorner(e) {
  e.preventDefault();
  const form = document.getElementById('form-horner');
  if (!form) return mostrarNotificacion('No se encontró el formulario de Horner.', 'warning');
  const formData = new FormData(form);
  fetch('http://127.0.0.1:5000/actualizar-horner', {
    method: 'POST',
    body: formData
  })
    .then(() => cargarResultadosHorner())
    .catch(() => mostrarNotificacion("No se pudo actualizar Horner.", "error"));
}

function buscarPorEjercicioHorner(e) {
  cargarResultadosHorner();
}

const formHorner = document.getElementById("form-horner");
if (formHorner) {
  formHorner.addEventListener("submit", function (e) {
    e.preventDefault();
    const formData = new FormData(this);
    fetch("http://127.0.0.1:5000/horner", {
      method: "POST",
      body: formData
    })
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          mostrarNotificacion(data.error, "error");
          return;
        }
        mostrarNotificacion(data.mensaje || "Horner completado.", "success");
        cargarResultadosHorner();
        if (data.imagen) {
          const frame = document.getElementById("grafica-interactiva-horner");
          if (frame) frame.src = data.imagen + "?t=" + Date.now();
        }
      })
      .catch(() => mostrarNotificacion("Error al conectar con el servidor", "error"));
  });
}

window.addEventListener('load', () => {
  fetch('/resultados-biseccion')
    .then(res => res.json())
    .then(data => {
      const filas = Array.isArray(data) ? data : [];
      const ejerciciosUnicos = [...new Set(filas.map(row => row[0]))];
      const select = document.getElementById('ejercicioSelect');
      if (!select) return;
      ejerciciosUnicos.forEach(ej => {
        const option = document.createElement('option');
        option.value = ej;
        option.textContent = `Ejercicio ${ej}`;
        select.appendChild(option);
      });

      if (ejerciciosUnicos.length > 0) {
        select.value = ejerciciosUnicos[0];
        cargarGrafica();
      }
    });

  fetch('/resultados-falsa-posicion')
    .then(res => res.json())
    .then(data => {
      const filas = Array.isArray(data) ? data : [];
      const ejerciciosUnicos = [...new Set(filas.map(row => row[0]))];
      const select = document.getElementById('ejercicioSelectFalsa');
      if (!select) return;
      ejerciciosUnicos.forEach(ej => {
        const option = document.createElement('option');
        option.value = ej;
        option.textContent = `Ejercicio ${ej}`;
        select.appendChild(option);
      });

      if (ejerciciosUnicos.length > 0) {
        select.value = ejerciciosUnicos[0];
        cargarGraficaFalsa();
      }
    });

  fetch('/resultados-punto-fijo')
    .then(res => res.json())
    .then(data => {
      const filas = Array.isArray(data) ? data : [];
      const ejerciciosUnicos = [...new Set(filas.map(row => row[0]))];
      const select = document.getElementById('ejercicioSelectPuntoFijo');
      if (!select) return;
      ejerciciosUnicos.forEach(ej => {
        const option = document.createElement('option');
        option.value = ej;
        option.textContent = `Ejercicio ${ej}`;
        select.appendChild(option);
      });
      if (ejerciciosUnicos.length > 0) {
        select.value = ejerciciosUnicos[0];
        cargarGraficaPuntoFijo();
      } else {
        limpiarGraficaPuntoFijo();
      }
    });

  // Inicialización Newton
  if (document.getElementById("newtonTipo")) {
    cambiarTipoNewton();
  }

  // Inicialización métodos nuevos
  if (document.getElementById("form-newton-sistemas")) cargarResultadosNewtonSistemas();
  if (document.getElementById("form-secante")) cargarResultadosSecante();
  if (document.getElementById("form-muller")) cargarResultadosMuller();
  if (document.getElementById("form-bairstow")) cargarResultadosBairstow();
  if (document.getElementById("form-horner")) cargarResultadosHorner();
  let currentSlide = 0;

  window.abrirGuia = function() {
    const modal = document.getElementById('modal-guia');
    if (modal) modal.style.display = 'flex';
  }

  window.cerrarGuia = function() {
    const modal = document.getElementById('modal-guia');
    if (modal) modal.style.display = 'none';
  }

  window.moverCarrusel = function(direccion) {
    const track = document.querySelector('.carousel-track');
    const slides = document.querySelectorAll('.carousel-slide');
    const totalSlides = slides.length;

    currentSlide = (currentSlide + direccion + totalSlides) % totalSlides;
    const offset = currentSlide * -100;
    if (track) track.style.transform = `translateX(${offset}%)`;
  }

// Cerrar modal al hacer clic fuera del contenido
window.onclick = function(event) {
  const modal = document.getElementById('modal-guia');
  if (event.target == modal) {
    cerrarGuia();
  }
}
});
