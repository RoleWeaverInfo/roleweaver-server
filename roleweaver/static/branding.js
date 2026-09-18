// Display the supplied artwork once per browser tab; the header can reopen it.
(() => {
  const splash = document.getElementById('brand-splash');
  const enter = document.getElementById('splash-enter');
  const show = document.getElementById('show-splash');
  let timer;
  const dismiss = () => { if (splash.open) splash.close(); };
  splash.addEventListener('close', () => {
    clearTimeout(timer);
    try { sessionStorage.setItem('roleweaver-splash-seen', '1'); } catch (_) {}
  });
  enter.addEventListener('click', dismiss);
  show.addEventListener('click', () => { clearTimeout(timer); splash.showModal(); });
  let seen = false;
  try { seen = sessionStorage.getItem('roleweaver-splash-seen') === '1'; } catch (_) {}
  if (!seen && typeof splash.showModal === 'function') {
    splash.showModal();
    timer = setTimeout(dismiss, 5000);
  }
})();
