(() => {
    const list = document.querySelector('.employee-card-choices');
    if (!list) return;
    const boxes = [...list.querySelectorAll('input[type="checkbox"]')];
    const tools = document.querySelector('.employee-card-tools');
    tools.hidden = false;
    const count = document.getElementById('card-selected-count');
    const update = () => { count.textContent = `Επιλεγμένοι: ${boxes.filter(box => box.checked).length}`; };
    const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('el');
    document.getElementById('card-search').addEventListener('input', event => {
        const term = normalize(event.target.value.trim());
        boxes.forEach(box => { box.closest('label').parentElement.hidden = !normalize(box.closest('label').textContent).includes(term); });
    });
    document.getElementById('card-select-all').addEventListener('click', () => {
        boxes.filter(box => !box.closest('label').parentElement.hidden).forEach(box => { box.checked = true; }); update();
    });
    document.getElementById('card-clear').addEventListener('click', () => { boxes.forEach(box => { box.checked = false; }); update(); });
    boxes.forEach(box => box.addEventListener('change', update)); update();
})();
