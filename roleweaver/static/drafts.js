/* Browser-only unsaved text. Server data changes only through the normal Save buttons. */
class DraftStore {
  constructor(storage, scope) { this.storage=storage; this.prefix='roleweaver-draft-v1:'+scope+':'; }
  read(key) {
    const raw=this.storage.getItem(this.prefix+key);
    if(!raw)return null;
    const d=JSON.parse(raw);
    if(d.version!==1||!d.values||typeof d.values!=='object'||Array.isArray(d.values)||!d.base||typeof d.base!=='object'||Array.isArray(d.base)||!Number.isFinite(d.saved)||!Object.values(d.values).every(v=>typeof v==='string')||!Object.values(d.base).every(v=>typeof v==='string'))throw Error('Invalid recovery draft');
    return d;
  }
  write(key,values,base) {
    if(JSON.stringify(values)===JSON.stringify(base)){this.remove(key);return;}
    this.storage.setItem(this.prefix+key,JSON.stringify({version:1,values,base,saved:Date.now()}));
  }
  remove(key){this.storage.removeItem(this.prefix+key);}
  saved(key,values){const d=this.read(key);if(d&&JSON.stringify(d.values)===JSON.stringify(values))this.remove(key);}
}
if(typeof module!=='undefined')module.exports=DraftStore;
