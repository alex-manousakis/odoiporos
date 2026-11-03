const abroad=document.getElementById('id_is_abroad');
function updateRoute(){for(const row of document.querySelectorAll('.route-stops fieldset')){const stopAbroad=row.querySelector('[name$="-is_abroad"]');const band=row.querySelector('.abroad-option');band.hidden=!abroad.checked; if(!abroad.checked&&!stopAbroad.disabled){stopAbroad.checked=false;row.querySelector('[name$="-compensation_band"]').value='1';}}}
abroad.addEventListener('change',updateRoute);updateRoute();
