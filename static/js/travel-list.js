document.querySelectorAll('[data-trip-url]').forEach(row=>row.addEventListener('dblclick',event=>{if(!event.target.closest('a,button,input,select'))window.location.assign(row.dataset.tripUrl);}));
