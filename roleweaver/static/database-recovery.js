(() => {
 'use strict';
 const host=document.getElementById('recovery-root')||document.getElementById('page-backups');
 if(!host)return;
 const panel=document.createElement('section');
 panel.innerHTML=`<style>.database-health{width:100%;border-collapse:collapse}.database-health th,.database-health td{text-align:left;padding:8px;border-bottom:1px solid #3a475c}</style><h2>Database recovery</h2>
 <p>Verified snapshots protect world data, NPC memories and placements, translations and language preferences, and usage history. API keys and NWN game files are excluded. Keep downloaded copies on another disk or machine.</p>
 <p id="db-status" role="status">Checking databases…</p><p id="db-job" role="status" aria-live="polite"></p>
 <div style="overflow-x:auto"><table class="database-health"><thead><tr><th>Database</th><th>Health</th><th>Size (including WAL)</th></tr></thead><tbody id="db-health"></tbody></table></div>
 <p><button id="db-check">Check integrity</button> <button id="db-create">Back up now</button> <button id="db-retry" hidden>Retry companion startup</button> <a href="/recovery">Open recovery page</a></p>
 <details><summary>Automatic backup settings</summary><form id="db-settings">
 <label><input type="checkbox" id="db-enabled"> Enable periodic snapshots</label>
 <label>Interval (minutes) <input id="db-interval_minutes" type="number" min="5" max="1440" required></label>
 <label>Keep recent snapshots <input id="db-keep_recent" type="number" min="2" max="168" required></label>
 <label>Keep daily snapshots <input id="db-keep_daily" type="number" min="1" max="90" required></label>
 <label>Keep weekly snapshots <input id="db-keep_weekly" type="number" min="1" max="52" required></label>
 <label>Backup storage limit (MB) <input id="db-max_storage_mb" type="number" min="32" max="102400" required></label>
 <label>Free disk reserve (MB) <input id="db-min_free_mb" type="number" min="16" max="102400" required></label>
 <p>Retention categories share snapshots. Manual, imported and pre-restore snapshots start protected. If the budget cannot hold the selected retention, new backups stop with an error; protected copies are kept.</p><button>Save settings</button></form></details>
 <h3>Saved recovery points</h3><p id="db-storage"></p>
 <label>Recovery point <select id="db-file" style="max-width:100%"></select></label><p id="db-file-info"></p>
 <p><button id="db-download">Download ZIP</button> <button id="db-verify">Verify selected</button> <button id="db-protect">Protect / unprotect</button> <button id="db-delete" class="stop">Delete selected</button></p>
 <label>Import a recovery ZIP (up to 512 MB) <input id="db-import" type="file" accept=".zip,application/zip"></label>
 <h3>Restore a recovery point</h3><p>First stop your NWN server using its normal launcher or service. Leave this dashboard running. Restore replaces saved data, losing changes made after the selected snapshot. It does not roll back NWN characters, inventories, gold or campaign databases.</p>
 <label>Restore scope <select id="db-scope"><option value="all">All databases in this recovery point</option><option value="translations">Translation cache and language preferences only</option></select></label>
 <button id="db-preview">Preview restore</button><pre id="db-preview-info"></pre>
 <label><input type="checkbox" id="db-game-stopped"> I have stopped NWN and accept replacing the data shown in this preview.</label>
 <button id="db-restore" class="stop" disabled>Restore previewed recovery point</button>
 <p class="muted">Restore checks the archive again, drains active requests, saves an undo snapshot when possible, and preserves replaced database files in database-quarantine. Corrupt files are never silently replaced with an empty world. Quarantine files need manual cleanup after recovery is confirmed.</p>`;
 host.insertBefore(panel,host.querySelector('section'));
 const $=name=>document.getElementById('db-'+name);
 let state, initialized=false, preview=null, seenResult=null, sending=false, clientError='';
 const size=n=>n>=1073741824?(n/1073741824).toFixed(2)+' GB':n>=1048576?(n/1048576).toFixed(2)+' MB':((n||0)/1024).toFixed(1)+' KB';
 const date=n=>new Date(n*1000).toLocaleString();
 const selected=()=>state?.files.find(f=>f.name===$('file').value);
 const busy=()=>sending||state?.job.running;
 function controls(){
  panel.querySelectorAll('button').forEach(b=>b.disabled=!!busy());
  for(const id of ['download','verify','protect','delete','preview'])$(id).disabled=!!busy()||!selected();
  $('create').disabled=!!busy()||!state?.available;
  $('restore').disabled=!!busy()||!preview||!$('game-stopped').checked;
  $('import').disabled=!!busy();
 }
 function clearPreview(){preview=null;$('game-stopped').checked=false;$('preview-info').textContent='';controls();}
 function fileInfo(){const f=selected();$('file-info').textContent=f?`${size(f.bytes)} · ${f.verified?'Verified':'Verification needed'} · ${f.protected?'Protected':'Eligible for rotation/deletion'}${f.error?' · '+f.error:''}`:'No recovery points yet.';controls();}
 async function api(action,body){const r=await fetch('/api/databases'+(action?'/'+action:''),body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'Recovery request failed');return d;}
 async function run(action,body={}){try{clientError='';sending=true;controls();await api(action,body);await load();}catch(e){clientError=e.message;$('job').textContent=e.message;}finally{sending=false;controls();}}
 async function load(){
  try{
   state=await api('');
   $('status').textContent=state.error||state.warning||(state.maintenance?'Maintenance in progress.':'Companion running. Changes are committed to SQLite as they are saved.');
   const job=state.job;
   $('job').textContent=clientError||(job.running?job.label+'… This page remains available while requests finish.':job.error?job.label+': '+job.error:job.label?job.label+' complete. '+(job.result?.message||''):'');
   $('health').replaceChildren();
   for(const [kind,h] of Object.entries(state.health)){const tr=document.createElement('tr');for(const value of [kind,h.ok?(h.missing?'Not created yet':'OK'):h.error,size(h.bytes+(h.wal_bytes||0))]){const td=document.createElement('td');td.textContent=value;tr.append(td);}$('health').append(tr);}
   $('retry').hidden=state.available;
   $('storage').textContent=size(state.backup_bytes)+' of '+state.settings.max_storage_mb+' MB used; '+size(state.free_bytes)+' disk free. '+(state.settings.enabled?'Automatic snapshots every '+state.settings.interval_minutes+' minutes.':'Automatic snapshots disabled.');
   if(!initialized){$('enabled').checked=state.settings.enabled;for(const key of Object.keys(state.settings))if(key!=='enabled')$(key).value=state.settings[key];initialized=true;}
   const prior=$('file').value;$('file').replaceChildren();for(const f of state.files){const option=document.createElement('option');option.value=f.name;option.textContent=date(f.created)+' · '+(f.reason||'unknown')+' · '+size(f.bytes);$('file').append(option);}if(state.files.some(f=>f.name===prior))$('file').value=prior;
   if(!job.running&&job.result?.token&&job.result.token!==seenResult){preview=job.result;seenResult=preview.token;$('game-stopped').checked=false;$('preview-info').textContent='Snapshot: '+date(preview.created)+'\nScope: '+preview.scope+'\n'+Object.entries(preview.databases).map(([k,v])=>k+': '+Object.entries(v.records).map(([t,n])=>n+' '+t).join(', ')).join('\n')+'\n\n'+preview.warning;}
   if(job.result?.restored){clearPreview();$('preview-info').textContent=job.result.message;}
   fileInfo();
  }catch(e){$('status').textContent=e.message;}
 }
 $('check').onclick=()=>run('check');$('create').onclick=()=>run('create');$('retry').onclick=()=>run('retry');
 $('file').onchange=()=>{clearPreview();fileInfo();};$('scope').onchange=clearPreview;$('game-stopped').onchange=controls;
 $('download').onclick=()=>{location.href='/api/databases/download?name='+encodeURIComponent($('file').value);};
 $('verify').onclick=()=>run('verify',{name:$('file').value});
 $('protect').onclick=()=>run('protect',{name:$('file').value,protected:!selected().protected});
 $('delete').onclick=()=>{if(confirm('Delete this recovery point permanently? Download a copy first if needed.')){clearPreview();run('delete',{name:$('file').value});}};
 $('preview').onclick=()=>{clearPreview();run('preview',{name:$('file').value,scope:$('scope').value});};
 $('restore').onclick=()=>{if(preview&&confirm('Replace the previewed database data? NWN must be stopped.')){const token=preview.token;clearPreview();run('restore',{token,game_stopped:true});}};
 $('settings').onsubmit=e=>{e.preventDefault();const body={enabled:$('enabled').checked};for(const key of Object.keys(state.settings))if(key!=='enabled')body[key]=Number($(key).value);run('settings',body);};
 $('import').onchange=async()=>{const file=$('import').files[0];if(!file)return;try{if(file.size>512*1048576)throw Error('Archive exceeds 512 MB.');sending=true;controls();const r=await fetch('/api/databases/import',{method:'POST',headers:{'Content-Type':'application/zip'},body:file});const data=await r.json();if(!r.ok)throw Error(data.error);await load();}catch(e){$('job').textContent=e.message;}finally{sending=false;$('import').value='';controls();}};
 load();setInterval(()=>{if(!document.hidden&&(host.id==='recovery-root'||location.hash==='#backups'||state?.job.running))load();},2000);
})();
