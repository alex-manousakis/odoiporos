function parseGreekDate(value){
 const match=/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value);
 if(!match)return '';
 const day=Number(match[1]),month=Number(match[2]),year=Number(match[3]);
 const result=new Date(Date.UTC(year,month-1,day));
 if(result.getUTCFullYear()!==year||result.getUTCMonth()!==month-1||result.getUTCDate()!==day)return '';
 return result.toISOString().slice(0,10);
}
function formatGreekDate(value){const [year,month,day]=value.split('-');return `${day}/${month}/${year}`;}
// Double-click date shortcuts from the desktop travel form.
for(const [targetId,sourceId] of [
 ['id_return_at','id_departure_at'],
 ['id_work_starts_at','id_departure_at'],
 ['id_work_ends_at','id_return_at']
]){
 const target=document.getElementById(targetId);
 const source=document.getElementById(sourceId);
 if(!target||!source)continue;
 target.addEventListener('dblclick',()=>{
  if(target.matches(':disabled')||target.readOnly)return;
  const value=parseGreekDate(source.value);
  if(!value)return;
  target.value=formatGreekDate(value);
  target.dispatchEvent(new Event('input',{bubbles:true}));
  target.dispatchEvent(new Event('change',{bubbles:true}));
 });
}
const routes=JSON.parse(document.getElementById('routes-data').textContent);
const routeSelect=document.getElementById('id_route');
const search=document.getElementById('route-search');
const originalOptions=Array.from(routeSelect.options).map(o=>({value:o.value,text:o.text}));
search.addEventListener('input',()=>{const selected=routeSelect.value;routeSelect.replaceChildren();for(const o of originalOptions){if(!o.value||o.value===selected||o.text.toLocaleLowerCase('el').includes(search.value.toLocaleLowerCase('el'))){routeSelect.add(new Option(o.text,o.value,false,o.value===selected));}}});
function fillStops(select){const current=select.value;select.replaceChildren(new Option('---------',''));const route=routes.find(r=>String(r.id)===routeSelect.value);for(const stop of route?.stops||[])select.add(new Option(stop.city,stop.id,false,String(stop.id)===current));}
routeSelect.addEventListener('change',()=>document.querySelectorAll('#stays-rows select[name$="-stop"]').forEach(fillStops));
function addRow(prefix){const total=document.getElementById(`id_${prefix}-TOTAL_FORMS`);const index=Number(total.value);const html=document.getElementById(`${prefix}-empty`).innerHTML.replaceAll('__prefix__',index);document.getElementById(`${prefix}-rows`).insertAdjacentHTML('beforeend',html);total.value=index+1;const row=document.getElementById(`${prefix}-rows`).lastElementChild;if(prefix==='stays'){fillStops(row.querySelector('select[name$="-stop"]'));initializeStay(row);}return row;}
document.querySelectorAll('[data-add]').forEach(b=>b.addEventListener('click',()=>addRow(b.dataset.add)));

const accommodation=JSON.parse(document.getElementById('accommodation-data').textContent);
function updateStay(row){
 const kind=row.querySelector('[name$="-accommodation_type"]');
 const cost=row.querySelector('[name$="-estimated_cost"]');
 const selected=accommodation.types.find(t=>String(t.id)===kind.value);
 const excluded=row.querySelector('[name$="-is_excluded"]')?.checked;
 cost.disabled=!selected?.has_cost||excluded;
 cost.required=Boolean(!excluded && selected?.has_cost && row.querySelector('input[data-greek-date]').value);
 if(selected && !selected.has_cost)cost.value='';
 cost.placeholder=selected&&!selected.has_cost?'Χωρίς κόστος':'0,00';
}
function initializeStay(row){
 const kind=row.querySelector('[name$="-accommodation_type"]');
 if(!kind.value && accommodation.default && row.querySelector('input[data-greek-date]').value)kind.value=accommodation.default;
 updateStay(row);
}
document.querySelectorAll('#stays-rows .stay-row').forEach(updateStay);
document.getElementById('stays-rows').addEventListener('change',event=>{const row=event.target.closest('.stay-row');if(row)updateStay(row);});
// Reconcile the interval, retaining row identity and values for unchanged dates.
function synchronizeNights(){
 const start=parseGreekDate(document.getElementById('id_departure_at').value);
 const end=parseGreekDate(document.getElementById('id_return_at').value);
 const message=document.getElementById('night-message');
 if(!start||!end||end<start||!routeSelect.value){message.textContent='Συμπληρώστε διαδρομή και έγκυρες ημερομηνίες ταξιδιού.';return;}
 const count=(Date.parse(end)-Date.parse(start))/86400000;
 if(count>366){message.textContent='Για διάστημα άνω των 366 ημερών χρειάζεται έλεγχος.';return;}
 const wanted=[];
 for(let day=new Date(start+'T00:00:00Z');day<new Date(end+'T00:00:00Z');day.setUTCDate(day.getUTCDate()+1))wanted.push(day.toISOString().slice(0,10));
 const container=document.getElementById('stays-rows');
 const rows=Array.from(container.querySelectorAll('.stay-row'));
 const byDate=new Map();
 for(const row of rows){
  const value=parseGreekDate(row.querySelector('input[data-greek-date]').value);
  if(value&&!byDate.has(value))byDate.set(value,row);
  row.hidden=true;row.querySelector('[name$="-DELETE"]').checked=true;
  row.querySelectorAll('input,select').forEach(control=>{if(control.type!=='hidden'&&!control.name.endsWith('-DELETE'))control.disabled=true;});
 }
 for(const value of wanted){
  let row=byDate.get(value);
  if(!row){row=addRow('stays');row.querySelector('input[data-greek-date]').value=formatGreekDate(value);}
  row.hidden=false;row.querySelector('[name$="-DELETE"]').checked=false;
  row.querySelectorAll('input,select').forEach(control=>control.disabled=false);
  const stops=row.querySelector('select[name$="-stop"]');
  fillStops(stops);if(!stops.value&&stops.options.length>1)stops.selectedIndex=1;
  initializeStay(row);container.appendChild(row);
 }
 message.textContent=count?`${count} νύχτες από τις ημερομηνίες ταξιδιού. Ελέγξτε πόλη, τύπο και κόστος.`:'Δεν προκύπτει διανυκτέρευση.';
}
for(const id of ['id_departure_at','id_return_at','id_route'])document.getElementById(id).addEventListener('change',synchronizeNights);
synchronizeNights();

const modes=JSON.parse(document.getElementById('transport-data').textContent);
function updateSingleTransport(){
 const select=document.getElementById('id_transport');
 const mode=modes.find(m=>String(m.id)===select.value);
 const route=routes.find(r=>String(r.id)===routeSelect.value);
 for(const id of ['single-ticket-cost','single-transfer-cost']){
  const group=document.getElementById(id);group.hidden=!mode?.has_ticket_cost;
  // Disabled controls are ignored by the server; entered values stay available if toggled back.
  group.querySelector('input').disabled=!mode?.has_ticket_cost;
 }
 document.getElementById('id_ticket_cost').required=Boolean(mode?.has_ticket_cost);
 document.getElementById('single-mileage').hidden=!mode?.has_mileage_cost;
 document.getElementById('route-mileage').textContent=route?.distance_km ? new Intl.NumberFormat('el-GR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(route.distance_km)) : '—';
}
document.getElementById('id_transport').addEventListener('change',updateSingleTransport);
routeSelect.addEventListener('change',updateSingleTransport);updateSingleTransport();
