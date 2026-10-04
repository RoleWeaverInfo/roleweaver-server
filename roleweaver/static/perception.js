/* The inspector renders the same filtered snapshot used for NPC dialogue. */
(() => {
  'use strict';
  const style=document.createElement('style');
  style.textContent='#npc-perception{min-width:0;overflow-wrap:anywhere}#perception-objects{max-width:100%;overflow-x:auto}#npc-perception table{table-layout:fixed;width:100%}#npc-perception th,#npc-perception td{white-space:normal;overflow-wrap:anywhere;vertical-align:top}';
  document.head.append(style);
  window.renderPerception = snapshot => {
    const summary=document.getElementById('perception-summary');
    const objects=document.getElementById('perception-objects');
    objects.replaceChildren();
    if(!snapshot?.available){summary.textContent='No fresh observation. Connect this NPC to the game; old surroundings are not used as current knowledge.';return;}
    summary.textContent=(snapshot.area||'Current area')+' · '+(snapshot.self_condition||'condition unknown')+' · '+snapshot.self_activity+
      (snapshot.scope==='current area, line of sight'?' · Area-wide line of sight'+(snapshot.truncated?' · Crowded area: scan incomplete':''):'')+
      (snapshot.detail==='basic'?' · Basic bridge: install the perception update for detailed observations.':' · Detailed observation');
    if(!snapshot.objects.length){const p=document.createElement('p');p.textContent='Nothing reported in this partial view. This does not prove the area is empty.';objects.append(p);return;}
    const table=document.createElement('table');table.className='overview-table';
    const head=document.createElement('tr');for(const title of ['Visible object','Kind','Position','Observed state']){const th=document.createElement('th');th.textContent=title;th.scope='col';head.append(th);}
    const thead=document.createElement('thead');thead.append(head);table.append(thead);
    const body=document.createElement('tbody');
    for(const item of snapshot.objects){
      const states=[item.appearance,item.description,item.condition,item.activity,item.attitude?item.attitude+' (game relationship)':'',item.open,item.merchant?'Role Weaver merchant':''];
      if(typeof item.usable==='boolean')states.push(item.usable?'usable':'not usable');
      const row=document.createElement('tr');
      for(const value of [item.label,item.kind,item.distance+' m'+(item.bearing?' · '+item.bearing:''),states.filter(Boolean).join(' · ')||'No further visible details']){
        const td=document.createElement('td');td.textContent=value;row.append(td);
      }
      body.append(row);
    }
    table.append(body);objects.append(table);
  };
})();
