/* --------------------------------------------------------------
 * panel.js – v10-may-2025
 * --------------------------------------------------------------
 *  • Compatible con firmware v7-CSV-FULL-fix (01-may-2025)
 *  • Incluye secciones completas: PID/FF, gráficas, CRUD, calendarios
 *  • Sin dependencias de jQuery en la lógica propia (evita conflictos)
 * -------------------------------------------------------------- */
window.addEventListener('DOMContentLoaded', () => {

  /* ===== Helpers DOM / HTTP ================================== */
  const qs  = s => document.querySelector(s);
  const qsa = s => Array.from(document.querySelectorAll(s));
  const api = (url, method='GET', data=null) => {
    if(method === 'GET' && data){
      const qs = new URLSearchParams(data).toString();
      url += (url.includes('?') ? '&' : '?') + qs;
    }
    return method === 'GET'
      ? fetch(url).then(r => {
          if (!r.ok) throw new Error(`${url} → ${r.status}`);
          return r.json();
        })
      : fetch(url,{
          method,
          headers:{'Content-Type':'application/x-www-form-urlencoded'},
          body:new URLSearchParams(data).toString()
        }).then(r=>{
          if (!r.ok) throw new Error(`${url} → ${r.status}`);
          return r.json();
        });
  };

  // Helper para peticiones POST con JSON
  const apiJson = (url, data={}) =>
    fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    }).then(r=>{ if(!r.ok) throw new Error(`${url} → ${r.status}`); return r.json(); });

  /* ===== Referencias UI ====================================== */
  const ui = {
    logs   : qs('#logs'),
    badge  : qs('#execBadge'),
    btn    : qs('#execBtn'),
    box    : qs('#execBox'),
    ip     : qs('#mcu-ip'),
    robot  : qs('#robot-select'),
    type   : qs('#robot-type'),
    sensors: qs('#robot-sensors'),
    motors : qs('#robot-motors'),
    cam    : qs('#cameraFeed'),
    ffCard : qs('#ff-card'),
    ffWrap : qs('#ff-switch-wrap')
  };
  const manualBtns = qsa('.manual-toggle');
  const energyWraps = qsa('.energy-wrap');
  // show energy controls by default; disabled state is managed later
  energyWraps.forEach(w=>w.style.display='');
  let autoExec=false, regs=[], plants=[], tasks=[], currentRegId=null,
      tick=0, editingTask=null, currentRobot=0,
      lastStatus=null, pidEditable=true, isBasicEnv=false,
      s1Target=90, s2Target=90, manualMode=false;

  const reloadCamera = () => {
    if(ui.cam) ui.cam.src = `/video_feed?ts=${Date.now()}`;
  };

  /* ===== Popup tareas ======================================= */
  const popup = qs('#taskPopup');
  if(popup) popup.addEventListener('click',e=>e.stopPropagation());
  const hidePopup = () => { if(popup) popup.classList.add('d-none'); };
  const showPopup = (html,x,y) => {
    if(!popup) return;
    popup.innerHTML = html;
    popup.style.left = `${x}px`;
    popup.style.top  = `${y}px`;
    popup.classList.remove('d-none');
    document.addEventListener('click', hidePopup, {once:true});
  };
  const showTaskPopup = (t,x,y) => {
    const html = `
      <h6>${t.n}</h6>
      <div>Día: ${t.off}</div>
      <div>Hora: ${String(t.h).padStart(2,'0')}:${String(t.m).padStart(2,'0')}</div>
      <div>Vol: ${(t.vol ?? 0)} ml</div>`;
    showPopup(html,x,y);
  };
  const showCreatePopup = (x,y) => {
    showPopup('<button id="popupCreateBtn" class="btn btn-sm btn-success">Crear tarea</button>',x,y);
    const btn = qs('#popupCreateBtn');
    if(btn) btn.onclick=hidePopup;
  };

  ['#initialDate','#plInitialDate'].forEach(sel=>{
    const el = qs(sel);
    if(el && !el.value)
      el.value = new Date().toISOString().slice(0,10);
  });


  async function loadIP(){
    try{
      const r = await api('/current_ip');
      if(ui.ip && r.ip) ui.ip.textContent = `IP: ${r.ip}`;
    }catch(e){console.warn(e);}
  }

  async function loadRobots(){
    if(!ui.robot) return;
    try{
      const list = await api('/api/robots');
      ui.robot.innerHTML = '';
      list.forEach((r,i)=>{
        const opt=document.createElement('option');
        opt.value=i;
        opt.textContent=`${r.name} (${r.ip})`;
        ui.robot.appendChild(opt);
      });
      ui.robot.disabled=false;
      ui.robot.style.display='';
      currentRobot = ui.robot.selectedIndex;
    }catch(e){
      console.warn('Robot list unavailable:',e);
      ui.robot.innerHTML='';
      ui.robot.disabled=true;
      ui.robot.style.display='none';
    }
  }

  async function loadRobotInfo(){
    try{
      const info = await api('/api/robot_info');
      if(ui.type && info.type) ui.type.textContent = `Tipo: ${info.type}`;
      if(ui.sensors && info.sensors){
        const names = info.sensors.map(s=>typeof s==='string'?s:(s.id||s.name));
        ui.sensors.textContent = `Sensores: ${names.join(', ')}`;
      }
      if(ui.motors && info.motors){
        const names = info.motors.map(m=>typeof m==='string'?m:(m.id||m.name));
        ui.motors.textContent = `Actuadores: ${names.join(', ')}`;
      }
      isBasicEnv = info.type === 'basic_env';
      pidEditable = info.pidEditable !== false;
      if(!pidEditable){
        pidSw.checked = false;
        pidSw.disabled = true;
        pidCtrls.style.display = 'none';
      }
      const pidS1 = qs('#pid-s1');
      const pidS2 = qs('#pid-s2');
      if(pidS1) pidS1.style.display = isBasicEnv ? '' : 'none';
      if(pidS2) pidS2.style.display = isBasicEnv ? '' : 'none';

      const motors = info.motorInfo || info.motors || [];
      const valve = motors.find(m => m.type && m.type !== 'servo');
      const useFF = !valve || valve.type !== 'pump';
      if(ui.ffCard) ui.ffCard.style.display = useFF ? '' : 'none';
      if(ui.ffWrap) ui.ffWrap.style.display = useFF ? '' : 'none';
      if(!useFF){
        ffSw.checked = false;
        ffEq.style.display = 'none';
      }
      togglePid();
      reloadCamera();
    }catch(e){ console.warn('robot info', e); }
  }

  /* ===== Sliders (noUiSlider) ================================ */
  const mk = (sel,min,max,step,start,out,cb)=>{
    noUiSlider.create(qs(sel),{start,step,range:{min,max}});
    qs(sel).noUiSlider.on('update',(_,__,v)=>
      qs(out).textContent = (+v).toFixed(step<1 ? 1 : 0)
    );
    if(cb) qs(sel).noUiSlider.on('change',(_,__,v)=>cb(+v));
  };
  mk('#servo-slider',50,180,1,170,'#servo-val',
     v=>api(`/control?servo=${Math.round(v)}`));
  mk('#s1-slider',0,180,1,90,'#s1-val',
     v=>{ s1Target=v; api(`/control?servo=${Math.round(v)}&pin=1`); });
  mk('#s2-slider',0,180,1,90,'#s2-val',
     v=>{ s2Target=v; api(`/control?servo=${Math.round(v)}&pin=2`); });
  mk('#flow-slider',0,30,0.1,0,'#flow-val',
     v=>api(`/control?flow=${v}`));

  const mkEnergy = (sel,out,btn,comp)=>{
    const el = qs(sel); if(!el) return;
    noUiSlider.create(el,{start:0,step:1,range:{min:-255,max:255}});
    el.noUiSlider.on('update',(_,__,v)=> qs(out).textContent=Math.round(v));
    qs(btn)?.addEventListener('click',()=>{
      const v = Math.round(el.noUiSlider.get());
      const d={manual_mode:1,motor_energies:{}};
      d.motor_energies[comp]=v;
      apiJson('/entorno/actualizar_acciones',d).catch(console.warn);
    });
  };
  mkEnergy('#energy-corredera-slider','#energy-corredera-val','#energy-corredera-btn','corredera');
  mkEnergy('#energy-angulo-slider','#energy-angulo-val','#energy-angulo-btn','angulo');
  mkEnergy('#energy-valvula-slider','#energy-valvula-val','#energy-valvula-btn','valvula');

  /* mostrar gráficas al abrir config PID */
  const pidS1Col = $('#pidS1Collapse');
  const pidS2Col = $('#pidS2Collapse');
  pidS1Col.on('shown.bs.collapse',()=>{
    $('#s1-chart-card').show();
    $('#s1ChartCollapse').collapse('show');
  }).on('hidden.bs.collapse',()=>{
    $('#s1-chart-card').hide();
    $('#s1ChartCollapse').collapse('hide');
  });
  pidS2Col.on('shown.bs.collapse',()=>{
    $('#s2-chart-card').show();
    $('#s2ChartCollapse').collapse('show');
  }).on('hidden.bs.collapse',()=>{
    $('#s2-chart-card').hide();
    $('#s2ChartCollapse').collapse('hide');
  });

  /* ===== Switches PID / FF =================================== */
  const pidSw=qs('#pid-swch'), ffSw=qs('#ff-swch');
  const pidCtrls=qs('#pidControls'), ffEq=qs('#ffEqInline');
  const pidBadge=qs('#pid-active');
  const togglePid=()=>{
    pidCtrls.style.display=pidSw.checked?'':'none';
    if(pidBadge){
      pidBadge.textContent=pidSw.checked?'ON':'OFF';
      pidBadge.className=`badge badge-${pidSw.checked?'success':'secondary'} ml-1`;
    }
    if(pidEditable)
      api(`/control?pid=${pidSw.checked?1:0}`);
  };
  const toggleFf =()=>{ ffEq.style.display =ffSw.checked?'block':'none';
                        api(`/control?ff=${ffSw.checked?1:0}`); };
  pidSw.addEventListener('change',togglePid);
  ffSw .addEventListener('change',toggleFf);
  togglePid(); toggleFf();
  qs('#pid-valve-send')?.addEventListener('click',()=>{
    if(!pidEditable) return;
    const data={
      kp:qs('#pid-kp').value||0,
      ki:qs('#pid-ki').value||0,
      kd:qs('#pid-kd').value||0
    };
    api('/control','POST',data);
  });

  qs('#pid-s1-send')?.addEventListener('click',()=>{
    if(!pidEditable || !isBasicEnv) return;
    const data={
      kpa:qs('#pida-kp').value||0,
      kia:qs('#pida-ki').value||0,
      kda:qs('#pida-kd').value||0
    };
    api('/control','POST',data);
  });

  qs('#pid-s2-send')?.addEventListener('click',()=>{
    if(!pidEditable || !isBasicEnv) return;
    const data={
      kpc:qs('#pidc-kp').value||0,
      kic:qs('#pidc-ki').value||0,
      kdc:qs('#pidc-kd').value||0
    };
    api('/control','POST',data);
  });

  qs('#pid-cal').onclick = async () => {
    if(!pidEditable) return;
    const btn = qs('#pid-cal');
    btn.disabled = true;
    try {
      const r = await api('/api/calibrate_pid');
      if (r.error) throw new Error(r.error);
      alert(`PID calibrado: Kp=${(+r.kp).toFixed(2)} Ki=${(+r.ki).toFixed(2)} Kd=${(+r.kd).toFixed(2)}`);
      qs('#pid-kp').value = (+r.kp).toFixed(2);
      qs('#pid-ki').value = (+r.ki).toFixed(2);
      qs('#pid-kd').value = (+r.kd).toFixed(2);
      refreshStatus();
    } catch(e){
      alert(`Calibración PID no disponible: ${e.message}`);
    } finally {
      btn.disabled = false;
    }
  };

  /* ===== Ejecución automática ================================ */
  ui.btn.onclick=()=>api(`/control?ejec=${autoExec?0:1}`)
                    .then(refreshStatus).catch(alert);

  manualBtns.forEach(btn=>{
    btn.addEventListener('click',()=>{
      const next = manualMode ? 0 : 1;
      apiJson('/entorno/actualizar_acciones',{manual_mode:next})
        .then(refreshStatus).catch(e=>alert(e.message));
    });
  });

  /* ===== Gráfica Flujo vs SP ================================ */
  const ctxFlow=qs('#chart').getContext('2d');
  const flowData={labels:[],datasets:[
    {label:'Flujo',data:[],borderWidth:1,fill:false},
    {label:'Setpoint',data:[],borderWidth:1,fill:false,borderDash:[4,4]}
  ]};
  const chartFlow=new Chart(ctxFlow,{type:'line',data:flowData,
    options:{responsive:true,animation:false,maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},scales:{x:{display:false}}}});

  /* ===== Gráficas Corredera / Ángulo ======================= */
  let chartS1=null,chartS2=null;
  const dataS1={labels:[],datasets:[
    {label:'Corredera',data:[],borderWidth:1,fill:false},
    {label:'Setpoint',data:[],borderWidth:1,fill:false,borderDash:[4,4]}
  ]};
  const dataS2={labels:[],datasets:[
    {label:'Ángulo',data:[],borderWidth:1,fill:false},
    {label:'Setpoint',data:[],borderWidth:1,fill:false,borderDash:[4,4]}
  ]};
  if(qs('#chart-s1')){
    chartS1=new Chart(qs('#chart-s1').getContext('2d'),{
      type:'line',data:dataS1,
      options:{responsive:true,animation:false,maintainAspectRatio:false,
        interaction:{mode:'index',intersect:false},scales:{x:{display:false}}}
    });
  }
  if(qs('#chart-s2')){
    chartS2=new Chart(qs('#chart-s2').getContext('2d'),{
      type:'line',data:dataS2,
      options:{responsive:true,animation:false,maintainAspectRatio:false,
        interaction:{mode:'index',intersect:false},scales:{x:{display:false}}}
    });
  }

  /* ===== Gráfica Feed-Forward ================================ */
  const ctxFF=qs('#ff-chart').getContext('2d');
  const chartFF=new Chart(ctxFF,{type:'scatter',
    data:{datasets:[{data:[],pointRadius:3}]},
    options:{responsive:true,animation:false,maintainAspectRatio:false,
             plugins:{legend:{display:false}}}});

  async function loadFF(){
    const card = ui.ffCard;
    if(card && card.style.display === 'none') return;
    try{
      const ff = await api('/getFeedForward');
      qs('#ff-eq').textContent=`y = ${(+ff.b0).toFixed(3)}·x + ${(+ff.a0).toFixed(1)}`;
      chartFF.data.datasets[0].data=ff.flow.map((f,i)=>({x:f,y:ff.angle[i]}));
      chartFF.update('none');
    }catch(e){console.warn(e);}
  }

  qs('#btn-cal').onclick = async () => {
    const btn = qs('#btn-cal');
    const st  = qs('#cal-status');
    btn.disabled = true;
    st.textContent = 'Calibrando...';
    try {
      const r = await api('/api/calibrate_flow');
      if (r.error) throw new Error(r.error);
      st.textContent = 'OK';
      await loadFF();
      refreshStatus();
    } catch(e){
      try{
        await api('/calibrateFeedForward');
        st.textContent = 'OK';
        await loadFF();
        refreshStatus();
      }catch(e2){
        st.textContent = 'Error';
        alert(`Error calibrando flujo: ${e2.message}`);
      }
    } finally {
      btn.disabled = false;
    }
  };

  /* ===== Status & Logs ======================================= */
  async function refreshStatus(){
    try{
      const st = await api('/status');
      lastStatus = st;
      manualMode = !!st.manualMode;
      manualBtns.forEach(btn=>{
        btn.textContent = manualMode ? 'Desactivar modo manual' : 'Activar modo manual';
      });
      // ensure energy controls stay visible but toggle interactivity via disabled state
      energyWraps.forEach(w=>w.style.display='');
      const setDisabled = (sel,dis)=>{
        const el = qs(sel); if(!el || !el.noUiSlider) return;
        if(dis){ el.setAttribute('disabled',true); }
        else { el.removeAttribute('disabled'); }
      };
      ['#s1-slider','#s2-slider','#servo-slider','#flow-slider'].forEach(sel=>setDisabled(sel,manualMode));
      ['#energy-corredera-slider','#energy-angulo-slider','#energy-valvula-slider']
        .forEach(sel=>setDisabled(sel,!manualMode));
      ['#energy-corredera-btn','#energy-angulo-btn','#energy-valvula-btn']
        .forEach(sel=>{const b=qs(sel); if(b) b.disabled=!manualMode;});
      pidSw.checked = !!st.pidOn;
      if(pidBadge){
        pidBadge.textContent = st.pidOn ? 'ON':'OFF';
        pidBadge.className = `badge badge-${st.pidOn?'success':'secondary'} ml-1`;
      }
      pidCtrls.style.display = pidSw.checked ? '' : 'none';

      if(isBasicEnv){
        qs('#pidc-kp-cur').textContent = (+st.KpC).toFixed(2);
        qs('#pidc-ki-cur').textContent = (+st.KiC).toFixed(2);
        qs('#pidc-kd-cur').textContent = (+st.KdC).toFixed(2);

        qs('#pida-kp-cur').textContent = (+st.KpA).toFixed(2);
        qs('#pida-ki-cur').textContent = (+st.KiA).toFixed(2);
        qs('#pida-kd-cur').textContent = (+st.KdA).toFixed(2);
      }

      qs('#pid-kp-cur').textContent  = (+st.Kp).toFixed(1);
      qs('#pid-ki-cur').textContent  = (+st.Ki).toFixed(1);
      qs('#pid-kd-cur').textContent  = (+st.Kd).toFixed(1);

      qs('#servo-real').textContent = `${(+st.servo).toFixed(0)}°`;
      qs('#s1-real').textContent    = `${(+st.s1).toFixed(0)}°`;
      qs('#s2-real').textContent    = `${(+st.s2).toFixed(0)}°`;
      qs('#flow-real').textContent  = `${(+st.flow).toFixed(1)} ml/s`;

      // sync sliders with real readings so UI and charts share the same source
      qs('#s1-slider')?.noUiSlider?.set(+st.s1);
      qs('#s2-slider')?.noUiSlider?.set(+st.s2);
      qs('#servo-slider')?.noUiSlider?.set(+st.servo);
      qs('#flow-slider')?.noUiSlider?.set(+st.setpoint);

      if(!manualMode){
        qs('#energy-corredera-slider')?.noUiSlider?.set(st.energyCorredera ?? 0);
        qs('#energy-angulo-slider')?.noUiSlider?.set(st.energyAngulo ?? 0);
        qs('#energy-valvula-slider')?.noUiSlider?.set(st.energyValvula ?? 0);
        // keep chart targets aligned with current positions
        s1Target = +st.s1;
        s2Target = +st.s2;
      }

      autoExec=!!st.autoExecEnabled;
      ui.badge.textContent=autoExec?'⏳ En ejecución automática':'✔ Sistema en espera';
      ui.badge.className=`badge badge-${autoExec?'info':'success'}`;
      ui.btn.textContent=autoExec?'Detener ejecución':'Activar ejecución';
      ui.btn.className=`btn btn-sm btn-${autoExec?'danger':'primary'} ml-2`;
      ui.box.classList.toggle('bg-info',autoExec);
      ui.box.classList.toggle('bg-light',!autoExec);

      flowData.labels.push(tick++);
      flowData.datasets[0].data.push(+st.flow);
      flowData.datasets[1].data.push(+st.setpoint);
      if(flowData.labels.length>120){
        flowData.labels.shift();
        flowData.datasets.forEach(d=>d.data.shift());
      }
      chartFlow.update('none');

      if(chartS1){
        dataS1.labels.push(tick);
        dataS1.datasets[0].data.push(+st.s1);
        dataS1.datasets[1].data.push(+s1Target);
        if(dataS1.labels.length>120){
          dataS1.labels.shift();
          dataS1.datasets.forEach(d=>d.data.shift());
        }
        chartS1.update('none');
      }

      if(chartS2){
        dataS2.labels.push(tick);
        dataS2.datasets[0].data.push(+st.s2);
        dataS2.datasets[1].data.push(+s2Target);
        if(dataS2.labels.length>120){
          dataS2.labels.shift();
          dataS2.datasets.forEach(d=>d.data.shift());
        }
        chartS2.update('none');
      }

      qs('#node-vol-req').textContent      =(+st.volReq       ).toFixed(1);
      qs('#node-vol-disp-task').textContent=(+st.volDispTask  ).toFixed(1);
      qs('#node-vol-disp-day').textContent =(+st.volDispAcumDay).toFixed(1);
    }catch(e){console.warn(e);}
  }
  async function pollLogs(){
    try{
      const l=await api('/logs');
      ui.logs.innerHTML=l.logs.slice().reverse().join('<br>');
    }catch(e){console.warn(e);}
  }

  /* ===== CRUD: Regímenes, Plantas, Tareas ==================== */
  const updateRgBtn = () => {
    const btn = qs('#rg-save');
    if (btn) btn.textContent = (qs('#rg-id').value || '').trim() ? 'Actualizar' : 'Guardar';
  };
  async function loadRegs(){
    regs=await api('/api/regs');
    const list=qs('#rg-list'); list.innerHTML='';
    const sel=qs('#pl-reg');   sel.innerHTML='<option value="">-- Régimen --</option>';
    regs.forEach(r=>{
      const li=document.createElement('li');
      li.className='list-group-item d-flex flex-column flex-sm-row align-items-sm-center';
      li.innerHTML=`<img src="img/reg-default.png" class="list-img mr-sm-2 mb-1 mb-sm-0">`+
                  `<span class="badge badge-primary badge-mini mr-sm-2">#${r.id}</span>`+
                  `<span class="name text-truncate">${r.n}</span>`;
      li.onclick=()=>{
        currentRegId=r.id;
        qs('#rg-id').value=r.id;
        qs('#rg-name').value=r.n;
        qs('#rg-desc').value=r.d;
        list.querySelectorAll('li').forEach(it=>it.classList.remove('selected'));
        li.classList.add('selected');
        loadCalendarTasks();
        updateRgBtn();
      };
      list.appendChild(li);

      if(r.id===currentRegId) li.classList.add('selected');

      const opt=document.createElement('option');
      opt.value=r.id; opt.textContent=r.n; sel.appendChild(opt);
    });
    updateRgBtn();
  }
  async function loadPlants(){
    plants=await api('/api/plants');
    const list=qs('#pl-list'); list.innerHTML='';
    plants.forEach(p=>{
      const li=document.createElement('li');
      li.className='list-group-item d-flex flex-column flex-sm-row align-items-sm-center';
      li.innerHTML=`<img src="img/plant-default.png" class="list-img mr-sm-2 mb-1 mb-sm-0">`+
                  `<span class="badge badge-success badge-mini mr-sm-2">#${p.id}</span>`+
                  `<span class="name text-truncate">${p.n}</span>`;
      li.onclick=()=>{
        selectPlant(p);
        const card=qs('#pl-task-card');
        if(card){
          card.classList.remove('d-none');
          const reg=regs.find(r=>r.id==p.reg);
          qs('#pl-task-regname').textContent=reg?reg.n:'';
        }
      };
      list.appendChild(li);
    });
  }
  function selectPlant(p){
    qs('#pl-id').value=p.id; qs('#pl-name').value=p.n; qs('#pl-desc').value=p.d;
    qs('#pl-s1').value=p.s1; qs('#pl-s2').value=p.s2; qs('#pl-sp').value=p.sp;
    qs('#pl-reg').value=p.reg;
    const plInit=qs('#plInitialDate');
    if(plInit)
      plInit.value=`${p.yr.toString().padStart(4,'0')}-${p.mon.toString().padStart(2,'0')}-${p.day.toString().padStart(2,'0')}`;
    currentRegId=p.reg; loadCalendarTasks();
  }

  /* ===== Calendarios ========================================= */
  function buildCalendar(containerSel, list, sliderSel, labelSel, dateSel){
    const cont=qs(containerSel); cont.innerHTML='';
    const slider=qs(sliderSel); const label=qs(labelSel);
    const dEl = qs(dateSel);
    const week = parseInt(slider.value||'0',10);
    const baseDateStr = dEl && dEl.value ? dEl.value : new Date().toISOString().slice(0,10);
    const [yy,mm,dd] = baseDateStr.split('-').map(Number);
    const baseDate = new Date(yy,mm-1,dd); // parse as local date
    label.textContent=week;
    const startDow=(baseDate.getDay()+6)%7;
    const monday=new Date(baseDate);
    monday.setDate(baseDate.getDate()-startDow + week*7);
    monday.setHours(0,0,0,0);
    /* cabecera */
    cont.innerHTML='<div class="time-cell day-header"></div>';
    const highlightStart = containerSel === '#pl-calendar' ||
                           containerSel === '#calendar';
    ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'].forEach((d,i)=>{
      const dd=new Date(monday); dd.setDate(monday.getDate()+i);
      const cls=highlightStart && week===0 && i===startDow ? ' start-date' : '';
      cont.innerHTML+=`<div class="day-header${cls}">${d} ${String(dd.getDate()).padStart(2,'0')}/${String(dd.getMonth()+1).padStart(2,'0')}</div>`;
    });
    /* cuerpo 24 x 7 */
    for(let h=0;h<24;h++){
      cont.innerHTML+=`<div class="time-cell">${String(h).padStart(2,'0')}:00</div>`;
      for(let d=0;d<7;d++){
        const cls=highlightStart && week===0 && d===startDow ? ' start-date' : '';
        cont.innerHTML+=`<div class="day-cell${cls}"></div>`;
      }
    }
    const cells=[...cont.children];
    const idx=(d,h)=>(h+1)*8+d+1;   // celda según día y hora
    /* marca “ahora” en el calendario dash */
    if(containerSel==='#dash-calendar'){
      const now=new Date();
      const cell=cells[idx((now.getDay()+6)%7,now.getHours())];
      if(cell){
        cell.classList.add('highlight-now');
        const ln=document.createElement('div');
        ln.className='time-now-line';
        ln.style.top=`${(now.getMinutes()/60)*24}px`;
        cell.appendChild(ln);
      }
    }
    /* pinta los eventos */
    const CELL_H=24;
    list.forEach(t=>{
      const dayOfWeek = startDow + t.off - week*7;
      if(dayOfWeek < 0 || dayOfWeek > 6) return;
      const c=cells[idx(dayOfWeek,t.h)]; if(!c)return;
      const siblings=list.filter(u=>u.off==t.off&&u.h==t.h).sort((a,b)=>a.m-b.m);
      const w=100/siblings.length, pos=siblings.findIndex(u=>u.id==t.id);
      const ev=document.createElement('div');
      ev.className='event';
      ev.dataset.id=t.id;
      ev.style.cssText=`top:${2+(t.m/60)*CELL_H}px; left:calc(${w*pos}% + 2px); width:calc(${w}% - 4px); height:${CELL_H-4}px;
                       background:${t.exe?'#28a745':'#007bff'};`;
      ev.textContent=`${String(t.h).padStart(2,'0')}:${String(t.m).padStart(2,'0')} ${t.n}`;
      c.appendChild(ev);
    });
  }

  function enableEmptyCellClicks(cid,pref,list,sliderSel,dateSel){
    const slider = qs(sliderSel);
    const dateInput = qs(dateSel);
    qs(`#${cid}`).querySelectorAll('.day-cell').forEach((cell,i)=>{
      cell.onclick=e=>{
        qs(`#${cid}`).querySelectorAll('.day-cell.selected')
                     .forEach(c=>c.classList.remove('selected'));
        cell.classList.add('selected');
        const row=Math.floor(i/7), col=i%7; // horario 0-23, columnas 0-6
        const week = parseInt(slider?.value || '0',10);
        let base = new Date();
        if(dateInput && dateInput.value){
          const [y,m,d] = dateInput.value.split('-').map(Number);
          base = new Date(y, m-1, d); // local date, no timezone shift
        }
        const startDow=(base.getDay()+6)%7;
        ['Id','Name','Day','Hour','Minute','Volume'].forEach(f=>{
          const el=qs(`#${pref}${f}`);
          if(!el) return;
          if(f==='Day')      el.value = week*7 + col - startDow;
          else if(f==='Hour')el.value = row;
          else               el.value = '';
        });
        qs(`#${pref}Status`).textContent='Estado: --';
        (pref==='plDetail'?qs('#btnSavePlTask'):qs('#btnSaveTask')).textContent='Guardar';
        const unmarkBtn = pref==='plDetail'?qs('#btnUnmarkPlTask'):qs('#btnUnmarkTask');
        if(unmarkBtn) unmarkBtn.textContent = 'Marcar ejecutada';
        editingTask=null;
        showCreatePopup(e.clientX,e.clientY);
      };
    });
  }
  function enableTaskClicks(arr,pref,containerSel,openReg){
    setTimeout(() => {
      const scope = containerSel ? qs(containerSel) : document;
      if(!scope) return;
      scope.querySelectorAll('.event').forEach(ev => {
        ev.onclick = e => {
          e.stopPropagation();
          const t = arr.find(x => x.id == ev.dataset.id);
          if(!t) return;
          editingTask = t;
          const map = {
            Id: 'id',
            Name: 'n',
            Day: 'off',
            Hour: 'h',
            Minute: 'm',
            Volume: 'vol'
          };
          ['Id','Name','Day','Hour','Minute','Volume'].forEach(f => {
            const el = qs(`#${pref}${f}`);
            if(!el) return;
            const key = map[f];
            el.value = key === 'vol' ? (t[key] ?? 0) : t[key];
          });
          qs(`#${pref}Status`).textContent = `Estado: ${t.exe ? 'Ejecutada' : 'No ejecutada'}`;
          qs(`#${pref}Status`).className = `badge badge-${t.exe ? 'success' : 'secondary'}`;
          const unmarkBtn = pref === 'plDetail' ? qs('#btnUnmarkPlTask') : qs('#btnUnmarkTask');
          if(unmarkBtn) unmarkBtn.textContent = t.exe ? 'Marcar no ejecutada' : 'Marcar ejecutada';
          (pref === 'plDetail' ? qs('#btnSavePlTask') : qs('#btnSaveTask')).textContent = 'Modificar';
          if(openReg) showTab('#reg');
          showTaskPopup(t,e.clientX,e.clientY);
        };
      });
    },50);
  }

  async function loadCalendarTasks(){
    tasks=await api('/api/tasks');
    /* régimen actual (tab reg) */
    const filt=currentRegId?tasks.filter(t=>t.reg==currentRegId):tasks;
    const title=qs('#currentRegName');
    if(title){
      const reg=regs.find(r=>r.id==currentRegId);
      title.textContent=reg?`Régimen: ${reg.n}`:'';
    }
    buildCalendar('#calendar',filt,'#weekSlider','#weekLabel','#initialDate');
    enableTaskClicks(filt,'detail','#calendar',false); enableEmptyCellClicks('calendar','detail',filt,'#weekSlider','#initialDate');
    /* todas las tareas (dashboard) */
    buildCalendar('#dash-calendar',tasks,'#dashWeekSlider','#dashWeekLabel',null);
    enableTaskClicks(tasks,'detail','#dash-calendar',true);
    /* las del régimen de la planta seleccionada */
    const regId=qs('#pl-reg').value;
    const card=qs('#pl-task-card');
    if(card){
      if(regId){
        card.classList.remove('d-none');
        const reg=regs.find(r=>r.id==regId);
        qs('#pl-task-regname').textContent=reg?reg.n:'';
      }else{
        card.classList.add('d-none');
        qs('#pl-task-regname').textContent='';
      }
    }
    const fPl=tasks.filter(t=>t.reg==regId);
    buildCalendar('#pl-calendar',fPl,'#plWeekSlider','#plWeekLabel','#plInitialDate');
    enableTaskClicks(fPl,'plDetail','#pl-calendar',false); enableEmptyCellClicks('pl-calendar','plDetail',fPl,'#plWeekSlider','#plInitialDate');
  }

  /* ===== Tabs ================================================= */
  const showTab=id=>{
    qsa('.navbar-nav .nav-link').forEach(a=>
      a.classList.toggle('active',a.getAttribute('href')===id));
    qsa('.tab-pane').forEach(p=>{
      const on='#'+p.id===id;
      p.classList.toggle('show',on); p.classList.toggle('active',on);
    });
    if(id==='#dash'){
      chartFlow.resize();
      chartS1?.resize();
      chartS2?.resize();
    }
  };
  qsa('.navbar-nav .nav-link').forEach(a=>
    a.addEventListener('click',e=>{e.preventDefault();showTab(a.getAttribute('href'));}));

  ['#initialDate','#weekSlider','#dashWeekSlider','#plInitialDate','#plWeekSlider']
    .forEach(sel=>{ const el=qs(sel); if(el) el.addEventListener('input',loadCalendarTasks); });

  const nav=(i,p,n)=>{
    const inp=qs(i), prev=qs(p), next=qs(n);
    if(inp){
      if(prev) prev.addEventListener('click',()=>{inp.stepDown();inp.dispatchEvent(new Event('input'));});
      if(next) next.addEventListener('click',()=>{inp.stepUp();inp.dispatchEvent(new Event('input'));});
    }
  };
  nav('#weekSlider','#weekPrev','#weekNext');
  nav('#dashWeekSlider','#dashWeekPrev','#dashWeekNext');
  nav('#plWeekSlider','#plWeekPrev','#plWeekNext');

  /* ===== CRUD handlers ===================================== */
  const val = id => (qs(id)?.value || '').trim();

  const saveReg = async () => {
    await api('/api/regs','POST',{
      id: val('#rg-id'), n: val('#rg-name'), d: val('#rg-desc')
    });
    await loadRegs();
  };

  const delReg = async () => {
    const id = val('#rg-id');
    if(!id){
      alert('Seleccione un régimen primero');
      return;
    }
    if(!confirm(`¿Eliminar régimen #${id}?\nEsta acción no se puede deshacer.`)) return;
    try{
      await api(`/api/regs?del=${id}`); // el NodeMCU solo maneja ?del=ID
      alert('Régimen eliminado');
      qs('#rg-id').value='';
      qs('#rg-name').value='';
      qs('#rg-desc').value='';
      updateRgBtn();
      await loadRegs();
    }catch(err){
      alert(`Error al eliminar régimen: ${err.message}`);
    }
  };

  const savePlant = async () => {
    const start = val('#pl-start');
    const parts = start ? start.split('-') : [];
    await api('/api/plants','POST',{
      id: val('#pl-id'),
      reg: val('#pl-reg'),
      n: val('#pl-name'),
      d: val('#pl-desc'),
      s1: val('#pl-s1') || 90,
      s2: val('#pl-s2') || 90,
      sp: val('#pl-sp') || 1,
      day: parts[2] || 1,
      mon: parts[1] || 1,
      yr: parts[0] || 2025
    });
    await Promise.all([loadPlants(), loadCalendarTasks()]);
  };

  const delPlant = async () => {
    const pid = val('#pl-id');
    if(!pid) return;
    try{
      await api(`/api/plants?del=${pid}`); // NodeMCU espera ?del=ID
      qs('#pl-id').value='';
      qs('#pl-name').value='';
      qs('#pl-desc').value='';
      qs('#pl-reg').value='';
      const card=qs('#pl-task-card');
      if(card) card.classList.add('d-none');
      await Promise.all([loadPlants(), loadCalendarTasks()]);
    }catch(err){
      alert(`Error al eliminar planta: ${err.message}`);
    }
  };

  const saveTask = async pref => {
    await api('/api/tasks','POST',{
      id : val(`#${pref}Id`),
      reg: val('#rg-id') || val('#pl-reg'),
      n  : val(`#${pref}Name`),
      off: val(`#${pref}Day`),
      h  : val(`#${pref}Hour`),
      m  : val(`#${pref}Minute`),
      vol: val(`#${pref}Volume`)
    });
    await loadCalendarTasks();
  };

  qs('#rg-save')?.addEventListener('click', saveReg);
  qs('#rg-del') ?.addEventListener('click', delReg);
  qs('#rg-id') ?.addEventListener('input', updateRgBtn);
  qs('#pl-save')?.addEventListener('click', savePlant);
  qs('#pl-del') ?.addEventListener('click', delPlant);
  qs('#pl-reg') ?.addEventListener('change', () => {
    currentRegId = val('#pl-reg') ? parseInt(val('#pl-reg'),10) : null;
    loadCalendarTasks();
  });
  qs('#pl-copy-current')?.addEventListener('click', () => {
    const s1 = lastStatus?.s1 ?? lastStatus?.servo1 ??
               qs('#s1-slider')?.noUiSlider?.get();
    const s2 = lastStatus?.s2 ?? lastStatus?.servo2 ??
               qs('#s2-slider')?.noUiSlider?.get();
    const sp = lastStatus?.setpoint ?? qs('#flow-slider')?.noUiSlider?.get();
    if(s1 != null) qs('#pl-s1').value = Math.round(s1);
    if(s2 != null) qs('#pl-s2').value = Math.round(s2);
    if(sp != null) qs('#pl-sp').value = (+sp).toFixed(1);
  });
  qs('#btnSaveTask')?.addEventListener('click', () => saveTask('detail'));
  qs('#btnSavePlTask')?.addEventListener('click', () => saveTask('plDetail'));

  qs('#btnExecTask')?.addEventListener('click', async () => {
    if(!confirm('¿Ejecutar esta tarea?')) return;
    await api('/ejecutar_tarea', 'GET', { id: val('#detailId'), mark: true });
    await loadCalendarTasks();
  });

  qs('#btnUnmarkTask')?.addEventListener('click', async () => {
    await api('/api/tasks', 'POST', { id: val('#detailId'), exe: 0 });
    await loadCalendarTasks();
  });

  qs('#btnExecPlTask')?.addEventListener('click', async () => {
    if(!confirm('¿Ejecutar esta tarea?')) return;
    await api('/ejecutar_tarea', 'GET', { id: val('#plDetailId'), mark: true });
    await loadCalendarTasks();
  });

  qs('#btnUnmarkPlTask')?.addEventListener('click', async () => {
    await api('/api/tasks', 'POST', { id: val('#plDetailId'), exe: 0 });
    await loadCalendarTasks();
  });

  ui.robot?.addEventListener('change', async () => {
    const newIdx = ui.robot.value;
    if(!confirm('¿Cambiar de robot y recargar datos?')){
      ui.robot.value = currentRobot;
      return;
    }
    try{
      await api('/api/robots','POST',{index: newIdx});
      await loadRobots();
      currentRobot = ui.robot.selectedIndex;
      await Promise.all([loadRegs(), loadPlants(), loadRobotInfo()]);
      await loadCalendarTasks();
      await loadFF();
      await loadIP();
      refreshStatus();
      reloadCamera();
    }catch(e){
      alert(`Error seleccionando robot: ${e.message}`);
    }
  });

  /* ===== Cargas iniciales ==================================== */
  Promise.all([loadRegs(),loadPlants(),loadRobots(),loadRobotInfo()])
    .then(loadCalendarTasks)
    .then(loadFF)
    .then(loadIP)
    .then(()=>{ refreshStatus(); pollLogs(); reloadCamera();
                setInterval(refreshStatus,2000);
                setInterval(pollLogs,6000);
                setInterval(loadCalendarTasks,60000);
                showTab('#dash'); })
    .catch(err=>alert(`Error inicial: ${err.message}`));

}); /* DOMContentLoaded */
