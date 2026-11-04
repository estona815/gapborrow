import { review } from './engine.mjs';
(() => {
  'use strict';
  const form = document.getElementById('review-form');
  const requestBody = document.getElementById('requests');
  const schedules = document.getElementById('schedules');
  const reasons = document.getElementById('reasons');
  const error = document.getElementById('error');
  const download = document.getElementById('download');
  const submit = form.querySelector('[type="submit"]');
  const fields = ['horizon', 'inspection', 'lateness'];
  const names = {strict:'Strict queue', gap:'Protected gaps', deadline:'Earliest deadline'};
  let requests = [], examples = [], report = null, revision = 0, dirty = true;
  const svgNS = 'http://www.w3.org/2000/svg';

  function markDirty() {
    revision += 1;
    dirty = true;
    download.disabled = true;
    schedules.classList.add('dirty');
    if (report) {
      reasons.textContent = 'Inputs changed. Recalculate to refresh the result.';
      schedules.setAttribute('aria-label', 'Previous schedule, before the inputs changed');
    }
  }

  function renderRequests() {
    requestBody.replaceChildren();
    requests.forEach((request, index) => {
      const tr = document.createElement('tr');
      const name = document.createElement('td');
      name.textContent = request.id;
      tr.appendChild(name);
      for (const [key,label] of [['release','Start'],['deadline','Deadline'],['duration','Duration']]) {
        const td = document.createElement('td');
        const input = document.createElement('input');
        input.type = 'number'; input.min = key==='release'?'0':'1'; input.max='48';
        input.required = true; input.value = request[key] ?? '';
        input.setAttribute('aria-label', request.id+' '+label);
        input.addEventListener('input', () => {
          request[key] = input.value===''?null:Number(input.value);
          markDirty();
        });
        td.appendChild(input); tr.appendChild(td);
      }
      const td = document.createElement('td');
      const remove = document.createElement('button');
      remove.type='button'; remove.className='delete'; remove.textContent='Remove';
      remove.setAttribute('aria-label', request.id+' Remove');
      remove.addEventListener('click', () => {
        requests.splice(index,1); renderRequests(); markDirty();
      });
      td.appendChild(remove); tr.appendChild(td); requestBody.appendChild(tr);
    });
    document.getElementById('add').disabled = requests.length>=30;
  }

  function svgElement(tag, attrs, text) {
    const el = document.createElementNS(svgNS,tag);
    Object.entries(attrs).forEach(([key,value])=>el.setAttribute(key,String(value)));
    if (text!==undefined) el.textContent=text;
    return el;
  }

  function drawTimelines() {
    if (!report) return;
    for (const key of Object.keys(names)) {
      const svg = document.getElementById('timeline-'+key);
      if (!svg) continue;
      const width = Math.max(70,svg.getBoundingClientRect().width);
      const edge=2, span=width-2*edge, h=report.input.horizon;
      const x=t=>edge+t/h*span;
      svg.setAttribute('viewBox',`0 0 ${width} 90`);
      svg.replaceChildren();
      const row=report.strategies[key];
      svg.setAttribute('aria-label',`${names[key]} ${row.served}/${report.input.requests.length} requests. `+row.bookings.map(b=>`${b.id} ${b.start}~${b.end} slots`).join(', '));
      svg.appendChild(svgElement('rect',{x:edge,y:32,width:span,height:38,fill:'var(--track)'}));
      let dense=false;
      row.bookings.forEach(b=>{
        const bar=svgElement('rect',{x:x(b.start),y:32,width:x(b.end)-x(b.start),height:38,fill:b.id===report.input.requests[0].id?'var(--blue)':'var(--gold)'});
        bar.appendChild(svgElement('title',{},`${b.id}: ${b.start}~${b.end} slots`));svg.appendChild(bar);
        if(x(b.end)-x(b.start)>=b.id.length*11+10) {
          svg.appendChild(svgElement('text',{x:(x(b.start)+x(b.end))/2,y:58,'text-anchor':'middle',class:'bar-id'},b.id));
        } else {dense=true;}
      });
      const details=document.getElementById('details-'+key);
      details.hidden=!dense;
      const step=width<260?Math.max(1,Math.ceil(h/2)):Math.max(1,Math.ceil(h/8));
      const ticks=new Set([0,h]);
      for(let t=step;t<h;t+=step)ticks.add(t);
      Array.from(ticks).sort((a,b)=>a-b).forEach(t=>{
        svg.appendChild(svgElement('line',{x1:x(t),x2:x(t),y1:21,y2:70,stroke:'#95a1ad','stroke-width':.7}));
        svg.appendChild(svgElement('text',{x:x(t),y:13,'text-anchor':t===0?'start':t===h?'end':'middle'},t));
      });
    }
  }

  function renderReport(data) {
    report=data; dirty=false;
    schedules.classList.remove('dirty'); schedules.setAttribute('aria-label','Compare booking policies');
    schedules.replaceChildren();
    for(const key of Object.keys(names)) {
      const row=document.createElement('div'); row.className='chart-row';
      const label=document.createElement('div'); label.className='chart-label'; label.textContent=names[key];
      const svg=svgElement('svg',{id:'timeline-'+key,role:'img'});
      const count=document.createElement('div'); count.className='chart-count'; count.textContent=`${data.strategies[key].served}/${data.input.requests.length} requests`;
      const details=document.createElement('details');details.id='details-'+key;details.className='dense-bookings';details.hidden=true;
      const summary=document.createElement('summary');summary.textContent='Show exact booking times';details.appendChild(summary);
      const list=document.createElement('ul');
      data.strategies[key].bookings.forEach(b=>{const li=document.createElement('li');li.textContent=`${b.id} · ${b.start}~${b.end} slots`;list.appendChild(li);});
      details.appendChild(list);
      row.append(label,svg,count,details); schedules.appendChild(row);
    }
    reasons.replaceChildren();
    const refused=data.strategies.gap.reasons;
    if (!refused.length) reasons.textContent='All requests were scheduled.';
    for(const reason of refused) {
      const p=document.createElement('p'); p.textContent=reason.id+' · '+reason.message;
      reasons.appendChild(p);
      const alternate = document.createElement('p');
      const slot = reason.alternative;
      alternate.textContent = slot
        ? 'Alternative: slots ' + slot.start + '–' + slot.end + ' · deadline extension: ' + slot.deadline_extension + ' slots (individual review only)'
        : 'No alternative fits within the operating horizon without moving bookings.';
      reasons.appendChild(alternate);
    }
    drawTimelines(); download.disabled=false;
  }

  async function calculate() {
    if (!form.reportValidity()) return;
    const runRevision=revision;
    const payload={requests:requests.map(r=>({...r}))};
    fields.forEach(id=>payload[id]=Number(document.getElementById(id).value));
    error.hidden=true; submit.disabled=true; download.disabled=true;
    try {
      const data=review(payload);
      if(runRevision!==revision) return;
      renderReport(data);
    } catch(exc) {
      error.textContent=exc.message; error.hidden=false;
    } finally { submit.disabled=false; }
  }

  function loadExample(index) {
    const example=examples[index];
    if(!example)return;
    requests=example.requests.map(r=>({...r}));
    document.getElementById('horizon').value=example.horizon;
    document.getElementById('inspection').value=example.turnaround;
    document.getElementById('lateness').value=0;
    renderRequests(); markDirty(); calculate();
  }

  fields.forEach(id=>document.getElementById(id).addEventListener('input',markDirty));
  form.addEventListener('submit',event=>{event.preventDefault();calculate();});
  document.getElementById('example').addEventListener('change',event=>loadExample(Number(event.target.value)));
  document.getElementById('add').addEventListener('click',()=>{
    let next=0,id;
    do{id=next<26?String.fromCharCode(65+next):'R'+(next+1);next++;}while(requests.some(r=>r.id===id));
    const horizon=Number(document.getElementById('horizon').value)||8;
    requests.push({id,release:0,deadline:horizon,duration:1});
    renderRequests(); markDirty();
  });
  download.addEventListener('click',()=>{
    if(!report||dirty)return;
    const blob=new Blob([JSON.stringify(report,null,2)+'\n'],{type:'application/json'});
    const url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download='gapborrow-browser-review.json';document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  new ResizeObserver(drawTimelines).observe(schedules);
  fetch('./cases.json').then(r=>{if(!r.ok)throw new Error('Could not load the synthetic examples.');return r.json();})
    .then(data=>{examples=data;loadExample(3);})
    .catch(exc=>{error.hidden=false;error.textContent=exc.message;});
})();
