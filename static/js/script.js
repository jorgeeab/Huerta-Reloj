// ==================== CONFIGURACIONES ====================
// Ajusta API_BASE al servidor Flask (puerto 5001)
const API_BASE = "http://127.0.0.1:5000";

// Ajusta NODEMCU_IP a la IP real (o simulada) del NodeMCU
NODEMCU_IP = "http://192.168.100.226";
//NODEMCU_IP = "http://192.168.100.34";
//NODEMCU_IP = "http://192.168.66.55";

// ==================== LOGS ====================
function logMessage(msg){
  const logsDiv = document.getElementById('system-logs');
  const time = new Date().toLocaleTimeString();
  logsDiv.textContent += `[${time}] ${msg}\n`;
  logsDiv.scrollTop = logsDiv.scrollHeight;
}

// ==================== ESTADO NODEMCU ====================
let nodeTasksRunning = false;

// Llama periódicamente a fetchNodeStatus() cada 1s (ajustable)
function autoUpdateNodeStatus(){
  setInterval(fetchNodeStatus, 1000);
}

/**
 * Llama al endpoint de Flask para calibrar el flow.
 * Se espera que el endpoint /api/calibrate_flow retorne un JSON indicando el resultado.
 */
function calibrateFlow() {
  let url = `${API_BASE}/api/calibrate_flow`;

  fetch(url)
    .then(response => response.json())
    .then(data => {
      if(data.status === 'ok'){
         logMessage("Calibración completada: " + data.message);
         alert("Calibración completada en el NodeMCU");
      } else {
         logMessage("Error en calibración: " + data.error);
         alert("Error en calibración: " + data.error);
      }
    })
    .catch(error => {
      logMessage("Error al llamar a calibrar flow: " + error);
      alert("Error al llamar a calibrar flow: " + error);
    });
}

// ---------------------------------------------------------------------
// 1) Ya no acumulamos la historia en feedRatioHistory, sino que
//    consultaremos la tabla feed-forward (flow, angle).
// ---------------------------------------------------------------------
let feedForwardPoints = [];  // AQUÍ guardaremos los 20 puntos { flow, angle }

// Mantengo feedRatioHistory si deseas seguir usando su valor en otra parte,
// pero ya NO lo dibujaremos en el canvas:
let feedRatioHistory = [];
function fetchNodeStatus() {
  // 1) Llamar a /api/status en el servidor Flask
  fetch(`${API_BASE}/api/status`)
    .then(response => {
      if (!response.ok) {
        throw new Error(`Error HTTP en /api/status: ${response.status}`);
      }
      return response.json();
    })
    .then(d => {
      // -- Éxito: procesamos la respuesta JSON de /api/status --

      // Suponemos que el JSON viene estructurado como:
      // {
      //   "nodemcu": {
      //       "status": "...",
      //       "currentFlow": 1.23,
      //       "servoAngle": 180,
      //       ...
      //       "debugLogs": ["mensaje1", "mensaje2", ...]
      //   },
      //   "local": {
      //       "pid": {
      //          "flowCalibration": 1.0
      //       }
      //   }
      // }
      // Si tu JSON es diferente, ajusta las siguientes líneas.

      const nodeData = d.nodemcu || {};          // Ajusta si tu JSON no usa "nodemcu"
      const localData = d.local || {};           // Ajusta si tu JSON no tiene "local"
      const pidData = localData.pid || {};       // Ajusta si tu JSON no usa "pid"

      // 1) Actualiza elementos en la interfaz (valores del NodeMCU)
      document.getElementById('node-version').textContent    = nodeData.status        || '?';
      document.getElementById('node-flow').textContent       = nodeData.currentFlow   || 0;
      document.getElementById('node-servoangle').textContent = nodeData.servoAngle    || 0;
      document.getElementById('node-servo1').textContent     = nodeData.servo1        || '?';
      document.getElementById('node-servo2').textContent     = nodeData.servo2        || '?';
      document.getElementById('node-setpoint').textContent   = nodeData.setpoint      || 0;

      // 2) flowCalibration
      //    Si tu JSON final no tiene "local.pid.flowCalibration", cámbialo
      const calibrationVal = pidData.flowCalibration || 1.0;
      document.getElementById('node-calibration').textContent = calibrationVal;

      // 3) Actualiza estado de "tareas corriendo"
      nodeTasksRunning = nodeData.tasksRunning || false;
      document.getElementById('node-tasksRun').textContent    = nodeTasksRunning ? "true" : "false";
      document.getElementById('task-status').textContent      = `Estado: ${nodeTasksRunning ? "En ejecución" : "Detenido"}`;
      document.getElementById('toggle-tasks-btn').textContent = nodeTasksRunning ? "Detener Tareas" : "Iniciar Tareas";

      // 4) Mostrar logs de depuración (debugLogs: array)
      const logsDiv = document.getElementById('node-debuglogs');
      if (nodeData.debugLogs && nodeData.debugLogs.length > 0) {
        logsDiv.textContent = nodeData.debugLogs.join("\n");
      } else {
        logsDiv.textContent = "No logs disponibles";
      }
      logsDiv.scrollTop = logsDiv.scrollHeight;

      // 5) Mostrar la ecuación feed‑forward (si existe)
      if (nodeData.feedForwardEquation) {
        document.getElementById('node-feedEquation').textContent = nodeData.feedForwardEquation;
      } else {
        document.getElementById('node-feedEquation').textContent = "";
      }

      // 6) Encadenar la segunda petición a /api/feed_forward
      return fetch(`${API_BASE}/api/feed_forward`);
    })
    .then(resp => {
      if (!resp.ok) {
        throw new Error(`Error HTTP en /api/feed_forward: ${resp.status}`);
      }
      return resp.json();
    })
    .then(ffData => {
      // -- Procesamos la tabla feed-forward con dos arreglos paralelos --
      if (ffData.feedForwardTable &&
          ffData.feedForwardTable.flows &&
          ffData.feedForwardTable.angles) {

        const flows  = ffData.feedForwardTable.flows;
        const angles = ffData.feedForwardTable.angles;

        // Convertimos a un array de objetos [{ flow, angle }, ...]
        feedForwardPoints = flows.map((f, i) => ({
          flow:  f,
          angle: angles[i]
        }));
      } else {
        feedForwardPoints = [];
        logMessage("No se encontró 'feedForwardTable' o sus claves en /api/feed_forward");
      }

      // Finalmente, dibujamos la gráfica con los puntos
      updateFeedRatioChart();
    })
    .catch(err => {
      // Cualquier error en los dos fetch se captura aquí
      logMessage("Error en fetchNodeStatus => " + err);
    });
}

// Iniciar la calibración en el NodeMCU
function startCalibrate() {
  fetch(`${NODEMCU_IP}/calibrateFeedForward`)
    .then(r => r.text())
    .then(txt => {
      // El NodeMCU responde algo como "Calibración iniciada en segundo plano."
      console.log("Respuesta calibración:", txt);
      alert("Calibración => " + txt);
      // Podrías también forzar un primer check en 5s:
      setTimeout(checkCalibrationStatus, 5000);
    })
    .catch(err => {
      console.error("Error startCalibrate =>", err);
      alert("Error iniciando calibración => " + err);
    });
}

// Verificar en /status si se está calibrando actualmente
function checkCalibrationStatus() {
  fetch(`${NODEMCU_IP}/status`)
    .then(r => r.json())
    .then(data => {
      // Suponiendo que en /status incluiste:
      // "calibrationInProgress", "calibrationDone", "calibrationMessage"
      const inProgress = data.calibrationInProgress;
      const done       = data.calibrationDone;
      const msg        = data.calibrationMessage;

      // Mostramos en <span id="calib-status">...</span>
      const statusSpan = document.getElementById("calib-status");
      if (inProgress) {
        statusSpan.textContent = msg || "Calibrando...";
      } else if (done) {
        statusSpan.textContent = msg || "Calibración finalizada.";
      } else {
        statusSpan.textContent = "No en calibración.";
      }
    })
    .catch(err => {
      console.error("Error checkCalibrationStatus =>", err);
      alert("Error chequeando calibración => " + err);
    });
}

// Borrar config y resetear feed-forward
function resetFeedForwardTable() {
  if (!confirm("¿Seguro que deseas borrar la config y la tabla feed-forward?")) return;

  fetch(`${NODEMCU_IP}/deleteConfig`)
    .then(resp => resp.text())
    .then(txt => {
      console.log("Respuesta deleteConfig:", txt);
      alert("deleteConfig => " + txt);
    })
    .catch(err => {
      console.error("Error resetFeedForwardTable =>", err);
      alert("Error => " + err);
    });
}


// ----- Variables de control -----

// Variables para detectar clic rápido y actualizar continuamente
let servo1PressTimer = null;  // Timer para detectar si es solo un clic
let servo1Timer = null;       // Timer para la actualización continua
let servo1Dir = 0;            // Dirección: 1 para aumentar, -1 para disminuir

let servo2PressTimer = null;
let servo2Timer = null;
let servo2Dir = 0;

function servo2Down(direction) {
  servo2Dir = direction;
  servo2PressTimer = setTimeout(() => {
    servo2Timer = setInterval(() => {
      adjServo2(servo2Dir);
    }, 100);
  }, 200);
}

function servo2Up() {
  if (servo2PressTimer) {
    clearTimeout(servo2PressTimer);
    servo2PressTimer = null;
    if (!servo2Timer) {
      adjServo2(servo2Dir);
    }
  }
  if (servo2Timer) {
    clearInterval(servo2Timer);
    servo2Timer = null;
  }
}

function servo1Down(direction) {
  servo1Dir = direction;
  // Inicia un timeout de 200ms; si se mantiene presionado se activa el setInterval.
  servo1PressTimer = setTimeout(() => {
    servo1Timer = setInterval(() => {
      adjServo1(servo1Dir);
    }, 100); // cada 100 ms
  }, 200);
}

function servo1Up() {
  // Si se soltó antes de 200ms, es un clic rápido
  if (servo1PressTimer) {
    clearTimeout(servo1PressTimer);
    servo1PressTimer = null;
    // Si no se inició el intervalo, se hace un ajuste único (1 grado)
    if (!servo1Timer) {
      adjServo1(servo1Dir);
    }
  }
  // Si se había iniciado el intervalo, detenerlo
  if (servo1Timer) {
    clearInterval(servo1Timer);
    servo1Timer = null;
  }
}
// ----- Joystick servo2 -----
function servo2Down(direction) {
  if (servo2Timer) return;
  servo2Dir = direction;
  servo2Speed = 1;

  servo2Timer = setInterval(() => {
    adjServo2(servo2Dir);
    servo2Speed += 0.2;
  }, 100);
}

function servo2Up() {
  if (servo2Timer) {
    clearInterval(servo2Timer);
    servo2Timer = null;
  }
  servo2Speed = 1;
  servo2Dir   = 0;
}

// ----- Entrada directa de ángulo (Servo1) -----
function applyServo1Angle() {
  let angleInput = document.getElementById('servo1-input');
  let angle = parseInt(angleInput.value);
  angle = Math.max(0, Math.min(180, angle));    // limitar
  adjServo1(angle - parseInt(document.getElementById('servo1-lab').textContent));
}

// ----- Entrada directa de ángulo (Servo2) -----
function applyServo2Angle() {
  let angleInput = document.getElementById('servo2-input');
  let angle = parseInt(angleInput.value);
  angle = Math.max(0, Math.min(180, angle));
  adjServo2(angle - parseInt(document.getElementById('servo2-lab').textContent));
}

function updateFeedRatioChart() {
  const canvas = document.getElementById("feedRatioChart");
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;

  // 1) Limpiar el canvas
  ctx.clearRect(0, 0, width, height);

  // 2) Si no hay datos suficientes, no dibujamos nada
  if (feedForwardPoints.length < 2) {
    ctx.fillText("No hay datos suficientes", 10, 20);
    return;
  }

  // 3) Hallar min y max de flow y angle
  const flows = feedForwardPoints.map(p => p.flow);
  const angles = feedForwardPoints.map(p => p.angle);
  const minFlow = Math.min(...flows);
  const maxFlow = Math.max(...flows);
  const minAngle = Math.min(...angles);
  const maxAngle = Math.max(...angles);

  // Pequeño margen interno
  const margin = 30;

  // 4) Funciones de escalado para flow→X y angle→Y
  //    Ajustan el rango [minFlow..maxFlow] → [margin..(width-margin)]
  function xCanvas(flowValue) {
    return margin + (flowValue - minFlow) * (width - 2*margin) / (maxFlow - minFlow);
  }

  //    Para angle: decide si angle=0 va arriba y angle=180 va abajo, o al revés.
  //    Aquí, angle=0 → parte superior, angle=180 → parte inferior:
  function yCanvas(angleValue) {
    return margin + (angleValue - minAngle) * (height - 2*margin) / (maxAngle - minAngle);
  }

  // 5) Dibujar ejes (simplemente una L invertida)
  ctx.strokeStyle = "#999";
  ctx.beginPath();
  // Eje Y
  ctx.moveTo(margin, margin);
  ctx.lineTo(margin, height - margin);
  // Eje X
  ctx.lineTo(width - margin, height - margin);
  ctx.stroke();

  // 6) Dibujar la línea que une los puntos (flow, angle)
  ctx.strokeStyle = "#3498db";
  ctx.lineWidth = 2;
  ctx.beginPath();
  feedForwardPoints.forEach((pt, i) => {
    const px = xCanvas(pt.flow);
    const py = yCanvas(pt.angle);
    if (i === 0) {
      ctx.moveTo(px, py);
    } else {
      ctx.lineTo(px, py);
    }
  });
  ctx.stroke();

  // 7) Dibujar cada punto con un pequeño círculo
  ctx.fillStyle = "#e74c3c";
  feedForwardPoints.forEach(pt => {
    const px = xCanvas(pt.flow);
    const py = yCanvas(pt.angle);
    ctx.beginPath();
    ctx.arc(px, py, 3, 0, 2 * Math.PI);
    ctx.fill();
  });

  // 8) Etiquetas de ejes
  ctx.fillStyle = "#333";
  ctx.fillText("Flow (ml/s)", width / 2 - 30, height - 5);

  // Girar texto para el eje Y
  ctx.save();
  ctx.translate(5, height / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("Angle (°)", 0, 0);
  ctx.restore();
}




// ==================== CONTROL DIRECTO ====================
let servo1Val = 90, servo2Val = 90, flowVal = 0;

/**
 * @desc Ajusta el servo1Val y llama a updateNodeControl()
 */
function adjServo1(delta){
  if(nodeTasksRunning){
    logMessage("No se puede mover servo1 => tasksRunning=true");
    return;
  }
  servo1Val = Math.min(180, Math.max(0, servo1Val + delta));
  document.getElementById('servo1-lab').textContent = servo1Val;
  updateNodeControl();
}

function adjServo2(delta){
  if(nodeTasksRunning){
    logMessage("No se puede mover servo2 => tasksRunning=true");
    return;
  }
  servo2Val = Math.min(180, Math.max(0, servo2Val + delta));
  document.getElementById('servo2-lab').textContent = servo2Val;
  updateNodeControl();
}

function setFlowSlider(v){
  if(nodeTasksRunning){
    logMessage("No se puede cambiar flow => tasksRunning=true");
    return;
  }
  flowVal = parseFloat(v);
  document.getElementById('flow-label').textContent = flowVal.toFixed(1) + " ml/s";
  // Se elimina la actualización automática:
  updateNodeControl();
}


/**
 * @desc Llama a /control en NodeMCU => ajusta servo1, servo2, flow
 */
// Bandera para controlar el envío automático de configuraciones
let autoUpdateEnabled = false;

// Función que envía la configuración al NodeMCU solo si está activada la bandera.
function updateNodeControl() {
  if (!autoUpdateEnabled) {
    logMessage("Actualización manual desactivada. Pulsa el botón 'Cambiar PID' para enviar configuraciones.");
    return;
  }
  let servo1Val = parseInt(document.getElementById('servo1-lab').textContent);
  let servo2Val = parseInt(document.getElementById('servo2-lab').textContent);
  let flowVal = parseFloat(document.getElementById('flow-slider').value);
  let kp = parseFloat(document.getElementById('pid-kp').value || "2");
  let ki = parseFloat(document.getElementById('pid-ki').value || "5");
  let kd = parseFloat(document.getElementById('pid-kd').value || "1");
  let flowCalibration = parseFloat(document.getElementById('pid-cal').value || "1");

  let url = `${NODEMCU_IP}/control?servo1=${servo1Val}&servo2=${servo2Val}&flow=${flowVal}&kp=${kp}&ki=${ki}&kd=${kd}&flowCalibration=${flowCalibration}`;
  let xhr = new XMLHttpRequest();
  xhr.open("GET", url, true);
  xhr.timeout = 5000;
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4) {
      if (xhr.status === 200) {
        logMessage("Control y PID actualizados => " + xhr.responseText);
      } else {
        logMessage(`Error updateNodeControl => HTTP ${xhr.status}`);
      }
    }
  };
  xhr.onerror = function() {
    logMessage("Error updateNodeControl => No se pudo conectar al NodeMCU");
  };
  xhr.ontimeout = function() {
    logMessage("Error updateNodeControl => Timeout");
  };
  xhr.send();
}
/**
 * @desc Iniciar/Detener tareas => /startStopTasks?run=..
 */
function startStopTasks(run) {
  let url = `${NODEMCU_IP}/startStopTasks?run=${run}`;
  let xhr = new XMLHttpRequest();
  xhr.open("GET", url, true);
  xhr.timeout = 5000;
  xhr.onreadystatechange = function(){
    if(xhr.readyState === 4){
      if(xhr.status === 200){
        logMessage("startStop => " + xhr.responseText);
      } else {
        logMessage(`Error startStopTasks => HTTP ${xhr.status}`);
      }
    }
  };
  xhr.onerror = function() {
    logMessage("Error startStop => No se pudo conectar al NodeMCU");
  };
  xhr.ontimeout = function() {
    logMessage("Error startStop => Timeout");
  };
  xhr.send();
}

// ==================== PID CONFIG ====================
function loadPID(){
  let url = `${API_BASE}/api/pid`;
  let xhr = new XMLHttpRequest();
  xhr.open("GET", url, true);
  xhr.timeout = 5000;
  xhr.onreadystatechange = function(){
    if(xhr.readyState === 4){
      if(xhr.status === 200){
        try {
          let d = JSON.parse(xhr.responseText);
          document.getElementById('pid-kp').value  = d.kp  || 2;
          document.getElementById('pid-ki').value  = d.ki  || 5;
          document.getElementById('pid-kd').value  = d.kd  || 1;
          document.getElementById('pid-cal').value = d.flowCalibration || 1;
          logMessage("PID cargado => " + JSON.stringify(d));
        } catch(e){
          logMessage("Error parseando PID => " + e);
        }
      } else {
        logMessage(`Error loadPID => HTTP ${xhr.status}`);
      }
    }
  };
  xhr.onerror = function(){
    logMessage("Error loadPID => No se pudo conectar al servidor Flask");
  };
  xhr.ontimeout = function(){
    logMessage("Error loadPID => Timeout");
  };
  xhr.send();
}


// ==================== PUSH CONFIG ====================
function pushConfig(){
  let url = `${API_BASE}/api/push_config`;
  let xhr = new XMLHttpRequest();
  xhr.open("POST", url, true);
  xhr.timeout = 5000;
  xhr.onreadystatechange = function(){
    if(xhr.readyState === 4){
      if(xhr.status === 200){
        logMessage("Push config => " + xhr.responseText);
      } else {
        logMessage(`Error pushConfig => HTTP ${xhr.status}`);
      }
    }
  };
  xhr.onerror = function(){
    logMessage("Error pushConfig => No se pudo conectar al servidor Flask");
  };
  xhr.ontimeout = function(){
    logMessage("Error pushConfig => Timeout");
  };
  xhr.send(); // sin body
}

// ==================== PLANTAS ====================
let nextPlantID=1;
function assignNextPlantID(){
  document.getElementById('plant-id').value= nextPlantID;
  nextPlantID++;
  logMessage("Nuevo ID local => Planta="+ nextPlantID);
}
function loadPlants() {
  let url = `${API_BASE}/api/plants`;
  let xhr = new XMLHttpRequest();
  xhr.open("GET", url, true);
  xhr.onreadystatechange = function(){
    if(xhr.readyState === 4 && xhr.status === 200){
      try {
        let plants = JSON.parse(xhr.responseText);
        renderPlants(plants);
      } catch(e){
        logMessage("Error parseando plants => " + e);
      }
    }
  };
  xhr.onerror = function(){
    logMessage("Error cargando plants => No se pudo conectar a Flask");
  };
  xhr.ontimeout = function(){
    logMessage("Error cargando plants => Timeout");
  };
  xhr.send();
}
function renderPlants(plants) {
  let ul = document.getElementById("plants-ul");
  ul.innerHTML = "";

  if (plants.length === 0) {
    ul.innerHTML = "<li>No hay plantas registradas</li>";
    return;
  }

  plants.forEach(p => {
    let li = document.createElement("li");
    li.innerHTML = `[${p.id}] ${p.name} ` +
      `<button onclick="selectPlant(${p.id})">✏️</button>` +
      `<button onclick="deletePlant(${p.id})">🗑️</button>`;
    ul.appendChild(li);
  });
}
function selectPlant(plantId) {
  let xhr = new XMLHttpRequest();
  xhr.open("GET", `${API_BASE}/api/plants`, true);
  xhr.onreadystatechange = function(){
    if(xhr.readyState === 4 && xhr.status === 200){
      let plants = JSON.parse(xhr.responseText);
      let plant = plants.find(p => p.id === plantId);
      if (plant) {
        document.getElementById('plant-id').value = plant.id;
        document.getElementById('plant-name').value = plant.name;
        document.getElementById('plant-desc').value = plant.description;
        document.getElementById('plant-servo1').value = plant.servo1pos;
        document.getElementById('plant-servo2').value = plant.servo2pos;
        document.getElementById('plant-flowsp').value = plant.flowSetpoint;
        document.getElementById('plant-day').value = plant.start_day;
        document.getElementById('plant-mon').value = plant.start_month;
        document.getElementById('plant-year').value = plant.start_year;
        document.getElementById('plant-regimen').value = plant.regimen_id || "";
      }
    }
  };
  xhr.send();
}
function deletePlant(plantId) {
  if (!confirm(`¿Seguro que deseas eliminar la planta ID ${plantId}?`)) return;

  let xhr = new XMLHttpRequest();
  xhr.open("DELETE", `${API_BASE}/api/plants`, true);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4 && xhr.status === 200) {
      alert("Planta eliminada correctamente");
      loadPlants(); // Recargar la lista después de eliminar
    } else if (xhr.readyState === 4) {
      alert(`Error al eliminar planta: HTTP ${xhr.status}`);
    }
  };
  xhr.send(JSON.stringify({ id: plantId }));
}
function savePlant() {
  let plantId = document.getElementById('plant-id').value;
  let plantName = document.getElementById('plant-name').value.trim();
  let plantDesc = document.getElementById('plant-desc').value.trim();
  let servo1 = parseInt(document.getElementById('plant-servo1').value);
  let servo2 = parseInt(document.getElementById('plant-servo2').value);
  let flowSetpoint = parseFloat(document.getElementById('plant-flowsp').value);
  let startDay = parseInt(document.getElementById('plant-day').value);
  let startMonth = parseInt(document.getElementById('plant-mon').value);
  let startYear = parseInt(document.getElementById('plant-year').value);
  let regimenId = document.getElementById('plant-regimen').value;

  if (!plantName) {
    alert("El nombre de la planta es obligatorio.");
    return;
  }

  let data = {
    id: plantId ? parseInt(plantId) : null,
    name: plantName,
    description: plantDesc,
    servo1pos: servo1,
    servo2pos: servo2,
    flow_setpoint: flowSetpoint,
    start_day: startDay,
    start_month: startMonth,
    start_year: startYear,
    regimen_id: regimenId ? parseInt(regimenId) : null
  };

  let xhr = new XMLHttpRequest();
  xhr.open("POST", `${API_BASE}/api/plants`, true);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4) {
      if (xhr.status === 200) {
        alert("Planta guardada correctamente.");
        loadPlants(); // Recargar lista de plantas
      } else if (xhr.status === 400) {
        alert("Error: Ya existe una planta con este nombre.");
      } else {
        alert(`Error al guardar planta: HTTP ${xhr.status}`);
      }
    }
  };
  xhr.send(JSON.stringify(data));
}

function fillPlantConfig() {
  let url = `${API_BASE}/api/esp_status`;
  let xhr = new XMLHttpRequest();
  xhr.open("GET", url, true);
  xhr.timeout = 5000;
  xhr.onreadystatechange = function(){
    if(xhr.readyState===4){
      if(xhr.status===200){
        try {
          let data = JSON.parse(xhr.responseText);
          document.getElementById('plant-servo1').value = data.servo1     || 90;
          document.getElementById('plant-servo2').value = data.servo2     || 90;
          document.getElementById('plant-flowsp').value = data.currentFlow|| 1.0;
          logMessage("Configuración NodeMCU usada para la planta");
        } catch(e){
          logMessage("Error parseando fillPlantConfig => " + e);
        }
      } else {
        logMessage(`Error fillPlantConfig => HTTP ${xhr.status}`);
      }
    }
  };
  xhr.onerror = function(){
    logMessage("Error fillPlantConfig => No se pudo conectar");
  };
  xhr.ontimeout = function(){
    logMessage("Error fillPlantConfig => Timeout");
  };
  xhr.send();
}
// ==================== RENDER FUNCIONES ====================
function renderRegimens(regimens) {
  let ul = document.getElementById('regimens-ul');
  ul.innerHTML = "";
  regimens.forEach(rg => {
    let li = document.createElement("li");
    li.innerHTML = `[${rg.id}] ${rg.name} ` +
      `<button onclick="selectRegimen(${rg.id})">✏️</button>` +
      `<button onclick="deleteRegimen(${rg.id})">🗑️</button>`;
    ul.appendChild(li);
  });
}

function renderTasks(tasks) {
  let ul = document.getElementById('tasks-ul');
  ul.innerHTML = "";

  tasks.forEach(tk => {
    let li = document.createElement("li");
    li.innerHTML = `[${tk.id}] ${tk.name} - ${tk.volume} ml ` +
      `<br>Estado: ${tk.executed ? "✅ Ejecutada" : "⏳ Pendiente"} ` +
      (tk.executed_at ? `<br>Fecha Ejecución: ${tk.executed_at}` : "") +
      (tk.execution_comment ? `<br>Comentario: ${tk.execution_comment}` : "") +
      `<br><button onclick="selectTask(${tk.id})">✏️</button>` +
      `<button onclick="deleteTask(${tk.id}, ${tk.regimen_id})">🗑️</button>` +
      `<button class="btn" onclick="executeTask(${tk.id})">▶️ Ejecutar</button>`;

    ul.appendChild(li);
  });
}


function executeTask(taskId) {
  let regimenId = document.getElementById('regimen-id').value;
  let plantId   = document.getElementById('plant-id').value;
  let servo1    = parseInt(document.getElementById('plant-servo1').value);
  let servo2    = parseInt(document.getElementById('plant-servo2').value);
  let flowSetpoint = parseFloat(document.getElementById('plant-flowsp').value);

  fetch(`${API_BASE}/api/tasks?regimen_id=${regimenId}`)
    .then(resp => resp.json())
    .then(tasks => {
      let t = tasks.find(x => x.id == taskId);
      if (!t) {
        alert("No se encontró la tarea ID="+taskId);
        return;
      }
      let volumen = t.volume;

      let data = {
        "plant_id": parseInt(plantId),
        "volume": volumen,
        "servo1pos": servo1,
        "servo2pos": servo2,
        "flow_setpoint": flowSetpoint
      };

      fetch(`${API_BASE}/api/regar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      .then(r => r.json())
      .then(result => {
        if (result.error) {
          alert("Error al regar: " + result.error);
        } else {
          alert(result.mensaje || "Riego ejecutado con éxito");

          // 🚀 Volver a cargar la lista de tareas después de actualizar
          loadTasks();
        }
      })
      .catch(err => {
        console.error("Error al ejecutar riego:", err);
        alert("Error al ejecutar riego");
      });
    })
    .catch(err => {
      console.error("Error obteniendo tareas:", err);
      alert("Error al obtener la tarea.");
    });
}



// ==================== REGÍMENES ====================
function loadRegimens() {
  let xhr = new XMLHttpRequest();
  xhr.open("GET", `${API_BASE}/api/regimens`, true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4 && xhr.status === 200) {
      let regimens = JSON.parse(xhr.responseText);
      renderRegimens(regimens);
    }
  };
  xhr.send();
}

function selectRegimen(regimenId) {
  let xhr = new XMLHttpRequest();
  xhr.open("GET", `${API_BASE}/api/regimens`, true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4 && xhr.status === 200) {
      let regimens = JSON.parse(xhr.responseText);
      let regimen = regimens.find(rg => rg.id === regimenId);
      if (regimen) {
        document.getElementById('regimen-id').value = regimen.id;
        document.getElementById('regimen-name').value = regimen.name;
        document.getElementById('regimen-desc').value = regimen.description;
        loadTasksForRegimen(regimen.id);
      }
    }
  };
  xhr.send();
}
function loadRegimensForSelect() {
  let url = `${API_BASE}/api/regimens`;
  let xhr = new XMLHttpRequest();
  xhr.open("GET", url, true);
  xhr.onreadystatechange = function(){
    if(xhr.readyState === 4 && xhr.status === 200){
      try {
        let regimens = JSON.parse(xhr.responseText);
        let select = document.getElementById("plant-regimen");
        select.innerHTML = '<option value="">-- Seleccione un Régimen --</option>';
        regimens.forEach(rg => {
          let option = document.createElement("option");
          option.value = rg.id;
          option.textContent = `${rg.name} (ID: ${rg.id})`;
          select.appendChild(option);
        });
        logMessage("Regímenes actualizados en el <select>");
      } catch(e){
        logMessage("Error parseando loadRegimensForSelect => " + e);
      }
    }
  };
  xhr.onerror = function(){
    logMessage("Error loadRegimensForSelect => No se pudo conectar");
  };
  xhr.ontimeout = function(){
    logMessage("Error loadRegimensForSelect => Timeout");
  };
  xhr.send();
}
function saveRegimen() {
  let regimenId = document.getElementById('regimen-id').value;
  let regimenName = document.getElementById('regimen-name').value;
  let regimenDesc = document.getElementById('regimen-desc').value;

  let data = { name: regimenName, description: regimenDesc };
  if (regimenId) data.id = parseInt(regimenId);

  let xhr = new XMLHttpRequest();
  xhr.open("POST", `${API_BASE}/api/regimens`, true);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4 && xhr.status === 200) {
      alert("Régimen guardado correctamente");
      loadRegimens(); // Recargar la lista de regímenes en pantalla
      loadRegimensForSelect(); // También recargar el <select> de las plantas
    } else if (xhr.readyState === 4) {
      alert(`Error al guardar régimen: HTTP ${xhr.status}`);
    }
  };
  xhr.send(JSON.stringify(data));
}
function deleteRegimen(regimenId) {
  if (!confirm(`¿Seguro que deseas eliminar el régimen ID ${regimenId}?`)) return;

  let xhr = new XMLHttpRequest();
  xhr.open("DELETE", `${API_BASE}/api/regimens`, true);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4 && xhr.status === 200) {
      alert("Régimen eliminado correctamente");
      loadRegimens(); // Recargar la lista de regímenes en pantalla
      loadRegimensForSelect(); // También recargar el <select> de las plantas
    } else if (xhr.readyState === 4) {
      alert(`Error al eliminar régimen: HTTP ${xhr.status}`);
    }
  };
  xhr.send(JSON.stringify({ id: regimenId }));
}


// ==================== TAREAS ====================
function loadTasksForRegimen(regimenId) {
  let xhr = new XMLHttpRequest();
  xhr.open("GET", `${API_BASE}/api/tasks?regimen_id=${regimenId}`, true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4 && xhr.status === 200) {
      let tasks = JSON.parse(xhr.responseText);
      renderTasks(tasks);
    }
  };
  xhr.send();
}

function saveTask() {
  let taskId = document.getElementById('task-id').value;
  let regimenId = document.getElementById('regimen-id').value;

  let taskData = {
    regimen_id: parseInt(regimenId),
    name: document.getElementById('task-name').value,
    description: document.getElementById('task-desc').value,
    day_offset: parseInt(document.getElementById('task-dayoff').value || "0"),
    hour: parseInt(document.getElementById('task-hour').value || "0"),
    minute: parseInt(document.getElementById('task-min').value || "0"),
    volume: parseFloat(document.getElementById('task-vol').value || "0")
  };

  if (taskId) taskData.id = parseInt(taskId);

  // === AÑADE ESTAS LÍNEAS PARA INCLUIR executed, execution_comment, executed_at ===
  taskData.executed = document.getElementById('task-executed').checked;
  taskData.execution_comment = document.getElementById('task-comment').value;
  // Si deseas actualizar executed_at también, por ejemplo:
  taskData.executed_at = document.getElementById('task-executed-at').value || null;

  // Enviar JSON al servidor
  let xhr = new XMLHttpRequest();
  xhr.open("POST", `${API_BASE}/api/tasks`, true);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4 && xhr.status === 200) {
      alert("Tarea guardada correctamente");
      loadTasksForRegimen(regimenId);
    } else if (xhr.readyState === 4) {
      alert(`Error al guardar tarea: HTTP ${xhr.status}`);
    }
  };
  xhr.send(JSON.stringify(taskData));
}


function toggleTasks() {
let newStatus = nodeTasksRunning ? 0 : 1;

fetch(`${NODEMCU_IP}/startStopTasks?run=${newStatus}`)
  .then(response => response.text())
  .then(data => {
    console.log("Respuesta NodeMCU:", data);
    setTimeout(fetchNodeStatus, 2000);
    setTimeout(loadTaskTimeline, 3000);
  })
  .catch(error => console.error("Error al cambiar estado de tareas:", error));
}

// Cargar y actualizar la línea de tiempo de tareas
function loadTaskTimeline() {
fetch(`${API_BASE}/api/task_timeline`)
  .then(response => response.json())
  .then(tasks => {
    let container = document.getElementById('task-timeline');
    container.innerHTML = "";

    tasks.forEach(task => {
      let div = document.createElement("div");
      div.className = "timeline-event";
      div.dataset.plantId = task.plant_id;
      div.dataset.regimenId = task.regimen_id;
      div.dataset.taskId = task.task_id;
      div.innerHTML = `<p><span>${task.date}</span> - ${task.plant_name} - ${task.task_name} (${task.volume}ml)</p>`;

      div.addEventListener("click", function () {
        selectTaskFromTimeline(task.plant_id, task.regimen_id, task.task_id);
      });

      container.appendChild(div);
    });

    console.log("Línea de tiempo de tareas actualizada.");
  })
  .catch(error => console.error("Error cargando la línea de tiempo de tareas:", error));
}

function selectTaskFromTimeline(plantId, regimenId, taskId) {
  document.querySelectorAll('.timeline-event').forEach(el => el.classList.remove('selected'));
  let selectedTask = document.querySelector(`[data-task-id='${taskId}']`);
  if (selectedTask) selectedTask.classList.add('selected');

  console.log(`Cargando tarea: Planta=${plantId}, Régimen=${regimenId}, Tarea=${taskId}`);

  // Cargar datos de la planta
  fetch(`${API_BASE}/api/plants`)
    .then(response => response.json())
    .then(plants => {
      let plant = plants.find(p => p.id == plantId);
      if (plant) {
        document.getElementById('plant-id').value = plant.id;
        document.getElementById('plant-name').value = plant.name;
        document.getElementById('plant-desc').value = plant.description;
      }
    });

  // Cargar datos del régimen
  fetch(`${API_BASE}/api/regimens`)
    .then(response => response.json())
    .then(regimens => {
      let regimen = regimens.find(r => r.id == regimenId);
      if (regimen) {
        document.getElementById('regimen-id').value = regimen.id;
        document.getElementById('regimen-name').value = regimen.name;
        document.getElementById('regimen-desc').value = regimen.description;

        // 🔥 Cargar las tareas del régimen seleccionado
        loadTasksForRegimen(regimen.id);
      }
    });

  // Cargar datos de la tarea
  fetch(`${API_BASE}/api/tasks?regimen_id=${regimenId}`)
    .then(response => response.json())
    .then(tasks => {
      let task = tasks.find(t => t.id == taskId);
      if (task) {
        document.getElementById('task-id').value = task.id;
        document.getElementById('task-name').value = task.name;
        document.getElementById('task-desc').value = task.description;
      }
    });
}


function deleteTask(taskId, regimenId) {
  if (!confirm(`¿Seguro que deseas eliminar la tarea ID ${taskId}?`)) return;

  let xhr = new XMLHttpRequest();
  xhr.open("DELETE", `${API_BASE}/api/tasks`, true);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4 && xhr.status === 200) {
      alert("Tarea eliminada correctamente");
      loadTasksForRegimen(regimenId);
    } else if (xhr.readyState === 4) {
      alert(`Error al eliminar tarea: HTTP ${xhr.status}`);
    }
  };
  xhr.send(JSON.stringify({ id: taskId }));
}
function fetchAndUpdateTasks() {
  let url = `${API_BASE}/api/update_tasks_decision`;

  fetch(url)
    .then(response => response.json())
    .then(data => {
      if (data.reload) {
        let confirmUpdate = confirm(data.message);
        if (confirmUpdate) {
          updateDatabaseWithNodeTasks(data.nodemcu_tasks);
        }
      } else {
        alert("Las tareas ya están sincronizadas.");
      }
    })
    .catch(error => console.error("Error al obtener tareas desde NodeMCU:", error));
}
function executeTask(taskId) {
  // Obtener regimenId, plantId, servo, flow, etc. del formulario
  let regimenId = document.getElementById('regimen-id').value;
  let plantId   = document.getElementById('plant-id').value;
  let servo1    = parseInt(document.getElementById('plant-servo1').value);
  let servo2    = parseInt(document.getElementById('plant-servo2').value);
  let flowSetpoint = parseFloat(document.getElementById('plant-flowsp').value);

  // 1) Consultar la tarea para saber su 'volume'
  fetch(`${API_BASE}/api/tasks?regimen_id=${regimenId}`)
    .then(resp => resp.json())
    .then(tasks => {
      let t = tasks.find(x => x.id == taskId);
      if (!t) {
        alert("No se encontró la tarea ID="+taskId);
        return;
      }
      let volumen = t.volume;  // ml que vas a regar

      // 2) Construir objeto con datos a enviar a Flask
      let data = {
        "plant_id": parseInt(plantId),
        "volume": volumen,           // volumen de la tarea
        "servo1pos": servo1,
        "servo2pos": servo2,
        "flow_setpoint": flowSetpoint
      };

      // 3) POST a /api/regar en Flask
      fetch(`${API_BASE}/api/regar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      .then(r => r.json())
      .then(result => {
        if (result.error) {
          alert("Error al regar: " + result.error);
        } else {
          alert(result.mensaje || "Riego ejecutado con éxito");
        }
      })
      .catch(err => {
        console.error("Error al ejecutar riego:", err);
        alert("Error al ejecutar riego");
      });
    })
    .catch(err => {
      console.error("Error obteniendo tareas:", err);
      alert("Error al obtener la tarea.");
    });
}

function updateDatabaseWithNodeTasks(nodemcuTasks) {
  let url = `${API_BASE}/api/update_tasks`;

  let formattedTasks = nodemcuTasks.map(t => ({
    task_id: t.task_id,
    regimen_id: t.regimen_id,
    name: t.name,
    description: t.description,
    day_offset: t.day_offset,
    hour: t.hour,
    minute: t.minute,
    volume: t.volume,
    executed: t.executed || false,
    executed_at: t.executed_at ? t.executed_at : null,
    execution_comment: t.execution_comment || ""
  }));

  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tasks: formattedTasks })
  })
  .then(response => response.json())
  .then(data => {
    alert(data.message);
    location.reload();
  })
  .catch(error => console.error("Error al actualizar tareas en la base de datos:", error));
}

function loadConfig() {
  let url = `${API_BASE}/api/get_nodemcu_tasks`;
  fetch(url)
    .then(response => response.json())
    .then(data => {
      if (data.reload) {
        alert("Configuración cargada, recargando página...");
        location.reload();
      } else {
        alert("Configuración sincronizada.");
      }
    })
    .catch(error => console.error("Error al cargar la configuración:", error));
}

function downloadTasks() {
  let url = `${API_BASE}/api/download_tasks`;
  window.location.href = url;
}

function selectTask(taskId) {
  let xhr = new XMLHttpRequest();
  xhr.open("GET", `${API_BASE}/api/tasks?regimen_id=${document.getElementById('regimen-id').value}`, true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4 && xhr.status === 200) {
      let tasks = JSON.parse(xhr.responseText);
      let selectedTask = tasks.find(t => t.id === taskId);
      if (selectedTask) {
        document.getElementById('task-id').value = selectedTask.id;
        document.getElementById('task-name').value = selectedTask.name;
        document.getElementById('task-desc').value = selectedTask.description;
        document.getElementById('task-dayoff').value = selectedTask.day_offset;
        document.getElementById('task-hour').value = selectedTask.hour;
        document.getElementById('task-min').value = selectedTask.minute;
        document.getElementById('task-vol').value = selectedTask.volume;
        document.getElementById('task-executed').checked = selectedTask.executed;
        document.getElementById('task-executed-at').value = selectedTask.executed_at || "";
        document.getElementById('task-comment').value = selectedTask.execution_comment || "";
      }
    }
  };
  xhr.send();
}



// ==================== ONLOAD ====================
document.addEventListener('DOMContentLoaded', function(){
  // Cargar PID, Plants, Regimens
  loadPID();
  loadPlants();
  loadRegimens();
  loadRegimensForSelect();
  // Iniciar auto-update del NodeMCU
  autoUpdateNodeStatus();
  loadTaskTimeline();
  setInterval(loadTaskTimeline, 10000);
});


// Función para habilitar el envío manual y actualizar la configuración
function enviarConfiguracion() {
  autoUpdateEnabled = true;
  updateNodeControl();
  // Opcional: si deseas que luego se vuelva a desactivar, puedes forzar:
  // autoUpdateEnabled = false;
}