async function api(url, method='GET', data=null) {
    const opts = { method };
    if (method === 'POST') {
        opts.headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
        opts.body = new URLSearchParams(data).toString();
    }
    if (method === 'GET' && data) {
        url += '?' + new URLSearchParams(data).toString();
    }
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(url + ' → ' + r.status);
    return await r.json();
}

function byId(id){ return document.getElementById(id); }

// ----- Control manual -----
byId('apply-setpoints').addEventListener('click', async () => {
    const payload = {
        setpoints: {
            slide: parseFloat(byId('setpoint_slide').value || '0'),
            angle: parseFloat(byId('setpoint_angle').value || '0'),
            volume: parseFloat(byId('setpoint_volume').value || '0'),
            valve_motor: parseFloat(byId('valve_motor').value || '0')
        }
    };
    try {
        await fetch('/entorno/actualizar_acciones', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        alert('Acciones enviadas');
    } catch (e) {
        alert('Error al enviar acciones: ' + e.message);
    }
});

// ----- Volumen -----
byId('send-volume').addEventListener('click', async () => {
    const payload = { setpoints: { volume: parseFloat(byId('vol_req').value || '0') } };
    await fetch('/entorno/actualizar_acciones', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
});

byId('reset-volume').addEventListener('click', async () => {
    await fetch('/entorno/actualizar_acciones', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reset_volume: true })
    });
});

// ----- Calibración -----
byId('apply-calib').addEventListener('click', async () => {
    const payload = {
        calibrations: {
            stepsPerMM: parseFloat(byId('steps_mm').value || '0'),
            stepsPerDegree: parseFloat(byId('steps_deg').value || '0')
        }
    };
    await fetch('/entorno/actualizar_acciones', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
});

// ----- PID switch -----
byId('pidSwitch').addEventListener('change', async e => {
    const payload = { manual_mode: e.target.checked ? 0 : 1 };
    await fetch('/entorno/actualizar_acciones', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
});

// ----- Régimenes -----
async function loadRegs(){
    const regs = await api('/api/regs');
    const list = byId('regs-list');
    const regSel = byId('plant-reg');
    const taskSel = byId('task-reg');
    list.innerHTML = '';
    regSel.innerHTML = '';
    taskSel.innerHTML = '';
    regs.forEach(r => {
        const li = document.createElement('li');
        li.className = 'list-group-item';
        li.textContent = `#${r.id} ${r.n}`;
        li.addEventListener('click', () => {
            byId('reg-id').value = r.id;
            byId('reg-name').value = r.n;
            byId('reg-desc').value = r.d;
        });
        list.appendChild(li);
        const opt1 = document.createElement('option');
        opt1.value = r.id; opt1.textContent = r.n;
        regSel.appendChild(opt1.cloneNode(true));
        taskSel.appendChild(opt1);
    });
}

document.getElementById('reg-form').addEventListener('submit', async e => {
    e.preventDefault();
    await api('/api/regs', 'POST', {
        id: byId('reg-id').value,
        n: byId('reg-name').value,
        d: byId('reg-desc').value
    });
    byId('reg-id').value='';
    byId('reg-name').value='';
    byId('reg-desc').value='';
    loadRegs();
});

byId('reg-del').addEventListener('click', async () => {
    const id = byId('reg-id').value;
    if (!id) return;
    if (confirm('¿Eliminar régimen #' + id + '?')) {
        await api('/api/regs', 'GET', { del: id });
        byId('reg-id').value='';
        byId('reg-name').value='';
        byId('reg-desc').value='';
        loadRegs();
    }
});

// ----- Plantas -----
async function loadPlants(){
    const plants = await api('/api/plants');
    const list = byId('plants-list');
    list.innerHTML = '';
    plants.forEach(p => {
        const li = document.createElement('li');
        li.className = 'list-group-item';
        li.textContent = `#${p.id} ${p.n}`;
        li.addEventListener('click', () => {
            byId('plant-id').value = p.id;
            byId('plant-name').value = p.n;
            byId('plant-desc').value = p.d;
            byId('plant-s1').value = p.s1;
            byId('plant-s2').value = p.s2;
            byId('plant-sp').value = p.sp;
            byId('plant-day').value = p.day;
            byId('plant-mon').value = p.mon;
            byId('plant-yr').value = p.yr;
            byId('plant-reg').value = p.reg;
        });
        list.appendChild(li);
    });
}

document.getElementById('plant-form').addEventListener('submit', async e => {
    e.preventDefault();
    await api('/api/plants', 'POST', {
        id: byId('plant-id').value,
        reg: byId('plant-reg').value,
        n: byId('plant-name').value,
        d: byId('plant-desc').value,
        s1: byId('plant-s1').value,
        s2: byId('plant-s2').value,
        sp: byId('plant-sp').value,
        day: byId('plant-day').value,
        mon: byId('plant-mon').value,
        yr: byId('plant-yr').value
    });
    byId('plant-id').value='';
    e.target.reset();
    loadPlants();
});

byId('plant-del').addEventListener('click', async () => {
    const id = byId('plant-id').value;
    if (!id) return;
    if (confirm('¿Eliminar planta #' + id + '?')) {
        await api('/api/plants', 'GET', { del: id });
        byId('plant-id').value='';
        loadPlants();
    }
});

// ----- Tareas -----
async function loadTasks(){
    const tasks = await api('/api/tasks');
    const list = byId('tasks-list');
    list.innerHTML = '';
    tasks.forEach(t => {
        const li = document.createElement('li');
        li.className = 'list-group-item';
        li.textContent = `#${t.id} (${t.reg}) ${t.n}`;
        li.addEventListener('click', () => {
            byId('task-id').value = t.id;
            byId('task-name').value = t.n;
            byId('task-desc').value = t.off;
            byId('task-off').value = t.off;
            byId('task-h').value = t.h;
            byId('task-m').value = t.m;
            byId('task-vol').value = t.vol;
            byId('task-reg').value = t.reg;
        });
        list.appendChild(li);
    });
}

document.getElementById('task-form').addEventListener('submit', async e => {
    e.preventDefault();
    await api('/api/tasks', 'POST', {
        id: byId('task-id').value,
        reg: byId('task-reg').value,
        n: byId('task-name').value,
        off: byId('task-off').value,
        h: byId('task-h').value,
        m: byId('task-m').value,
        vol: byId('task-vol').value,
        exe: 0
    });
    byId('task-id').value='';
    e.target.reset();
    loadTasks();
});

byId('task-del').addEventListener('click', async () => {
    const id = byId('task-id').value;
    if (!id) return;
    if (confirm('¿Eliminar tarea #' + id + '?')) {
        await api('/api/tasks', 'GET', { del: id });
        byId('task-id').value='';
        loadTasks();
    }
});

// ----- Inicial -----
window.addEventListener('DOMContentLoaded', () => {
    loadRegs().then(() => { loadPlants(); loadTasks(); });
    pollLogs();
    setInterval(pollLogs, 5000);
});

async function pollLogs(){
    try{
        const data = await api('/logs');
        byId('logs').innerHTML = data.logs.join('<br>');
        const logsDiv = byId('logs');
        logsDiv.scrollTop = logsDiv.scrollHeight;
    }catch(e){
        console.warn(e);
    }
}
