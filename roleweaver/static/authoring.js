const buildDefaults={appearance:'6',race:'6',gender:'0',npc_class:'4',level:'1',factions:''};
let authoringCatalog=null;
function options(id,rows,value){const select=$(id);select.replaceChildren();for(const row of rows){const o=document.createElement('option');o.value=String(row.id);o.textContent=row.name;select.append(o)}select.value=String(value);}
function resetAppearanceOptions(value){if(!authoringCatalog)return;options('appearance',authoringCatalog.appearances,value);$('appearance-filter').value='';}
async function initAuthoring(){
 authoringCatalog=await api('catalog');resetAppearanceOptions('6');options('race',authoringCatalog.races,'6');options('npc_class',authoringCatalog.classes,'4');options('npc-template',authoringCatalog.templates,'guard');
 $('appearance-filter').oninput=()=>{const value=$('appearance').value,q=$('appearance-filter').value.toLowerCase();options('appearance',authoringCatalog.appearances.filter(a=>String(a.id)===value||a.name.toLowerCase().includes(q)),value)};
 $('appearance').addEventListener('change',()=>{const a=authoringCatalog.appearances.find(a=>String(a.id)===$('appearance').value);if(a&&a.id<=6){$('race').value=String(a.id)}stashDraft('profile')});
 $('use-template').onclick=()=>{const t=authoringCatalog.templates.find(t=>t.id===$('npc-template').value);$('new').click();if(draftSlots.profile?.pending){notice('Restore or discard the previous new-NPC draft before applying a template.');return;}for(const k of fields)if(k!=='id')$(k).value=t[k]??buildDefaults[k]??'';stashDraft('profile');notice('Template loaded. Choose a unique NPC ID and name, customize, then save.');};
}
const accessFields=['access-id','access-title','access-text','access-audience','access-target','access-disclosure'];
function editAccess(entry){for(const id of accessFields)$(id).value=entry[id.slice(7)]??(id==='access-audience'?'public':'');$('access-id').readOnly=!!entry.id;mountDraft('access','access:'+(entry.id||'new'),accessFields,'access-form');}
async function listAccess(){const rows=await api('access-lore');$('access-list').replaceChildren();for(const row of rows){const div=document.createElement('div');div.className='entry';const title=document.createElement('span');title.textContent=row.title+' — '+row.audience+(row.target?' / '+row.target:'')+' ';const edit=document.createElement('button');edit.type='button';edit.textContent='Edit';edit.onclick=()=>editAccess(row);const remove=document.createElement('button');remove.type='button';remove.textContent='Delete';remove.onclick=async()=>{if(!confirm('Delete lore entry '+row.title+'?'))return;try{await api('access-lore-delete',{id:row.id});if($('access-id').value===row.id)editAccess({});await listAccess();}catch(e){$('access-notice').textContent=e.message}};const active=document.createElement('input');active.type='checkbox';active.style.width='auto';active.checked=row.active!==false;active.setAttribute('aria-label','Active: '+row.title);const label=document.createElement('label');label.append(active,document.createTextNode(' Active'));active.onchange=async()=>{active.disabled=true;try{await api('access-lore-toggle',{id:row.id,active:active.checked});$('access-notice').textContent='Active status saved. Applies to new replies.';}catch(e){active.checked=!active.checked;$('access-notice').textContent=e.message}finally{active.disabled=false}};div.append(title,label,edit,remove);$('access-list').append(div);}}
function initLoreAccess(){
 accessFields.forEach(id=>$(id).addEventListener('input',()=>stashDraft('access')));
 $('access-new').onclick=()=>editAccess({});editAccess({});listAccess().catch(e=>$('access-notice').textContent=e.message);
 $('access-form').onsubmit=async e=>{e.preventDefault();const slot=draftSlots.access;if(slot.pending)return;const key=slot.key,values=draftValues(accessFields);const body=Object.fromEntries(Object.entries(values).map(([k,v])=>[k.slice(7),v]));try{await api('access-lore',body);draftSaved('access',key,values);if(draftSlots.access.key===key&&JSON.stringify(draftValues(accessFields))===JSON.stringify(values))editAccess(body);await listAccess();$('access-notice').textContent='Lore saved. Applies to the next reply.';}catch(e){$('access-notice').textContent=e.message}};
}

const worldFields=['world-title','world-lore'];
let worldDocumentId='',worldSaving=false;
function worldKey(id){return id==='world_lore'?'world':'world:'+(id||'new');}
function editWorldDocument(doc){
 worldDocumentId=doc.id||'';$('world-title').value=doc.title||'';$('world-lore').value=doc.text||'';
 mountDraft('world',worldKey(worldDocumentId),worldFields,'world-lore-form');
 $('lore-notice').textContent=doc.id?'Editing '+doc.title+'. Active status is controlled by the checkbox above.':'New documents start inactive.';
}
async function listWorldDocuments(){
 const data=await api('world-documents');$('world-documents').replaceChildren();
 $('world-budget').textContent=data.documents.filter(d=>d.active).length+' active of '+data.documents.length+' documents · '+data.active_characters.toLocaleString()+' / '+data.limit.toLocaleString()+' active characters';
 for(const doc of data.documents){
  const row=document.createElement('div');row.className='entry';
  const title=document.createElement('strong');title.textContent=doc.title+' ';
  const active=document.createElement('input');active.type='checkbox';active.checked=doc.active;active.style.width='auto';active.setAttribute('aria-label','Active: '+doc.title);
  const label=document.createElement('label');label.append(active,document.createTextNode(' Active'));
  active.onchange=async()=>{active.disabled=true;try{await api('world-document-toggle',{id:doc.id,active:active.checked});await listWorldDocuments();$('lore-notice').textContent='Active status saved. Applies to new replies.';}catch(e){active.checked=!active.checked;$('lore-notice').textContent=e.message}finally{active.disabled=false}};
  const edit=document.createElement('button');edit.type='button';edit.textContent='Edit';edit.onclick=()=>editWorldDocument(doc);
  const remove=document.createElement('button');remove.type='button';remove.textContent='Delete';
  remove.onclick=async()=>{if(!confirm('Delete document '+doc.title+'? Inactivate it instead to keep it for later.'))return;try{await api('world-document-delete',{id:doc.id});if(worldDocumentId===doc.id)editWorldDocument({});await listWorldDocuments();}catch(e){$('lore-notice').textContent=e.message}};
  row.append(title,label,edit,remove);$('world-documents').append(row);
 }
 if(!data.documents.length)$('world-documents').textContent='No documents yet. Add or import one below.';
 return data.documents;
}
function newWorldID(){return 'doc_'+crypto.randomUUID().replaceAll('-','').slice(0,28);}
async function initWorldDocuments(){
 const rows=await listWorldDocuments();editWorldDocument(rows.find(d=>d.id==='world_lore')||rows[0]||{});
 $('world-new').disabled=false;$('world-import').disabled=false;
 $('world-new').onclick=()=>editWorldDocument({});
 $('world-title').addEventListener('input',()=>stashDraft('world'));
 $('world-lore-form').onsubmit=async e=>{
  e.preventDefault();const slot=draftSlots.world;if(slot?.pending||worldSaving)return;worldSaving=true;
  const key=slot.key,values=draftValues(worldFields),id=worldDocumentId;
  const body={id:id||newWorldID(),title:values['world-title'],text:values['world-lore']};if(!id)body.active=false;
  try{const saved=await api('world-document',body);draftSaved('world',key,values);if(draftSlots.world.key===key&&JSON.stringify(draftValues(worldFields))===JSON.stringify(values))editWorldDocument(saved);await listWorldDocuments();$('lore-notice').textContent='Document saved.'+(saved.active?' Applies to new replies.':' Check Active to use it.');}
  catch(e){$('lore-notice').textContent=e.message}finally{worldSaving=false}
 };
 $('world-import').onchange=async()=>{
  const files=[...$('world-import').files];$('world-import').disabled=true;let count=0;
  try{for(const file of files){
   if(!/\.(txt|md)$/i.test(file.name)||file.size>80000)throw Error('Use .txt or .md files of at most 20,000 characters each.');
   const text=await file.text();if(text.length>20000||text.includes('\u0000'))throw Error('Document must be plain text, at most 20,000 characters: '+file.name);
   await api('world-document',{id:newWorldID(),title:file.name.slice(0,100),text,active:false});count++;
  }$('world-import-notice').textContent='Imported '+count+' document(s), inactive. Check Active when ready.';}
  catch(e){$('world-import-notice').textContent='Imported '+count+' document(s). '+e.message;}
  finally{$('world-import').value='';$('world-import').disabled=false;await listWorldDocuments();}
 };
}
