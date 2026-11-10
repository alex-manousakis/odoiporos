const unitFilter=document.getElementById('statement-unit-filter');
if(unitFilter){
 unitFilter.addEventListener('submit',()=>{
  for(const field of ['period','signatory','print_date']){
   const source=document.getElementById('id_'+field);
   let hidden=unitFilter.querySelector('input[name="'+field+'"]');
   if(!hidden){hidden=document.createElement('input');hidden.type='hidden';hidden.name=field;unitFilter.appendChild(hidden);}
   hidden.value=source.value;
  }
 });
 document.getElementById('id_department').addEventListener('change',()=>unitFilter.requestSubmit());
}
