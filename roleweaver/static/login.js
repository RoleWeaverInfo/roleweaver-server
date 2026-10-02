(() => {
 'use strict';
 const form=document.getElementById('login-form'), field=document.getElementById('password'), button=document.getElementById('login-submit'), error=document.getElementById('login-error');
 form.addEventListener('submit',async event=>{
  event.preventDefault();button.disabled=true;error.textContent='';
  try{
   const response=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:field.value})});
   field.value='';const data=await response.json();
   if(!response.ok)throw Error(data.error||'Unable to sign in');
   location.replace('/');
  }catch(e){error.textContent=e.message||'Cannot reach the dashboard';field.focus();}
  finally{field.value='';button.disabled=false;}
 });
})();
