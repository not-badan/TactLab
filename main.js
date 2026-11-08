import {Viewer} from './viewer.js';
const $=id=>document.getElementById(id),form=$('form'),viewer=new Viewer($('canvas'));
const defaults={mode:'panel',component:'B3F-1000',hole:22,panel:2,key:14,proud:1.4,gap:.30,convention:'side',material:'fdm',moving:'fdm',light:'none',arm:24,pitch:22,slot:6,extra:1,trim:0,hand:'right',color:'#ea713c'};
const dimensions={hole:['Отверстие',20,34,.1],panel:['Толщина панели',1,5,.1],key:['Диаметр клавиши',12,24,.1],proud:['Выступ клавиши',.6,3,.1],arm:['Длина до носика',20,40,.5],pitch:['Межосевое пазов',19,34,.5],slot:['Регулировка в пазу',4,12,.5],extra:['Ход после щелчка¹',.5,1.5,.1]};
const fmt=v=>Number(v).toLocaleString('ru',{maximumFractionDigits:3});
let p={...defaults}, data,view='assembled',pressed=false,revision=0,timer,ready=false,exporting=false;
try{let s=JSON.parse(localStorage.getItem('tact.settings.v1'));if(s&&typeof s==='object')for(let k in p)if(typeof s[k]===typeof p[k])p[k]=s[k];}catch{}
function buttons(attr,chosen){document.querySelectorAll('[data-'+attr+']').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset[attr]===chosen)))}
function configure(){
  const panel=p.mode==='panel';
  $('title').textContent=panel?'Панельная кнопка':'Рычажный концевик';
  $('subtitle').textContent=panel?'Врезной корпус с защёлками и сменной клавишей':'Регулируемое основание и рычаг на металлической оси';
  $('geoTitle').textContent=panel?'Посадка в панель':'Геометрия концевика';
  $('movingName').textContent=panel?'Клавиша':'Рычаг';$('colorName').textContent=panel?'Цвет клавиши':'Цвет рычага';
  $('lightField').hidden=!panel;$('handField').hidden=panel;
  $('dims').innerHTML=(panel?['hole','panel','key','proud']:['arm','pitch','slot','extra']).map(key=>{
    const [label,min,max,step]=dimensions[key];
    return '<label>'+label+'<div class="unit"><input name="'+key+'" type="number" min="'+min+'" max="'+max+'" step="'+step+'"><span>мм</span></div></label>';
  }).join('');
  for(const input of form.elements)if(input.name in p)input.value=p[input.name];
  buttons('mode',p.mode);buttons('view',view);
}
function status(message='',bad=false){$('status').textContent=message;$('status').classList.toggle('error',bad);}
function updateActions(){$('export').disabled=!ready||exporting;$('export').firstChild.textContent=exporting?'Готовим файлы… ':'Скачать комплект ';}
function schedule(){
  const id=++revision;clearTimeout(timer);ready=false;updateActions();$('stage').classList.add('busy');
  if(!form.checkValidity()){status('Проверь диапазон и шаг у выделенного размера.',true);form.reportValidity();return;}
  status('Построение модели…');
  timer=setTimeout(async()=>{
    try{
      const response=await fetch('/api/model',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
      const result=await response.json();if(id!==revision)return;
      if(!response.ok)throw Error(result.error);
      const reset=!data||data.settings.mode!==p.mode||data.settings.hand!==p.hand;
      data=result;viewer.set(data,view,pressed,reset);describe();ready=true;
      try{localStorage.setItem('tact.settings.v1',JSON.stringify(p))}catch{}
      status();
    }catch(e){if(id===revision)status((e.message||'Ошибка построения')+(data?' Показана предыдущая модель.':''),true);}
    finally{if(id===revision){$('stage').classList.remove('busy');updateActions()}}
  },180);
}
function describe(){
  if(!data)return;
  press.textContent=pressed?'Отпустить':'Нажать';
  const s=data.settings,panel=s.mode==='panel',g=s.gap/(s.convention==='side'?1:2);
  const first=(.43-s.trim)*s.arm/7.5;
  const values=panel?[[fmt(s.hole)+' мм','Отверстие панели'],[fmt(g)+' мм','Зазор на сторону'],[fmt(.95)+' мм','Ход до упора']]:
    [[fmt(s.arm)+' мм','Плечо рычага'],[fmt(first)+' мм','До щелчка¹'],[fmt(first+s.extra)+' мм','До упора¹']];
  $('readout').innerHTML=values.map(([v,t])=>'<div><b>'+v+'</b><span>'+t+'</span></div>').join('');
  const fit=panel?'Клавиша Ø'+fmt(s.key)+' мм · отверстие направляющей Ø'+fmt(s.key+2*g)+' мм.':'Ось Ø3 мм · отверстие рычага Ø'+fmt(3+2*g)+' мм.';
  $('viewNote').textContent=(view==='section'?fit+' ':'')+(pressed?'Положение номинального замыкания. ':'')+(panel?'':'¹ Расчёт без деформации накладки. ')+(view==='assembled'?'Вращение — перетаскиванием. Масштаб — колесом или двумя пальцами.':view==='exploded'?'Детали разнесены по высоте для осмотра.':'Половина модели снята по оси штока.');
  $('partsList').replaceChildren(...data.parts.filter(x=>['body','moving','insert','component','rubber'].includes(x.role)||x.id==='pin'||x.id==='led').map(row=>{const d=document.createElement('div');d.className='partsLine';const sw=document.createElement('i');sw.style.background=row.color;d.append(sw,document.createTextNode(row.name));return d;}));
  $('assemblyText').innerHTML=panel?'<p>Совмести грани на буртике клавиши с винтовыми стойками и вложи клавишу сзади. Подпаяй провода, заведи переключатель во вкладыш, выведи провода через окна и закрепи стяжкой. Стяни вкладыш и стакан двумя саморезами Ø2 × 6 мм. На толкатель нужна мягкая накладка Ø3,3 × 1 мм.</p><p>В комплекте три высоты вкладыша. Начни с номинального и проверь возврат при нажатии по краю. Для подсветки понадобится светодиод Ø3 мм.</p>':'<p>Заведи переключатель в седло, приклей мягкую накладку Ø3,3 × 1 мм к рычагу над штоком. Введи ось Ø3 мм, зафиксируй концы и выставь основание двумя винтами М3 в пазах. Длина оси указана в инструкции комплекта.</p>';
}
form.addEventListener('input',e=>{const el=e.target;if(!(el.name in defaults))return;p[el.name]=typeof defaults[el.name]==='number'?Number(el.value):el.value;schedule()});
form.addEventListener('submit',e=>e.preventDefault());
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{if(p.mode===b.dataset.mode)return;p.mode=b.dataset.mode;pressed=false;$('press').setAttribute('aria-pressed','false');configure();schedule()});
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;pressed=false;$('press').disabled=view==='exploded';$('press').setAttribute('aria-pressed','false');buttons('view',view);if(data){viewer.set(data,view,false,true);describe()}});
$('press').onclick=()=>{if(!data)return;pressed=!pressed;$('press').setAttribute('aria-pressed',String(pressed));viewer.set(data,view,pressed);describe()};
$('homeView').onclick=()=>viewer.home();
$('reset').onclick=()=>{p={...defaults,mode:p.mode};pressed=false;$('press').setAttribute('aria-pressed','false');configure();schedule()};
$('export').onclick=async()=>{
  if(!ready||exporting)return;
  const snapshot={...data.settings},id=revision;exporting=true;updateActions();status('Собираем STL и STEP…');
  try{
    const r=await fetch('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(snapshot)});
    if(!r.ok)throw Error((await r.json()).error);
    const url=URL.createObjectURL(await r.blob()),a=document.createElement('a');
    a.href=url;a.download='Tact-'+(snapshot.mode==='panel'?'panel-D'+snapshot.hole:'limit-L'+snapshot.arm)+'.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
    if(id===revision)status('Комплект передан в загрузки браузера.');
  }catch(e){if(id===revision)status(e.message,true)}finally{exporting=false;updateActions()}
};
configure();schedule();
