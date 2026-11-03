const routes=JSON.parse(document.getElementById('routes-data').textContent);
const routeSelect=document.getElementById('id_route');
const search=document.getElementById('route-search');
const originalOptions=Array.from(routeSelect.options).map(o=>({value:o.value,text:o.text}));
search.addEventListener('input',()=>{const selected=routeSelect.value;routeSelect.replaceChildren();for(const o of originalOptions){if(!o.value||o.value===selected||o.text.toLocaleLowerCase('el').includes(search.value.toLocaleLowerCase('el'))){routeSelect.add(new Option(o.text,o.value,false,o.value===selected));}}});
function fillStops(select){const current=select.value;select.replaceChildren(new Option('---------',''));const route=routes.find(r=>String(r.id)===routeSelect.value);for(const stop of route?.stops||[])select.add(new Option(stop.city,stop.id,false,String(stop.id)===current));}
routeSelect.addEventListener('change',()=>document.querySelectorAll('#stays-rows select[name$="-stop"]').forEach(fillStops));
function addRow(prefix){const total=document.getElementById(`id_${prefix}-TOTAL_FORMS`);const index=Number(total.value);const html=document.getElementById(`${prefix}-empty`).innerHTML.replaceAll('__prefix__',index);document.getElementById(`${prefix}-rows`).insertAdjacentHTML('beforeend',html);total.value=index+1;const row=document.getElementById(`${prefix}-rows`).lastElementChild;if(prefix==='stays')fillStops(row.querySelector('select[name$="-stop"]'));return row;}
document.querySelectorAll('[data-add]').forEach(b=>b.addEventListener('click',()=>addRow(b.dataset.add)));
document.getElementById('generate-nights').addEventListener('click',()=>{const start=document.getElementById('id_departure_at').value;const end=document.getElementById('id_return_at').value;const message=document.getElementById('night-message');if(!start||!end||end<start||!routeSelect.value){message.textContent='Συμπληρώστε διαδρομή και έγκυρες ημερομηνίες.';return;}const existing=new Set(Array.from(document.querySelectorAll('#stays-rows input[type=date]')).map(i=>i.value));let day=new Date(start+'T00:00:00Z');const finish=new Date(end+'T00:00:00Z');if((finish-day)/86400000>366){message.textContent='Για διάστημα άνω των 366 ημερών χρειάζεται έλεγχος.';return;}while(day<finish){const value=day.toISOString().slice(0,10);if(!existing.has(value)){let row=Array.from(document.querySelectorAll('#stays-rows fieldset')).find(r=>!r.querySelector('input[type=date]').value);if(!row)row=addRow('stays');fillStops(row.querySelector('select[name$="-stop"]'));row.querySelector('input[type=date]').value=value;const stops=row.querySelector('select[name$="-stop"]');if(stops.options.length>1)stops.selectedIndex=1;existing.add(value);}day.setUTCDate(day.getUTCDate()+1);}message.textContent='Συμπληρώθηκαν οι νύχτες που έλειπαν. Ελέγξτε πόλη, τύπο και κόστος.';});

const modes=JSON.parse(document.getElementById('transport-data').textContent);
function updateCosts(row, infer=false){
 const transport=row.querySelector('[name$="-transport"]');
 const kind=row.querySelector('[name$="-kind"]');
 const mode=modes.find(m=>String(m.id)===transport.value);
 if(infer && mode){if(mode.has_ticket_cost)kind.value='ticket';else if(mode.has_mileage_cost)kind.value='mileage';else kind.value='other';}
 const showTicket=kind.value==='other'||(kind.value==='ticket'&&mode?.has_ticket_cost);
 const visibility={ticket:showTicket,transfer:kind.value==='ticket'&&mode?.has_ticket_cost,mileage:kind.value==='mileage'&&mode?.has_mileage_cost};
 for(const group of row.querySelectorAll('[data-cost]')){
  const input=group.querySelector('input');
  // Retain entered values visibly rather than silently discarding them on mode change.
  group.hidden=!visibility[group.dataset.cost]&&!input.value;
 }
}
document.querySelectorAll('.expense-row').forEach(row=>updateCosts(row));
document.getElementById('expenses-rows').addEventListener('change',event=>{const row=event.target.closest('.expense-row');if(row)updateCosts(row,event.target.name.endsWith('-transport'));});
new MutationObserver(records=>{for(const record of records)for(const node of record.addedNodes)if(node.nodeType===1&&node.matches('.expense-row'))updateCosts(node);}).observe(document.getElementById('expenses-rows'),{childList:true});
