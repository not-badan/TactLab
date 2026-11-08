import * as T from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

export class Viewer {
  constructor(canvas) {
    this.canvas=canvas;
    this.scene=new T.Scene();
    this.scene.add(new T.HemisphereLight(0xf3f8ff,0xada99c,2.6));
    const light=new T.DirectionalLight(0xfff4de,3.2);
    light.position.set(-20,-36,75);
    this.scene.add(light);
    const rim=new T.DirectionalLight(0xc9eaff,2);
    rim.position.set(30,40,25);
    this.scene.add(rim);
    this.camera=new T.OrthographicCamera(-30,30,30,-30,.1,500);
    this.camera.up.set(0,0,1);
    try {
      this.renderer=new T.WebGLRenderer({canvas,antialias:true,alpha:true});
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
      this.renderer.setClearColor(0,0);
    } catch {
      const fresh=canvas.cloneNode(false);
      canvas.replaceWith(fresh);
      this.canvas=fresh;
      this.ctx=fresh.getContext('2d');
    }
    this.group=new T.Group();
    this.scene.add(this.group);
    this.controls=new OrbitControls(this.camera,this.canvas);
    this.controls.minZoom=.4;
    this.controls.maxZoom=6;
    this.controls.addEventListener('change',()=>this.draw());
    this.observer=new ResizeObserver(()=>this.resize());
    this.observer.observe(this.canvas.parentElement);
    this.height=52;
    this.resize();
  }
  resize(){
    const {width,height}=this.canvas.parentElement.getBoundingClientRect();
    const aspect=width/height;
    const h=(this.height||52)*Math.max(1,1.05/aspect);
    Object.assign(this.camera,{left:-h*aspect/2,right:h*aspect/2,top:h/2,bottom:-h/2});
    this.camera.updateProjectionMatrix();
    if(this.renderer)this.renderer.setSize(width,height,false);
    else {this.canvas.width=Math.round(width); this.canvas.height=Math.round(height);}
    this.draw();
  }
  clear(){
    for(const obj of [...this.group.children]){
      obj.traverse(o=>{o.geometry?.dispose();o.material?.dispose()});
      this.group.remove(obj);
    }
  }
  set(data,view,pressed,reset=false){
    this.data=data;this.view=view;this.pressed=pressed;
    const p=data.settings;
    this.clear();
    for(const row of data.parts){
      const raw=view==='section'?row.cut:row.mesh;
      if(!raw.indices.length)continue;
      const geo=new T.BufferGeometry();
      geo.setAttribute('position',new T.Float32BufferAttribute(raw.vertices,3));
      geo.setIndex(raw.indices);
      geo.computeVertexNormals();
      const mesh=new T.Mesh(geo,new T.MeshStandardMaterial({color:row.color,roughness:.53,metalness:row.role==='metal'?.65:.12,side:T.DoubleSide}));
      const edges=new T.LineSegments(new T.EdgesGeometry(geo,32),new T.LineBasicMaterial({color:0x132c38,transparent:true,opacity:.38}));
      mesh.add(edges);
      if(view==='exploded'){
        if(row.id==='pin')mesh.position.y=-15;
        else mesh.position.z=row.spread;
      }
      if(pressed && view!=='exploded'){
        const stroke=.18-p.trim+.25;
        if(p.mode==='panel' && ['key','pad'].includes(row.id))mesh.position.z-=stroke;
        if(p.mode==='limit' && ['lever','pad'].includes(row.id)){
          const angle=Math.asin(stroke/7.5)*(p.hand==='right'?1:-1);
          mesh.rotation.y=angle;
          mesh.position.set(-14*Math.sin(angle),0,14*(1-Math.cos(angle)));
        }
        if(row.id==='stem'){
          const z=(p.mode==='panel'?-11.2:6.8)+p.trim+3.4;
          mesh.scale.z=1-.25/.9;
          mesh.position.z=z*(1-mesh.scale.z);
        }
      }
      this.group.add(mesh);
    }
    if(reset || !this.center)this.home(); else this.draw();
  }
  home(){
    if(!this.data)return;
    const bounds=new T.Box3().setFromObject(this.group);
    const size=bounds.getSize(new T.Vector3());
    const center=bounds.getCenter(new T.Vector3());
    this.center=center;
    this.height=Math.max(size.z*1.28,Math.hypot(size.x,size.y)*.88,28);
    const direction=this.view==='section'?new T.Vector3(.08,-1,.06):new T.Vector3(.77,-1.3,.90);
    this.camera.position.copy(center).addScaledVector(direction.normalize(),130);
    this.camera.zoom=1;this.controls.target.copy(center);this.controls.update();this.resize();
  }
  labelGap(){
    const overlay=this.canvas.parentElement.querySelector(".measure");
    const show=this.view==="section" && this.data;
    overlay.toggleAttribute("hidden",!show);
    if(!show)return;
    const p=this.data.settings,g=p.gap/(p.convention==="side"?1:2);
    const panel=p.mode==="panel";
    const pos=new T.Vector3((panel?p.key/2:1.5)+g/2,0,panel?.8:14).project(this.camera);
    const w=this.canvas.clientWidth,h=this.canvas.clientHeight;
    const x=(pos.x+1)*w/2,y=(1-pos.y)*h/2;
    const left=Math.min(w-88,Math.max(5,x+25)),top=Math.min(h-74,Math.max(51,y-44));
    const [line,dot,bg,txt]=overlay.children;
    line.setAttribute("d","M"+x+" "+y+" L"+left+" "+(top+14));
    dot.setAttribute("cx",x);dot.setAttribute("cy",y);
    bg.setAttribute("x",left);bg.setAttribute("y",top);
    txt.setAttribute("x",left+8);txt.setAttribute("y",top+16);
    txt.textContent=g.toLocaleString("ru",{maximumFractionDigits:3})+" мм";
  }
  draw(){
    if(!this.group)return;
    this.camera.updateMatrixWorld();this.labelGap();
    if(this.renderer){this.renderer.render(this.scene,this.camera);return;}
    // Painter's algorithm gives older browsers the same CAD triangles and orbit controls.
    const ctx=this.ctx, w=this.canvas.width,h=this.canvas.height;
    if(!ctx)return;
    ctx.clearRect(0,0,w,h);this.camera.updateMatrixWorld();this.group.updateMatrixWorld(true);
    const triangles=[];
    for(const mesh of this.group.children){
      const geo=mesh.geometry, points=[],world=[];
      for(let k=0;k<geo.attributes.position.count;k++){
        const v=new T.Vector3().fromBufferAttribute(geo.attributes.position,k).applyMatrix4(mesh.matrixWorld);
        world.push(v);points.push(v.clone().project(this.camera));
      }
      const idx=geo.index.array;
      for(let i=0;i<idx.length;i+=3){
        const [a,b,c]=[idx[i],idx[i+1],idx[i+2]];
        const normal=world[b].clone().sub(world[a]).cross(world[c].clone().sub(world[a])).normalize();
        const color=mesh.material.color.clone().multiplyScalar(.65+.40*Math.max(0,normal.dot(new T.Vector3(-.35,-.45,.82))));
        triangles.push({face:[points[a],points[b],points[c]],color:'#'+color.getHexString(),z:points[a].z+points[b].z+points[c].z});
      }
    }
    triangles.sort((a,b)=>b.z-a.z);
    for(const tri of triangles){
      ctx.beginPath();tri.face.forEach((v,i)=>ctx[i?'lineTo':'moveTo']((v.x+1)*w/2,(1-v.y)*h/2));
      ctx.closePath();ctx.fillStyle=ctx.strokeStyle=tri.color;ctx.fill();ctx.lineWidth=.5;ctx.stroke();
    }
  }
}