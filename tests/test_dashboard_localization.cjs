/* Run with node --test tests/test_dashboard_localization.cjs.
 * Boundary tests use an isolated DOM stub, never a backend or a Gemini request.
 */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const directory = path.join(__dirname,'../backend/app/static');
const source = fs.readFileSync(path.join(directory,'dashboard-messages.js'),'utf8');
const turkish = fs.readFileSync(path.join(directory,'dashboard-tr.js'),'utf8');
class Element {
  constructor(tag='span') { this.tagName=tag;this.dataset={};this.attrs={};this._text='';this.children=[];this.value='';this.open=false; }
  get textContent() {return this._text;}
  set textContent(value) {this._text=String(value);}
  setAttribute(key,value) {this.attrs[key]=String(value);if(key.startsWith('data-'))this.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(value);}
  removeAttribute(key) {delete this.attrs[key];if(key.startsWith('data-'))delete this.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())];}
  addEventListener() {}
  matches() {return Object.keys(this.dataset).some(key=>key.startsWith('i18n')||key==='numberValue');}
  querySelectorAll() {return this.children.filter(node=>node.matches());}
}
function fixture({saved=null,blocked=false}={}) {
  const nodes=[],listeners={};const selectors=[new Element('select'),new Element('select')];
  const announce=new Element();let stored=saved,calls=0;
  const document={documentElement:{lang:'en'},body:new Element('body'),
    querySelectorAll: selector=>selector==='[data-locale-select]'?selectors:nodes.filter(node=>node.matches()),
    getElementById: id=>id==='locale-announcement'?announce:null,
    addEventListener:(key,fn)=>{(listeners[key]??=[]).push(fn);},dispatchEvent:event=>{for(const fn of listeners[event.type]??[])fn(event);}};
  const context={window:{},document,Event,Intl,localStorage:{getItem(){if(blocked)throw Error('blocked');return stored;},setItem(key,value){if(blocked)throw Error('blocked');stored=value;}},MutationObserver:class{observe(){}},fetch(){calls++;throw Error('localization must not send requests');}};
  vm.createContext(context);vm.runInContext(source,context);context.REUI=context.window.REUI;
  vm.runInContext(turkish,context);
  return {ui:context.REUI,nodes,selectors,document,announce,initialize(){for(const fn of listeners.DOMContentLoaded??[])fn();},stored:()=>stored,calls:()=>calls};
}
// Catalog inspection is confined to this test VM; the public UI exposes no catalog mutation UI.
function catalogs() {
  const context={window:{},document:{addEventListener(){}},Event,Intl};vm.createContext(context);
  vm.runInContext(source.replace('    t,apply,set,raw,write,ref,number,attribute,','    catalogs,t,apply,set,raw,write,ref,number,attribute,'),context);
  context.REUI=context.window.REUI;vm.runInContext(turkish,context);return context.REUI.catalogs;
}
test('English and Turkish cover every key and preserve named placeholders',()=>{
  const {en,tr}=catalogs();assert.deepEqual(Object.keys(en).sort(),Object.keys(tr).sort());
  for(const key of Object.keys(en))assert.deepEqual([...en[key].matchAll(/\{(\w+)\}/g)].map(m=>m[1]).sort(),[...tr[key].matchAll(/\{(\w+)\}/g)].map(m=>m[1]).sort(),key);
});
test('English is the default; unsupported saved preferences fall back safely',()=>{
  for(const saved of [null,'xx']) {const f=fixture({saved});f.initialize();assert.equal(f.ui.getLocale(),'en');assert.equal(f.document.documentElement.lang,'en');}
});
test('saved Turkish initializes document language and both header selectors',()=>{
  const f=fixture({saved:'tr'});f.initialize();assert.equal(f.ui.getLocale(),'tr');assert.ok(f.selectors.every(node=>node.value==='tr'));assert.match(f.announce.textContent,/Türkçe/);
});
test('switching persists and announces both language choices',()=>{
  const f=fixture();f.initialize();for(const code of ['tr','en','tr']){assert.equal(f.ui.setLocale(code),true);assert.equal(f.stored(),code);assert.equal(f.document.documentElement.lang,code);}
});
test('blocked localStorage does not disable switching or throw',()=>{
  const f=fixture({blocked:true});assert.doesNotThrow(()=>f.initialize());assert.equal(f.ui.setLocale('tr'),true);assert.equal(f.ui.getLocale(),'tr');
});
test('bound dynamic status interpolates IDs verbatim across language switches',()=>{
  const f=fixture();const node=new Element();f.nodes.push(node);f.ui.set(node,'demo.completed',{scenario:'B',verdict:'CLAIM FLAGGED'});f.ui.setLocale('tr');assert.match(node.textContent,/Senaryo B tamamlandı/);assert.match(node.textContent,/CLAIM FLAGGED/);
});
test('locale switches never translate user values, enum values, hashes or raw API prose',()=>{
  const f=fixture();const input=new Element('input');input.value='Ölçüm İSTANBUL & <test>';
  const raw=new Element();const payload={state:'RECYCLING_PENDING',hash:'0xA09F',reason:'Unavailable'};f.ui.raw(raw,JSON.stringify(payload));f.nodes.push(input,raw);
  f.ui.setLocale('tr');assert.equal(input.value,'Ölçüm İSTANBUL & <test>');assert.equal(raw.textContent,JSON.stringify(payload));assert.equal(f.calls(),0);f.ui.raw(raw,60.3);assert.equal(raw.textContent,'60.3');
});
test('raw API results replace old UI bindings without later relabeling',()=>{
  const f=fixture();const node=new Element();f.nodes.push(node);f.ui.set(node,'demo.processing');f.ui.raw(node,'VERIFIED');f.ui.setLocale('tr');assert.equal(node.textContent,'VERIFIED');
});
test('legacy raw replacements invalidate stale status bindings',()=>{
  const f=fixture();const node=new Element();f.nodes.push(node);f.ui.set(node,'audit.loading');node.textContent='API_VALUE';f.ui.setLocale('tr');assert.equal(node.textContent,'API_VALUE');assert.equal(node.dataset.i18n,undefined);
});
test('nested accessible copy labels update without collapsing technical details',()=>{
  const f=fixture();const details=new Element('details');details.open=true;const copy=new Element('button');f.nodes.push(details,copy);
  f.ui.attribute(copy,'aria-label','audit.copyFor',{label:f.ui.ref('audit.fileHash')});f.ui.setLocale('tr');assert.match(copy.attrs['aria-label'],/Tam değeri kopyala/);assert.match(copy.attrs['aria-label'],/Dosya SHA-256/);assert.equal(details.open,true);
});
test('localized numeric output keeps canonical numeric inputs untouched',()=>{
  const f=fixture();const input=new Element('input');input.value='60.3';f.ui.setLocale('tr');assert.equal(f.ui.number(60.3),'60,3');assert.equal(f.ui.number(1000),'1.000');assert.equal(input.value,'60.3');assert.equal(f.ui.number(0.045),'0,045');f.ui.setLocale('en');assert.equal(f.ui.number(60.3),'60.3');
});
test('escaping user/API content cannot create translated markup or execute HTML',()=>{
  const f=fixture();assert.equal(f.ui.escape('<span data-i18n="demo.title">Ölçüm & test</span>'),'&lt;span data-i18n=&quot;demo.title&quot;&gt;Ölçüm &amp; test&lt;/span&gt;');
});
test('navigation respects reduced motion and focuses content without forced scrolling',()=>{
  const html=fs.readFileSync(path.join(directory,'index.html'),'utf8');
  const start=html.indexOf('    function navigateTo('),end=html.indexOf('    function toggleMobileDrawer(',start);
  const navigation=html.slice(start,end);
  for(const reduced of [true,false]) {
    let scroll,focused=false;
    const main={focus(options){focused=options.preventScroll===true;}};
    const context={_activeView:'demo',auditViewEntered(){},history:{pushState(){}},
      document:{querySelectorAll:()=>[],getElementById:id=>id==='mobile-drawer'?{classList:{contains:()=>true}}:id==='main-content'?main:null},
      window:{location:{hash:'#overview'},matchMedia:()=>({matches:reduced}),scrollTo:options=>{scroll=options;}}};
    vm.createContext(context);vm.runInContext(navigation+'\nnavigateTo("overview");',context);
    assert.equal(scroll.behavior,reduced?'instant':'smooth');assert.equal(focused,true);
  }
});
