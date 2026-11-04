// Native calendar selection with a separate, consistently formatted text field.
(() => {
  function isoDate(value) {
    const match=/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value.trim());
    if(!match)return '';
    const year=Number(match[3]),month=Number(match[2]),day=Number(match[1]);
    const date=new Date(0);date.setUTCFullYear(year,month-1,day);
    if(date.getUTCFullYear()!==year||date.getUTCMonth()!==month-1||date.getUTCDate()!==day)return '';
    return `${match[3]}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
  }
  function enhance() {
    document.querySelectorAll('input[data-greek-date]:not([data-calendar-ready])').forEach(input => {
      input.dataset.calendarReady='true';
      if(input.matches(':disabled')||input.readOnly)return;
      const wrapper=document.createElement('span');wrapper.className='date-with-calendar';
      input.parentNode.insertBefore(wrapper,input);wrapper.append(input);
      const button=document.createElement('button');button.type='button';button.className='calendar-button';
      button.title='Επιλογή ημερομηνίας';button.setAttribute('aria-label','Επιλογή ημερομηνίας');
      button.innerHTML='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v5M17 3v5M3 11h18M7 15h3M14 15h3"/></svg>';
      const picker=document.createElement('input');picker.type='date';picker.className='native-date-picker';
      picker.tabIndex=-1;picker.setAttribute('aria-label','Επιλογή ημερομηνίας');
      // No name: the Greek text field remains the only submitted value.
      wrapper.append(button,picker);
      button.addEventListener('click',()=>{
        if(input.matches(':disabled')||input.readOnly)return;
        picker.value=isoDate(input.value);
        try {
          if(typeof picker.showPicker!=='function')throw new Error('Native popup unavailable');
          picker.showPicker();
        } catch {
          picker.classList.add('native-date-fallback');picker.tabIndex=0;picker.focus();picker.click();
        }
      });
      picker.addEventListener('change',()=>{
        if(input.matches(':disabled')||input.readOnly)return;
        if(picker.value){const [year,month,day]=picker.value.split('-');input.value=`${day}/${month}/${year}`;}else input.value='';
        picker.classList.remove('native-date-fallback');picker.tabIndex=-1;
        input.dispatchEvent(new Event('input',{bubbles:true}));
        input.dispatchEvent(new Event('change',{bubbles:true}));
        input.focus();
      });
    });
  }
  enhance();
  new MutationObserver(enhance).observe(document.body,{childList:true,subtree:true});
})();
