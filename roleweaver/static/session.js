/* Run before dashboard modules so expired sessions never look like game failures. */
(() => {
 'use strict';
 const originalFetch=window.fetch.bind(window);
 window.fetch=async(...args)=>{
  const response=await originalFetch(...args);
  if(response.status===401 && new URL(response.url,location.href).origin===location.origin)location.replace('/login');
  return response;
 };
 function check(){if(!document.hidden)window.fetch('/api/session').catch(()=>{});}
 window.addEventListener('pageshow',check);
 document.addEventListener('visibilitychange',check);
 setInterval(check,60000);
 document.addEventListener('DOMContentLoaded',()=>{
  const button=document.getElementById('dashboard-logout');
  if(button)button.addEventListener('click',async()=>{
   button.disabled=true;
   try{const response=await window.fetch('/api/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!response.ok)throw Error();location.replace('/login');}
   catch(e){button.disabled=false;button.textContent='Retry log out';}
  });
 });
})();
