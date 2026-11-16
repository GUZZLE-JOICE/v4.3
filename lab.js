(function(){
  'use strict';

  var api={};
  var canvas=null,ctx=null,triangles=[],fileName='',modelCenter={x:0,y:0,z:0};
  var orbitYaw=-.55,orbitPitch=.38,orbitZoom=1,dragging=false,lastX=0,lastY=0;
  var audioCtx=null,lastMetrics=null,rafStarted=false,showGrid=true,wireframe=false,designBusy=false;
  var history=[],future=[],MAX_HISTORY=12,lastScalePercent=100;
  var SAFE_GENERATED_MM=120,SAFE_GENERATED_CM3=180,PANEL_MIN=330,PANEL_MAX=720;
  var MATERIALS={
    pla:{label:'PLA',density:1.24,price:19.99,priceLabel:'$19.99 / kg'},
    petg:{label:'PETG',density:1.27,price:19.99,priceLabel:'$19.99 / kg'},
    abs:{label:'ABS',density:1.04,price:19.99,priceLabel:'$19.99 / kg'},
    asa:{label:'ASA',density:1.05,price:29.99,priceLabel:'$29.99 / kg'},
    tpu:{label:'TPU 95A HF',density:1.21,price:41.99,priceLabel:'$41.99 / kg'}
  };
  var PRINTERS={
    a1mini:{label:'A1 MINI',family:'A',x:180,y:180,z:180,mode:'SINGLE NOZZLE',enclosed:false},
    a1:{label:'A1',family:'A',x:256,y:256,z:256,mode:'SINGLE NOZZLE',enclosed:false},
    a2l:{label:'A2L',family:'A',x:330,y:320,z:325,mode:'SINGLE NOZZLE',enclosed:false},
    p1p:{label:'P1P',family:'P',x:256,y:256,z:256,mode:'SINGLE NOZZLE',enclosed:false},
    p1s:{label:'P1S',family:'P',x:256,y:256,z:256,mode:'SINGLE NOZZLE',enclosed:true},
    p2s:{label:'P2S',family:'P',x:256,y:256,z:256,mode:'SINGLE NOZZLE',enclosed:true},
    x1:{label:'X1',family:'X',x:256,y:256,z:256,mode:'SINGLE NOZZLE',enclosed:true},
    x1c:{label:'X1 CARBON',family:'X',x:256,y:256,z:256,mode:'SINGLE NOZZLE',enclosed:true},
    x1e:{label:'X1E',family:'X',x:256,y:256,z:256,mode:'SINGLE NOZZLE',enclosed:true},
    x2d:{label:'X2D · MAIN NOZZLE',family:'X',x:256,y:256,z:260,mode:'MAIN NOZZLE',enclosed:true},
    x2daux:{label:'X2D · AUX NOZZLE',family:'X',x:235.5,y:256,z:256,mode:'AUX NOZZLE',enclosed:true},
    x2dtotal:{label:'X2D · TOTAL',family:'X',x:256,y:256,z:260,mode:'TWO-NOZZLE UNION',enclosed:true},
    h2s:{label:'H2S',family:'H',x:340,y:320,z:340,mode:'SINGLE NOZZLE',enclosed:true},
    h2c:{label:'H2C · SINGLE NOZZLE',family:'H',x:325,y:320,z:320,mode:'SINGLE NOZZLE',enclosed:true},
    h2ctotal:{label:'H2C · TOTAL',family:'H',x:330,y:320,z:320,mode:'TWO-NOZZLE UNION',enclosed:true},
    h2d:{label:'H2D · SINGLE NOZZLE',family:'H',x:325,y:320,z:325,mode:'SINGLE NOZZLE',enclosed:true},
    h2ddual:{label:'H2D · DUAL INTERSECTION',family:'H',x:300,y:320,z:320,mode:'DUAL NOZZLE INTERSECTION',enclosed:true},
    h2dtotal:{label:'H2D · TOTAL',family:'H',x:350,y:320,z:320,mode:'TWO-NOZZLE UNION',enclosed:true},
    h2dpro:{label:'H2D PRO · SINGLE',family:'H',x:325,y:320,z:325,mode:'SINGLE NOZZLE',enclosed:true},
    h2dprodual:{label:'H2D PRO · DUAL INTERSECTION',family:'H',x:300,y:320,z:320,mode:'DUAL NOZZLE INTERSECTION',enclosed:true},
    h2dprototal:{label:'H2D PRO · TOTAL',family:'H',x:350,y:320,z:320,mode:'TWO-NOZZLE UNION',enclosed:true}
  };

  function el(id){return document.getElementById(id);}
  function number(id,fallback){var value=Number(el(id).value);return Number.isFinite(value)?value:fallback;}
  function status(id,text,kind){var node=el(id);node.textContent=text;node.className='labStatus'+(kind?' '+kind:'');}
  function tone(kind){
    try{
      if(window.JarvisFX&&window.JarvisFX.tone){window.JarvisFX.tone(kind==='bad'?'error':kind==='print'?'confirm':kind==='load'?'lab':'node');return;}
      var AC=window.AudioContext||window.webkitAudioContext;if(!AC)return;
      audioCtx=audioCtx||new AC();if(audioCtx.state==='suspended')audioCtx.resume();
      var now=audioCtx.currentTime,osc=audioCtx.createOscillator(),gain=audioCtx.createGain();
      var hz=kind==='bad'?155:(kind==='print'?620:(kind==='load'?410:285));
      osc.type='sine';osc.frequency.setValueAtTime(hz,now);if(kind==='print')osc.frequency.exponentialRampToValueAtTime(880,now+.16);
      gain.gain.setValueAtTime(.0001,now);gain.gain.exponentialRampToValueAtTime(.035,now+.018);gain.gain.exponentialRampToValueAtTime(.0001,now+.22);
      osc.connect(gain);gain.connect(audioCtx.destination);osc.start(now);osc.stop(now+.24);
    }catch(e){}
  }
  function safeName(name){return String(name||'model.stl').replace(/[^a-z0-9._ -]+/ig,'_').slice(0,100)||'model.stl';}
  function boundsOf(list){
    var min={x:Infinity,y:Infinity,z:Infinity},max={x:-Infinity,y:-Infinity,z:-Infinity};
    list.forEach(function(t){t.forEach(function(v){min.x=Math.min(min.x,v.x);min.y=Math.min(min.y,v.y);min.z=Math.min(min.z,v.z);max.x=Math.max(max.x,v.x);max.y=Math.max(max.y,v.y);max.z=Math.max(max.z,v.z);});});
    if(!Number.isFinite(min.x))return{min:{x:0,y:0,z:0},max:{x:1,y:1,z:1}};
    return{min:min,max:max};
  }
  function clamp(value,min,max,fallback){value=Number(value);if(!Number.isFinite(value))value=fallback;return Math.max(min,Math.min(max,value));}
  function vertex(x,y,z){return{x:Number(x)||0,y:Number(y)||0,z:Number(z)||0};}
  function recenter(){var b=boundsOf(triangles);modelCenter={x:(b.min.x+b.max.x)/2,y:(b.min.y+b.max.y)/2,z:(b.min.z+b.max.z)/2};}
  function snapshot(){return{triangles:triangles.slice(),fileName:fileName,modelCenter:{x:modelCenter.x,y:modelCenter.y,z:modelCenter.z}};}
  function updateHistory(){var node=el('labHistoryStatus');if(node)node.textContent='UNDO '+history.length+' · REDO '+future.length;}
  function pushHistory(){history.push(snapshot());if(history.length>MAX_HISTORY)history.shift();future=[];updateHistory();}
  function restoreSnapshot(state){triangles=(state&&state.triangles||[]).slice();fileName=state&&state.fileName||'';modelCenter=state&&state.modelCenter?{x:state.modelCenter.x,y:state.modelCenter.y,z:state.modelCenter.z}:{x:0,y:0,z:0};resetTransform();updateMetrics();}
  function undo(){if(!history.length){status('labModelStatus','NOTHING TO UNDO','');return;}future.push(snapshot());restoreSnapshot(history.pop());updateHistory();status('labModelStatus','UNDO COMPLETE','good');tone('ready');}
  function redo(){if(!future.length){status('labModelStatus','NOTHING TO REDO','');return;}history.push(snapshot());restoreSnapshot(future.pop());updateHistory();status('labModelStatus','REDO COMPLETE','good');tone('ready');}
  function replaceModel(next,name,placeOnBed){pushHistory();triangles=(next||[]).slice();fileName=safeName(name||'jarvis-created-model.stl');recenter();resetTransform();if(placeOnBed)snapToBed(false);orbitYaw=-.55;orbitPitch=.38;orbitZoom=1;updateMetrics();status('labModelStatus','CREATED · '+fileName+' · '+triangles.length.toLocaleString()+' TRIANGLES','good');status('labPrintStatus','READY FOR PRINT REVIEW','good');tone('load');}
  function cubeMesh(w,d,h){
    w=clamp(w,1,180,20);d=clamp(d,1,180,20);h=clamp(h,1,180,20);var x=w/2,y=d/2;
    var v=[vertex(-x,-y,0),vertex(x,-y,0),vertex(x,y,0),vertex(-x,y,0),vertex(-x,-y,h),vertex(x,-y,h),vertex(x,y,h),vertex(-x,y,h)];
    return[[v[0],v[2],v[1]],[v[0],v[3],v[2]],[v[4],v[5],v[6]],[v[4],v[6],v[7]],[v[0],v[1],v[5]],[v[0],v[5],v[4]],[v[1],v[2],v[6]],[v[1],v[6],v[5]],[v[2],v[3],v[7]],[v[2],v[7],v[6]],[v[3],v[0],v[4]],[v[3],v[4],v[7]]];
  }
  function sphereMesh(radius,segments,rings){
    radius=clamp(radius,1,90,15);segments=segments||28;rings=rings||16;var out=[];
    for(var j=0;j<rings;j++){var a0=Math.PI*j/rings,a1=Math.PI*(j+1)/rings;for(var i=0;i<segments;i++){var p0=2*Math.PI*i/segments,p1=2*Math.PI*(i+1)/segments;
      function p(a,b){return vertex(radius*Math.sin(a)*Math.cos(b),radius*Math.sin(a)*Math.sin(b),radius*Math.cos(a)+radius);}
      var v00=p(a0,p0),v01=p(a0,p1),v10=p(a1,p0),v11=p(a1,p1);if(j>0)out.push([v00,v10,v01]);if(j<rings-1)out.push([v01,v10,v11]);}}
    return out;
  }
  function cylinderMesh(radius,height,segments,topRadius){
    radius=clamp(radius,1,90,12);height=clamp(height,1,180,30);segments=segments||32;topRadius=topRadius===undefined?radius:clamp(topRadius,0,90,0);var out=[],bottom=vertex(0,0,0),top=vertex(0,0,height);
    for(var i=0;i<segments;i++){var a=2*Math.PI*i/segments,b=2*Math.PI*(i+1)/segments,b0=vertex(radius*Math.cos(a),radius*Math.sin(a),0),b1=vertex(radius*Math.cos(b),radius*Math.sin(b),0),t0=vertex(topRadius*Math.cos(a),topRadius*Math.sin(a),height),t1=vertex(topRadius*Math.cos(b),topRadius*Math.sin(b),height);out.push([b0,b1,t0],[b1,t1,t0],[bottom,b1,b0]);if(topRadius>0)out.push([top,t0,t1]);}
    return out;
  }
  function torusMesh(major,minor,segments,tubeSegments){
    major=clamp(major,2,80,18);minor=clamp(minor,.5,Math.max(1,major*.8),5);segments=segments||32;tubeSegments=tubeSegments||14;var out=[];
    function p(u,v){return vertex((major+minor*Math.cos(v))*Math.cos(u),(major+minor*Math.cos(v))*Math.sin(u),minor*Math.sin(v)+minor);}
    for(var i=0;i<segments;i++)for(var j=0;j<tubeSegments;j++){var u0=2*Math.PI*i/segments,u1=2*Math.PI*(i+1)/segments,v0=2*Math.PI*j/tubeSegments,v1=2*Math.PI*(j+1)/tubeSegments,a=p(u0,v0),b=p(u1,v0),c=p(u1,v1),d=p(u0,v1);out.push([a,b,d],[b,c,d]);}return out;
  }
  function wedgeMesh(width,depth,height){
    width=clamp(width,2,180,65);depth=clamp(depth,2,180,30);height=clamp(height,2,180,24);var x=width/2,y=depth/2,v=[vertex(-x,-y,0),vertex(-x,y,0),vertex(x,-y,0),vertex(x,y,0),vertex(x,-y,height),vertex(x,y,height)];
    return[[v[0],v[2],v[3]],[v[0],v[3],v[1]],[v[2],v[4],v[5]],[v[2],v[5],v[3]],[v[0],v[4],v[2]],[v[0],v[5],v[4]],[v[0],v[1],v[5]],[v[0],v[5],v[4]],[v[1],v[3],v[5]]];
  }
  function ringMesh(outer,inner,height,segments){
    outer=clamp(outer,2,90,18);inner=clamp(inner,.5,outer-.5,10);height=clamp(height,1,180,5);segments=segments||36;var out=[];
    for(var i=0;i<segments;i++){var a=2*Math.PI*i/segments,b=2*Math.PI*(i+1)/segments,ob0=vertex(outer*Math.cos(a),outer*Math.sin(a),0),ob1=vertex(outer*Math.cos(b),outer*Math.sin(b),0),ot0=vertex(ob0.x,ob0.y,height),ot1=vertex(ob1.x,ob1.y,height),ib0=vertex(inner*Math.cos(a),inner*Math.sin(a),0),ib1=vertex(inner*Math.cos(b),inner*Math.sin(b),0),it0=vertex(ib0.x,ib0.y,height),it1=vertex(ib1.x,ib1.y,height);out.push([ob0,ob1,ot0],[ob1,ot1,ot0],[ib0,it0,ib1],[ib1,it0,it1],[ot0,ot1,it0],[ot1,it1,it0],[ob0,ib0,ob1],[ob1,ib0,ib1]);}return out;
  }
  function boatHullMesh(length,width,height){
    length=clamp(length,30,150,90);width=clamp(width,18,90,42);height=clamp(height,8,70,22);
    var xs=[-length/2,-length*.32,0,length*.31,length/2],half=[1,width*.38,width*.50,width*.41,1],tops=[height*.35,height*.78,height,height*.82,height*.42],out=[];
    var sections=xs.map(function(x,i){return[vertex(x,-half[i]*.36,0),vertex(x,half[i]*.36,0),vertex(x,-half[i],tops[i]),vertex(x,half[i],tops[i])];});
    for(var i=0;i<sections.length-1;i++){
      var a=sections[i],b=sections[i+1];
      out.push([a[0],b[0],b[1]],[a[0],b[1],a[1]]);
      out.push([a[0],a[2],b[2]],[a[0],b[2],b[0]]);
      out.push([a[1],b[1],b[3]],[a[1],b[3],a[3]]);
      out.push([a[2],a[3],b[3]],[a[2],b[3],b[2]]);
    }
    var first=sections[0],last=sections[sections.length-1];
    out.push([first[0],first[1],first[3]],[first[0],first[3],first[2]]);
    out.push([last[0],last[3],last[1]],[last[0],last[2],last[3]]);
    return out;
  }
  function offsetMesh(mesh,pos){pos=pos||{};var x=clamp(pos.x,-180,180,0),y=clamp(pos.y,-180,180,0),z=clamp(pos.z,-180,180,0);return mesh.map(function(t){return t.map(function(v){return vertex(v.x+x,v.y+y,v.z+z);});});}
  function primitiveMesh(type,params){params=params||{};if(type==='sphere')return sphereMesh(params.r||params.radius);if(type==='cylinder')return cylinderMesh(params.r||params.radius,params.h||params.height);if(type==='cone')return cylinderMesh(params.r||params.radius,params.h||params.height,32,0);if(type==='torus')return torusMesh(params.major||params.majorRadius,params.minor||params.tubeRadius);if(type==='wedge')return wedgeMesh(params.w||params.width,params.d||params.depth,params.h||params.height);if(type==='ring')return ringMesh(params.outer||params.outerRadius,params.inner||params.innerRadius,params.h||params.height);if(type==='boat_hull')return boatHullMesh(params.length||params.l,params.width||params.w,params.height||params.h);return cubeMesh(params.w||params.width,params.d||params.depth,params.h||params.height);}
  function createPrimitive(type){var defaults={cube:{w:25,d:25,h:25},sphere:{r:16},cylinder:{r:14,h:30},cone:{r:16,h:32},torus:{major:20,minor:5},wedge:{w:65,d:30,h:24},ring:{outer:20,inner:12,h:5}};replaceModel(primitiveMesh(type,defaults[type]),'jarvis-'+type+'.stl',true);}
  function parseBinaryStl(buffer){
    if(buffer.byteLength<84)return null;
    var view=new DataView(buffer),count=view.getUint32(80,true);
    if(count<1||84+count*50>buffer.byteLength)return null;
    var out=new Array(count),offset=84;
    for(var i=0;i<count;i++,offset+=50){
      out[i]=[
        {x:view.getFloat32(offset+12,true),y:view.getFloat32(offset+16,true),z:view.getFloat32(offset+20,true)},
        {x:view.getFloat32(offset+24,true),y:view.getFloat32(offset+28,true),z:view.getFloat32(offset+32,true)},
        {x:view.getFloat32(offset+36,true),y:view.getFloat32(offset+40,true),z:view.getFloat32(offset+44,true)}
      ];
    }
    return out;
  }
  function parseAsciiStl(text){
    var points=[],match,re=/\bvertex\s+([-+\deE.]+)\s+([-+\deE.]+)\s+([-+\deE.]+)/g;
    while((match=re.exec(text))){points.push({x:Number(match[1]),y:Number(match[2]),z:Number(match[3])});if(points.length>900000)throw new Error('Model is too detailed for the in-app preview.');}
    var out=[];for(var i=0;i+2<points.length;i+=3)out.push([points[i],points[i+1],points[i+2]]);return out;
  }
  function parseObj(text){
    var vertices=[],out=[];
    text.split(/\r?\n/).forEach(function(line){
      line=line.trim();if(!line||line[0]==='#')return;
      if(line.indexOf('v ')===0){var p=line.split(/\s+/);if(p.length>=4)vertices.push({x:Number(p[1]),y:Number(p[2]),z:Number(p[3])});return;}
      if(line.indexOf('f ')===0){
        var ids=line.slice(2).trim().split(/\s+/).map(function(token){var n=parseInt(token.split('/')[0],10);return n<0?vertices.length+n:n-1;}).filter(function(n){return n>=0&&n<vertices.length;});
        for(var i=1;i+1<ids.length;i++)out.push([vertices[ids[0]],vertices[ids[i]],vertices[ids[i+1]]]);
      }
    });
    return out;
  }
  function parseModel(file,buffer){
    var lower=file.name.toLowerCase();
    if(lower.endsWith('.obj'))return parseObj(new TextDecoder('utf-8').decode(buffer));
    var binary=parseBinaryStl(buffer);return binary||parseAsciiStl(new TextDecoder('utf-8').decode(buffer));
  }
  function resetTransform(){
    ['labRotX','labRotY','labRotZ','labMoveX','labMoveY','labMoveZ'].forEach(function(id){el(id).value='0';});el('labScale').value='100';lastScalePercent=100;updateMetrics();
  }
  function printerProfile(){var picker=el('labPrinter'),key=picker&&picker.value||'a1mini';return PRINTERS[key]||PRINTERS.a1mini;}
  function materialProfile(){var picker=el('labMaterial'),key=picker&&picker.value||'pla';return MATERIALS[key]||MATERIALS.pla;}
  function updateFactoryLabels(){
    var printer=printerProfile(),material=materialProfile(),fitLabel=el('labFitLabel'),price=el('labMaterialPrice'),autoFit=el('labAutoFitBtn'),profile=el('labPrinterProfile');
    if(fitLabel)fitLabel.textContent=printer.label+' FIT';
    if(price)price.textContent=material.priceLabel+' · FACTORY REFERENCE';
    if(autoFit)autoFit.textContent='FIT '+printer.label.replace(/ ·.*$/,'');
    if(profile)profile.innerHTML='<b>'+printer.label+'</b> · '+printer.family+' SERIES\nBUILD VOLUME · '+printer.x+' × '+printer.y+' × '+printer.z+' mm\nMODE · '+printer.mode+' · '+(printer.enclosed?'ENCLOSED':'OPEN FRAME')+'\nFIT LIMITS · X '+printer.x+' · Y '+printer.y+' · Z '+printer.z+' mm';
    try{if(el('labPrinter'))localStorage.setItem('jarvis_lab_printer_v1',el('labPrinter').value);if(el('labMaterial'))localStorage.setItem('jarvis_lab_material_v1',el('labMaterial').value);}catch(e){}
  }
  function transformPoint(v){
    var s=Math.max(.01,number('labScale',100)/100),x=(v.x-modelCenter.x)*s,y=(v.y-modelCenter.y)*s,z=(v.z-modelCenter.z)*s;
    var rx=number('labRotX',0)*Math.PI/180,ry=number('labRotY',0)*Math.PI/180,rz=number('labRotZ',0)*Math.PI/180;
    var cy=Math.cos(rx),sy=Math.sin(rx),y1=y*cy-z*sy,z1=y*sy+z*cy;y=y1;z=z1;
    cy=Math.cos(ry);sy=Math.sin(ry);var x1=x*cy+z*sy;z1=-x*sy+z*cy;x=x1;z=z1;
    cy=Math.cos(rz);sy=Math.sin(rz);x1=x*cy-y*sy;y1=x*sy+y*cy;x=x1;y=y1;
    return{x:x+number('labMoveX',0),y:y+number('labMoveY',0),z:z+number('labMoveZ',0)};
  }
  function transformedBounds(){
    var min={x:Infinity,y:Infinity,z:Infinity},max={x:-Infinity,y:-Infinity,z:-Infinity},volume=0,surface=0;
    triangles.forEach(function(t){
      var a=transformPoint(t[0]),b=transformPoint(t[1]),c=transformPoint(t[2]);
      [a,b,c].forEach(function(v){min.x=Math.min(min.x,v.x);min.y=Math.min(min.y,v.y);min.z=Math.min(min.z,v.z);max.x=Math.max(max.x,v.x);max.y=Math.max(max.y,v.y);max.z=Math.max(max.z,v.z);});
      volume+=(a.x*(b.y*c.z-b.z*c.y)-a.y*(b.x*c.z-b.z*c.x)+a.z*(b.x*c.y-b.y*c.x))/6;
      var ux=b.x-a.x,uy=b.y-a.y,uz=b.z-a.z,vx=c.x-a.x,vy=c.y-a.y,vz=c.z-a.z;
      surface+=Math.hypot(uy*vz-uz*vy,uz*vx-ux*vz,ux*vy-uy*vx)/2;
    });
    return{min:min,max:max,volume:Math.abs(volume),surface:surface};
  }
  function formatTime(minutes){minutes=Math.max(1,Math.round(minutes));var h=Math.floor(minutes/60),m=minutes%60;return h?(h+'h '+String(m).padStart(2,'0')+'m'):(m+'m');}
  function updateMetrics(){
    if(!triangles.length){lastMetrics=null;['labDimensions','labTriangles','labVolume','labSurface','labGrams','labTime','labCost','labA1Fit'].forEach(function(id){el(id).textContent='—';});updateFactoryLabels();return;}
    var stats=transformedBounds(),dx=Math.abs(stats.max.x-stats.min.x),dy=Math.abs(stats.max.y-stats.min.y),dz=Math.abs(stats.max.z-stats.min.z);
    var infill=Math.max(0,Math.min(100,number('labInfill',15)))/100,layer=Math.max(.08,Math.min(.4,number('labLayer',.2)));
    var solidCm3=stats.volume/1000;if(!Number.isFinite(solidCm3)||solidCm3<.01)solidCm3=(dx*dy*dz/1000)*.18;
    var material=materialProfile(),density=material.density,costPerKg=material.price,walls=clamp(number('labWalls',2),1,12,2),supports=el('labSupports')?el('labSupports').value:'OFF',iron=el('labIroning')?el('labIroning').value:'OFF',outerSpeed=clamp(number('labOuterSpeed',120),10,500,120),shellAndFill=Math.min(.92,.20+walls*.055+.62*infill);
    var supportFactor=supports==='OFF'?1:1.10,grams=Math.max(.2,solidCm3*density*shellAndFill*supportFactor),speedFactor=Math.max(.55,Math.min(2.5,120/outerSpeed)),minutes=grams*5.8*(.20/layer)*speedFactor*(iron==='OFF'?1:1.12),cost=grams/1000*costPerKg;
    var printer=printerProfile(),marginX=(printer.x-dx)/2,marginY=(printer.y-dy)/2,marginZ=printer.z-dz,fits=marginX>=-.01&&marginY>=-.01&&marginZ>=-.01&&stats.min.z>=-.21&&stats.max.z<=printer.z+.21;
    lastMetrics={dx:dx,dy:dy,dz:dz,grams:grams,minutes:minutes,layer:layer,infill:infill*100,volume:solidCm3,surface:stats.surface/100,cost:cost,fits:fits,printer:printer.label,material:material.label,marginX:marginX,marginY:marginY,marginZ:marginZ};
    el('labDimensions').textContent=Math.round(dx)+'×'+Math.round(dy)+'×'+Math.round(dz)+' mm';el('labTriangles').textContent=triangles.length.toLocaleString();el('labVolume').textContent=solidCm3.toFixed(1)+' cm³';el('labSurface').textContent=(stats.surface/100).toFixed(1)+' cm²';el('labGrams').textContent=grams.toFixed(1)+' g';el('labTime').textContent=formatTime(minutes);el('labCost').textContent='$'+cost.toFixed(2);el('labA1Fit').textContent=fits?'YES':'NO';
    updateFactoryLabels();
  }
  function slicePreset(){return{
    printer:el('labPrinter').value,printer_label:printerProfile().label,build_volume:[printerProfile().x,printerProfile().y,printerProfile().z],material:el('labMaterial').value,quality:el('labQualityPreset').value,layer_mm:number('labLayer',.2),first_layer_mm:number('labFirstLayer',.2),line_width_mm:number('labLineWidth',.42),infill_percent:number('labInfill',15),nozzle_mm:number('labNozzle',.4),wall_generator:el('labWallGenerator').value,wall_loops:number('labWalls',2),top_layers:number('labTopLayers',4),bottom_layers:number('labBottomLayers',3),top_pattern:el('labTopPattern').value,bottom_pattern:el('labBottomPattern').value,infill_pattern:el('labInfillPattern').value,supports:el('labSupports').value,support_style:el('labSupportStyle').value,support_threshold_deg:number('labSupportAngle',30),brim:el('labBrim').value,brim_width_mm:number('labBrimWidth',5),skirt_loops:number('labSkirtLoops',0),seam:el('labSeam').value,ironing:el('labIroning').value,elephant_foot_mm:number('labElephantFoot',.15),plate:el('labPlateType').value,sequence:el('labSequence').value,timelapse:el('labTimelapse').value,outer_wall_speed:number('labOuterSpeed',120),inner_wall_speed:number('labInnerSpeed',200),infill_speed:number('labInfillSpeed',250),first_layer_speed:number('labFirstLayerSpeed',50),travel_speed:number('labTravelSpeed',500)
  };}
  function applyQualityPreset(){var key=el('labQualityPreset').value,presets={fine:{layer:.12,walls:3,infill:15,outer:80},standard:{layer:.20,walls:2,infill:15,outer:120},strength:{layer:.20,walls:4,infill:25,outer:90},draft:{layer:.28,walls:2,infill:10,outer:160}},p=presets[key]||presets.standard;el('labLayer').value=p.layer.toFixed(2);el('labWalls').value=p.walls;el('labInfill').value=p.infill;el('labOuterSpeed').value=p.outer;updateMetrics();tone('node');}
  function exportPreset(){var data={format:'JARVIS-LAB-PRESET',version:2,created_at:new Date().toISOString(),model:safeName(fileName||'unsaved-model.stl'),settings:slicePreset(),estimate:lastMetrics};downloadBlob(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),'jarvis-lab-preset.json');status('labPrintStatus','LAB PRESET EXPORTED','good');tone('ready');}
  function viewerRotate(v){
    var cy=Math.cos(orbitYaw),sy=Math.sin(orbitYaw),x=v.x*cy+v.z*sy,z=-v.x*sy+v.z*cy;
    cy=Math.cos(orbitPitch);sy=Math.sin(orbitPitch);var y=v.y*cy-z*sy,z2=v.y*sy+z*cy;return{x:x,y:y,z:z2};
  }
  function projectPoint(v,cx,cy,scale){var r=viewerRotate(v);return{x:cx+r.x*scale,y:cy-r.y*scale,z:r.z};}
  function drawBuildPlate(cx,cy,scale){
    var p=printerProfile(),hx=p.x/2,hy=p.y/2,corners=[vertex(-hx,-hy,0),vertex(hx,-hy,0),vertex(hx,hy,0),vertex(-hx,hy,0)].map(function(v){return projectPoint(v,cx,cy,scale);});
    ctx.beginPath();ctx.moveTo(corners[0].x,corners[0].y);for(var c=1;c<corners.length;c++)ctx.lineTo(corners[c].x,corners[c].y);ctx.closePath();ctx.fillStyle='rgba(0,229,255,.028)';ctx.fill();ctx.strokeStyle='rgba(58,255,196,.52)';ctx.lineWidth=1.2;ctx.stroke();
    if(showGrid){
      var step=(Math.max(p.x,p.y)>300)?40:20;ctx.strokeStyle='rgba(0,229,255,.14)';ctx.lineWidth=.8;
      for(var x=-Math.floor(hx/step)*step;x<=hx;x+=step){var a=projectPoint(vertex(x,-hy,0),cx,cy,scale),b=projectPoint(vertex(x,hy,0),cx,cy,scale);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();}
      for(var y=-Math.floor(hy/step)*step;y<=hy;y+=step){var d=projectPoint(vertex(-hx,y,0),cx,cy,scale),e=projectPoint(vertex(hx,y,0),cx,cy,scale);ctx.beginPath();ctx.moveTo(d.x,d.y);ctx.lineTo(e.x,e.y);ctx.stroke();}
      var zTop=p.z,verticals=[vertex(-hx,-hy,zTop),vertex(hx,-hy,zTop),vertex(hx,hy,zTop),vertex(-hx,hy,zTop)].map(function(v){return projectPoint(v,cx,cy,scale);});
      ctx.setLineDash([4,7]);ctx.strokeStyle='rgba(0,229,255,.08)';for(var i=0;i<4;i++){ctx.beginPath();ctx.moveTo(corners[i].x,corners[i].y);ctx.lineTo(verticals[i].x,verticals[i].y);ctx.stroke();}ctx.setLineDash([]);
    }
    var label=projectPoint(vertex(0,-hy-8,0),cx,cy,scale);ctx.fillStyle='rgba(58,255,196,.55)';ctx.font='9px JetBrains Mono, monospace';ctx.textAlign='center';ctx.fillText(p.label+' · '+p.x+' × '+p.y+' × '+p.z+' MM',label.x,label.y);
  }
  function draw(){
    if(!canvas||!ctx){requestAnimationFrame(draw);return;}
    var dpr=Math.min(2,window.devicePixelRatio||1),rect=canvas.getBoundingClientRect(),w=Math.max(1,rect.width),h=Math.max(1,rect.height);
    if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
    var p=printerProfile(),cx=w*.5,cy=h*.57,scale=Math.min(w*.54/Math.max(1,p.x),h*.60/Math.max(1,p.y))*orbitZoom;
    drawBuildPlate(cx,cy,scale);
    if(triangles.length){
      var b=transformedBounds(),maxDim=Math.max(1,b.max.x-b.min.x,b.max.y-b.min.y,b.max.z-b.min.z),step=Math.max(1,Math.ceil(triangles.length/7000));
      ctx.lineWidth=.7;
      for(var i=0;i<triangles.length;i+=step){
        var t=triangles[i].map(function(v){return viewerRotate(transformPoint(v));});
        var pts=t.map(function(v){return{x:cx+v.x*scale,y:cy-v.y*scale,z:v.z};});
        var shade=Math.max(.10,Math.min(.42,.26+(pts[0].z+pts[1].z+pts[2].z)/(3*maxDim)*.25));
        ctx.beginPath();ctx.moveTo(pts[0].x,pts[0].y);ctx.lineTo(pts[1].x,pts[1].y);ctx.lineTo(pts[2].x,pts[2].y);ctx.closePath();if(!wireframe){ctx.fillStyle='rgba(0,229,255,'+shade+')';ctx.fill();}ctx.strokeStyle=wireframe?'rgba(58,255,196,.68)':'rgba(58,255,196,.26)';ctx.stroke();
      }
    }else{
      ctx.fillStyle='rgba(0,229,255,.32)';ctx.font='11px JetBrains Mono, monospace';ctx.textAlign='center';ctx.fillText('IMPORT STL OR OBJ',cx,cy);
    }
    requestAnimationFrame(draw);
  }
  function exportStl(){
    var buffer=new ArrayBuffer(84+triangles.length*50),view=new DataView(buffer);for(var h=0;h<80;h++)view.setUint8(h,0);view.setUint32(80,triangles.length,true);var off=84;
    triangles.forEach(function(t){
      var a=transformPoint(t[0]),b=transformPoint(t[1]),c=transformPoint(t[2]),ux=b.x-a.x,uy=b.y-a.y,uz=b.z-a.z,vx=c.x-a.x,vy=c.y-a.y,vz=c.z-a.z,nx=uy*vz-uz*vy,ny=uz*vx-ux*vz,nz=ux*vy-uy*vx,len=Math.hypot(nx,ny,nz)||1;nx/=len;ny/=len;nz/=len;
      [nx,ny,nz,a.x,a.y,a.z,b.x,b.y,b.z,c.x,c.y,c.z].forEach(function(n,index){view.setFloat32(off+index*4,n,true);});view.setUint16(off+48,0,true);off+=50;
    });
    return buffer;
  }
  function bufferToBase64(buffer){
    var bytes=new Uint8Array(buffer),chunk=0x8000,out='';for(var i=0;i<bytes.length;i+=chunk)out+=String.fromCharCode.apply(null,bytes.subarray(i,Math.min(i+chunk,bytes.length)));return btoa(out);
  }
  function snapToBed(record){if(!triangles.length)return;if(record!==false)pushHistory();var b=transformedBounds();el('labMoveZ').value=(number('labMoveZ',0)-b.min.z).toFixed(2);updateMetrics();status('labModelStatus','PLACED ON PRINT BED','good');tone('ready');}
  function centerXY(){if(!triangles.length)return;pushHistory();el('labMoveX').value='0';el('labMoveY').value='0';updateMetrics();status('labModelStatus','CENTERED ON BUILD PLATE','good');tone('ready');}
  function autoFitA1(){if(!triangles.length)return;pushHistory();var b=transformedBounds(),p=printerProfile(),dx=Math.max(1,b.max.x-b.min.x),dy=Math.max(1,b.max.y-b.min.y),dz=Math.max(1,b.max.z-b.min.z),factor=Math.min(1,(p.x-4)/dx,(p.y-4)/dy,(p.z-4)/dz);setScalePreservingPlacement(number('labScale',100)*factor);el('labMoveX').value='0';el('labMoveY').value='0';snapToBed(false);updateMetrics();status('labModelStatus',lastMetrics&&lastMetrics.fits?'FITTED TO '+p.label+' ENVELOPE':'FIT NEEDS MANUAL CHECK','good');tone('ready');}
  function mirrorAxis(axis){if(!triangles.length)return;pushHistory();triangles=triangles.map(function(t){return [t[0],t[2],t[1]].map(function(v){return vertex(axis==='x'?-v.x:v.x,axis==='y'?-v.y:v.y,axis==='z'?-v.z:v.z);});});recenter();resetTransform();snapToBed(false);status('labModelStatus','MIRRORED '+axis.toUpperCase(),'good');tone('ready');}
  function duplicateModel(){if(!triangles.length)return;pushHistory();var b=boundsOf(triangles),offset=Math.max(8,b.max.x-b.min.x+8),copy=offsetMesh(triangles,{x:offset,y:0,z:0});triangles=triangles.concat(copy);recenter();resetTransform();snapToBed(false);status('labModelStatus','DUPLICATED MODEL','good');tone('ready');}
  function clearModel(){if(!triangles.length)return;pushHistory();triangles=[];fileName='';modelCenter={x:0,y:0,z:0};resetTransform();updateMetrics();status('labModelStatus','MODEL CLEARED','');status('labPrintStatus','CREATE OR IMPORT A MODEL','');tone('ready');}
  function rotatePreset(axis){var id='labRot'+axis.toUpperCase();el(id).value=number(id,0)+90;updateMetrics();tone('node');}
  function placementAnchor(){if(!triangles.length)return null;var b=transformedBounds();return{x:(b.min.x+b.max.x)/2,y:(b.min.y+b.max.y)/2,z:b.min.z};}
  function restorePlacementAnchor(anchor){if(!anchor||!triangles.length)return;var b=transformedBounds(),cx=(b.min.x+b.max.x)/2,cy=(b.min.y+b.max.y)/2;el('labMoveX').value=(number('labMoveX',0)+anchor.x-cx).toFixed(2);el('labMoveY').value=(number('labMoveY',0)+anchor.y-cy).toFixed(2);el('labMoveZ').value=(number('labMoveZ',0)+anchor.z-b.min.z).toFixed(2);}
  function setScalePreservingPlacement(next){var anchor=placementAnchor();next=clamp(next,1,500,100);el('labScale').value=String(Number(next.toFixed(2)));lastScalePercent=next;restorePlacementAnchor(anchor);updateMetrics();}
  function scalePreset(percent){setScalePreservingPlacement(number('labScale',100)*Number(percent)/100);tone('node');}
  function setView(name){var presets={iso:[-.55,.38],top:[0,0],front:[0,Math.PI/2],right:[-Math.PI/2,Math.PI/2]},p=presets[name]||presets.iso;orbitYaw=p[0];orbitPitch=p[1];orbitZoom=1;tone('node');}
  function downloadBlob(blob,name){var a=document.createElement('a'),url=URL.createObjectURL(blob);a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url);},1000);}
  function downloadStl(){if(!triangles.length){status('labModelStatus','CREATE OR IMPORT A MODEL FIRST','bad');tone('bad');return;}downloadBlob(new Blob([exportStl()],{type:'model/stl'}),safeName(fileName||'jarvis-model.stl').replace(/\.[^.]+$/,'.stl'));status('labModelStatus','STL EXPORTED','good');tone('print');}
  function snapshotPng(){if(!canvas)return;canvas.toBlob(function(blob){if(blob){downloadBlob(blob,safeName(fileName||'jarvis-model').replace(/\.[^.]+$/,'')+'-preview.png');tone('ready');}},'image/png');}
  function metricText(){updateMetrics();if(!lastMetrics)return 'No model loaded.';return 'JARVIS LAB · '+safeName(fileName)+' · '+Math.round(lastMetrics.dx)+'×'+Math.round(lastMetrics.dy)+'×'+Math.round(lastMetrics.dz)+' mm · '+lastMetrics.volume.toFixed(1)+' cm³ · '+lastMetrics.grams.toFixed(1)+' g · '+formatTime(lastMetrics.minutes)+' · '+(lastMetrics.fits?lastMetrics.printer+' fit':lastMetrics.printer+' check required');}
  function copyStats(){var text=metricText();if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(text).then(function(){status('labModelStatus','MODEL STATS COPIED','good');tone('ready');});else status('labModelStatus',text,'good');}
  function fitCheck(){updateMetrics();if(!lastMetrics){status('labPrintStatus','CREATE OR IMPORT A MODEL FIRST','bad');return;}status('labPrintStatus',lastMetrics.fits?lastMetrics.printer+' SIZE CHECK PASSED':lastMetrics.printer+' SIZE CHECK FAILED · USE AUTO FIT',''+(lastMetrics.fits?'good':'bad'));tone(lastMetrics.fits?'ready':'bad');}
  function combineParts(parts){var all=[];(parts||[]).slice(0,24).forEach(function(part){var type=String(part&&part.type||'cube').toLowerCase();if(['cube','sphere','cylinder','cone','torus','wedge','ring','boat_hull'].indexOf(type)<0)return;var mesh=primitiveMesh(type,part.params||{});all=all.concat(offsetMesh(mesh,part.position||{}));});return all;}
  function semanticDesign(prompt){var p=String(prompt||'').toLowerCase(),nums=(p.match(/\d+(?:\.\d+)?/g)||[]).map(Number),a=nums[0],b=nums[1],c=nums[2];
    if(/\bboat\b|\bship\b|\bbenchy\b/.test(p)){var l=clamp(a||90,35,150,90),w=clamp(b||Math.round(l*.46),18,85,42),h=clamp(c||Math.round(l*.24),8,55,22);return{name:'printable-boat',parts:[{type:'boat_hull',params:{length:l,width:w,height:h}},{type:'cube',params:{w:l*.25,d:w*.48,h:h*.55},position:{x:l*.08,y:0,z:h*.68}}]};}
    if(/door\s*stop|wedge/.test(p))return{name:'door-stop',parts:[{type:'wedge',params:{w:a||70,d:b||32,h:c||24}}]};
    if(/phone.*stand|stand.*phone/.test(p))return{name:'phone-stand',parts:[{type:'cube',params:{w:a||75,d:55,h:5}},{type:'wedge',params:{w:a||75,d:25,h:60},position:{y:12,z:5}},{type:'cube',params:{w:a||75,d:8,h:10},position:{y:-22,z:5}}]};
    if(/tray/.test(p))return{name:'tray',parts:[{type:'cube',params:{w:a||100,d:b||70,h:3}},{type:'cube',params:{w:a||100,d:3,h:c||14},position:{y:-((b||70)/2),z:3}},{type:'cube',params:{w:a||100,d:3,h:c||14},position:{y:(b||70)/2,z:3}},{type:'cube',params:{w:3,d:b||70,h:c||14},position:{x:-((a||100)/2),z:3}},{type:'cube',params:{w:3,d:b||70,h:c||14},position:{x:(a||100)/2,z:3}}]};
    if(/bracket|l.?bracket/.test(p))return{name:'bracket',parts:[{type:'cube',params:{w:a||50,d:b||20,h:5}},{type:'cube',params:{w:5,d:b||20,h:c||45},position:{x:-((a||50)/2),z:(c||45)/2}}]};
    if(/washer|ring|cable.*clip/.test(p))return{name:'ring',parts:[{type:'ring',params:{outer:a||20,inner:b||12,h:c||5}}]};
    if(/planter|plant.*pot|pencil.*cup|cup.*holder/.test(p))return{name:'hollow-container',parts:[{type:'cylinder',params:{r:(a||64)/2,h:b||3}},{type:'ring',params:{outer:(a||64)/2,inner:Math.max(2,(a||64)/2-3),h:c||65},position:{z:3}}]};
    if(/coaster/.test(p))return{name:'coaster',parts:[{type:'cylinder',params:{r:(a||92)/2,h:b||4}},{type:'ring',params:{outer:(a||92)/2,inner:Math.max(2,(a||92)/2-3),h:2},position:{z:b||4}}]};
    if(/headphone.*stand|headset.*stand/.test(p))return{name:'headphone-stand',parts:[{type:'cube',params:{w:90,d:70,h:6}},{type:'cube',params:{w:12,d:18,h:110},position:{z:58}},{type:'cube',params:{w:70,d:22,h:8},position:{z:112}}]};
    if(/cable.*organizer|cord.*organizer/.test(p))return{name:'cable-organizer',parts:[{type:'cube',params:{w:a||90,d:b||28,h:5}},{type:'ring',params:{outer:8,inner:4,h:10},position:{x:-28,z:5}},{type:'ring',params:{outer:8,inner:4,h:10},position:{z:5}},{type:'ring',params:{outer:8,inner:4,h:10},position:{x:28,z:5}}]};
    if(/handle|drawer.*pull/.test(p))return{name:'handle',parts:[{type:'cylinder',params:{r:5,h:18},position:{x:-35}},{type:'cylinder',params:{r:5,h:18},position:{x:35}},{type:'cube',params:{w:a||80,d:10,h:10},position:{z:18}}]};
    if(/sphere|ball/.test(p))return{name:'sphere',parts:[{type:'sphere',params:{r:(a||32)/2}}]};
    if(/cylinder|spacer|knob/.test(p))return{name:'cylinder',parts:[{type:'cylinder',params:{r:(a||28)/2,h:b||30}}]};
    if(/cone/.test(p))return{name:'cone',parts:[{type:'cone',params:{r:(a||32)/2,h:b||35}}]};
    if(/torus/.test(p))return{name:'torus',parts:[{type:'torus',params:{major:a||20,minor:b||5}}]};
    if(/\b(?:box|cube|block)\b/.test(p))return{name:'custom-box',parts:[{type:'cube',params:{w:a||40,d:b||40,h:c||20}}]};
    return null;
  }
  function fallbackDesign(prompt){return semanticDesign(prompt);}
  function rawMeshVolumeCm3(mesh){var volume=0;(mesh||[]).forEach(function(t){var a=t[0],b=t[1],c=t[2];volume+=(a.x*(b.y*c.z-b.z*c.y)-a.y*(b.x*c.z-b.z*c.x)+a.z*(b.x*c.y-b.y*c.x))/6;});return Math.abs(volume)/1000;}
  function scaleRawMesh(mesh,factor){var b=boundsOf(mesh),cx=(b.min.x+b.max.x)/2,cy=(b.min.y+b.max.y)/2,cz=(b.min.z+b.max.z)/2;return mesh.map(function(t){return t.map(function(v){return vertex(cx+(v.x-cx)*factor,cy+(v.y-cy)*factor,cz+(v.z-cz)*factor);});});}
  function normalizeGeneratedMesh(mesh,prompt){var b=boundsOf(mesh),p=printerProfile(),dx=Math.max(1,b.max.x-b.min.x),dy=Math.max(1,b.max.y-b.min.y),dz=Math.max(1,b.max.z-b.min.z),explicit=/\b\d+(?:\.\d+)?\s*(?:mm|millimeter|millimetre|cm|centimeter|centimetre)s?\b/i.test(prompt),factor=Math.min(1,(p.x-8)/dx,(p.y-8)/dy,(p.z-8)/dz);if(!explicit){factor=Math.min(factor,SAFE_GENERATED_MM/Math.max(dx,dy,dz));var volume=rawMeshVolumeCm3(mesh);if(volume>SAFE_GENERATED_CM3)factor=Math.min(factor,Math.cbrt(SAFE_GENERATED_CM3/volume));}return{mesh:factor<.999?scaleRawMesh(mesh,factor):mesh,scaled:factor<.999,factor:factor};}
  function callDesigner(prompt){return new Promise(function(resolve){if(!api.callAIText){resolve(null);return;}var instruction='You are JARVIS LAB, a benign parametric 3D-print geometry planner. Build a recognizable printable approximation from multiple solids instead of answering with one unrelated primitive. Return ONLY compact JSON, no markdown. Schema: {"name":"model","parts":[{"type":"cube|sphere|cylinder|cone|torus|wedge|ring|boat_hull","params":{},"position":{"x":0,"y":0,"z":0}}]}. Use millimeters and at most 24 parts. Unless the user gives dimensions, keep the complete object under 120mm and roughly under 180 cm3. Keep parts touching or overlapping so the result is a connected model, and keep its lowest geometry at or above Z=0. A boat or ship MUST use boat_hull, never a lone cylinder. If the available primitives cannot represent the request reasonably, return {"error":"design needs geometry JARVIS LAB cannot create yet"} instead of inventing a random cylinder or box. Decline weapons, lock-bypass tools, or dangerous objects by returning {"error":"unsupported design"}. Request: '+String(prompt||'').slice(0,500);api.callAIText(instruction,function(reply,err){if(err||!reply){resolve(null);return;}try{var clean=String(reply).replace(/^```(?:json)?/i,'').replace(/```$/,'').trim();resolve(JSON.parse(clean));}catch(e){resolve(null);}});});}
  function designFromPrompt(prompt){prompt=String(prompt||'').trim();if(!prompt||designBusy)return;if(/\b(?:gun|firearm|weapon|knife|blade|lockpick|lock pick|explosive|bomb)\b/i.test(prompt)){status('labDesignStatus','DESIGN NOT SUPPORTED · TRY A BENIGN PART, TOOL HOLDER, BRACKET, STAND, OR PROTOTYPE','bad');tone('bad');return;}designBusy=true;status('labDesignStatus','JARVIS IS PLANNING PRINTABLE GEOMETRY…','');tone('node');var known=semanticDesign(prompt),plan=known?Promise.resolve(known):callDesigner(prompt);plan.then(function(spec){if(spec&&spec.error)throw new Error(spec.error);spec=spec&&Array.isArray(spec.parts)?spec:fallbackDesign(prompt);if(!spec||!Array.isArray(spec.parts))throw new Error('I could not make a recognizable printable model from that prompt. Add a shape, purpose, or dimensions and try again.');var mesh=combineParts(spec.parts);if(!mesh.length)throw new Error('No printable parts were produced.');var normalized=normalizeGeneratedMesh(mesh,prompt);replaceModel(normalized.mesh,safeName(spec.name||'jarvis-design')+'.stl',true);status('labDesignStatus','DESIGNED · '+safeName(spec.name||'JARVIS MODEL').toUpperCase()+' · '+spec.parts.length+' PART'+(spec.parts.length===1?'':'S')+(normalized.scaled?' · AUTO-SCALED TO PRACTICAL PRINT SIZE':''),'good');if(api.setCaption)api.setCaption('JARVIS LAB designed '+(spec.name||'the model')+(normalized.scaled?' and scaled it to a practical print size.':'.'));}).catch(function(error){status('labDesignStatus','DESIGN FAILED · '+String(error.message||error),'bad');tone('bad');}).finally(function(){designBusy=false;});}
  function handleVoiceCommand(command){var cmd=String(command||'').toLowerCase().replace(/^jarvis[, ]*/,'').trim(),m;if(!cmd)return false;
    if((m=cmd.match(/(?:design|make|create)(?: me)?(?: a| an)? (.+?)(?: model)?$/))){if(api.openLab)api.openLab();if(el('labDesignPrompt'))el('labDesignPrompt').value=m[1];designFromPrompt(m[1]);return true;}
    if((m=cmd.match(/add (?:a |an )?(cube|sphere|cylinder|cone|torus|wedge|ring)/))){if(api.openLab)api.openLab();createPrimitive(m[1]);return true;}
    var commands=[[/\bundo\b/,undo],[/\bredo\b/,redo],[/\bduplicate\b/,duplicateModel],[/\bclear (?:the )?model\b/,clearModel],[/\bcenter (?:the )?model\b/,centerXY],[/(?:place|put).*(?:bed|plate)/,function(){snapToBed(true);}],[/(?:fit|resize).*a1/,autoFitA1],[/mirror.*x/,function(){mirrorAxis('x');}],[/mirror.*y/,function(){mirrorAxis('y');}],[/mirror.*z/,function(){mirrorAxis('z');}],[/rotate.*x.*90/,function(){rotatePreset('x');}],[/rotate.*y.*90/,function(){rotatePreset('y');}],[/rotate.*z.*90/,function(){rotatePreset('z');}],[/half (?:the )?size/,function(){scalePreset(50);}],[/double (?:the )?size/,function(){scalePreset(200);}],[/reset.*transform/,function(){resetTransform();}],[/isometric|iso view/,function(){setView('iso');}],[/top view/,function(){setView('top');}],[/front view/,function(){setView('front');}],[/right view/,function(){setView('right');}],[/toggle grid|grid (?:on|off)/,function(){showGrid=!showGrid;el('labGridBtn').textContent=showGrid?'GRID ON':'GRID OFF';}],[/wireframe/,function(){wireframe=!wireframe;el('labWireBtn').textContent=wireframe?'WIREFRAME':'SOLID';}],[/export.*stl/,downloadStl],[/snapshot|save.*preview/,snapshotPng],[/copy.*stats/,copyStats],[/fit check/,fitCheck],[/fine (?:print|layer|profile)/,function(){el('labLayer').value='.12';updateMetrics();}],[/standard (?:print|layer|profile)/,function(){el('labLayer').value='.20';updateMetrics();}],[/draft (?:print|layer|profile)/,function(){el('labLayer').value='.28';updateMetrics();}],[/print (?:review|this|model)|send.*bambu/,openReview]];
    for(var i=0;i<commands.length;i++)if(commands[i][0].test(cmd)){if(api.openLab)api.openLab();commands[i][1]();return true;}
    if((m=cmd.match(/(?:set )?infill(?: to)? (\d{1,3})/))){if(api.openLab)api.openLab();el('labInfill').value=Math.min(100,Number(m[1]));updateMetrics();return true;}return false;
  }
  function openReview(){
    if(!triangles.length){status('labPrintStatus','IMPORT A MODEL FIRST','bad');tone('bad');return;}
    updateMetrics();var m=lastMetrics;
    el('labReviewText').textContent='MODEL · '+safeName(fileName)+'\nSIZE · '+Math.round(m.dx)+' × '+Math.round(m.dy)+' × '+Math.round(m.dz)+' mm\nFILAMENT · ~'+m.grams.toFixed(1)+' g (pre-slice estimate)\nTIME · ~'+formatTime(m.minutes)+' (pre-slice estimate)\nPROFILE · '+m.layer.toFixed(2)+' mm · '+Math.round(m.infill)+'% infill\n\nBambu Studio will calculate the exact time/grams after slicing and show the final printer/plate review.';
    el('labReview').classList.add('open');tone('ready');
  }
  function setWorkflow(stage,kind){var ids=['labStageModel','labStageSend','labStageStudio','labStageReview'];ids.forEach(function(id,index){var node=el(id);if(!node)return;node.classList.remove('active','good','bad');if(index<stage)node.classList.add('good');else if(index===stage&&kind)node.classList.add(kind);});}
  function saveAndOpenBambu(background){
    if(!api.saveModel||!api.openInBambu){status('labPrintStatus','LOCAL JARVIS BRIDGE IS NOT READY','bad');tone('bad');return Promise.reject(new Error('Local JARVIS bridge is not ready.'));}
    updateMetrics();if(!lastMetrics||!lastMetrics.fits){fitCheck();return Promise.reject(new Error('Model must pass the selected printer fit check first.'));}
    setWorkflow(0,'active');status('labPrintStatus','VALIDATING MODEL + BUILD VOLUME…','');
    var buffer=exportStl();
    if(buffer.byteLength>10*1024*1024){setWorkflow(0,'bad');status('labPrintStatus','MODEL IS TOO LARGE FOR THE LOCAL HANDOFF (10 MB)','bad');tone('bad');return Promise.reject(new Error('Model is too large for the local handoff.'));}
    setWorkflow(1,'active');status('labPrintStatus','SENDING TRANSFORMED STL TO LOCAL BAMBU HANDOFF…','');
    return Promise.resolve(api.saveModel(safeName(fileName).replace(/\.[^.]+$/,'.stl'),bufferToBase64(buffer))).then(function(saved){
      if(!saved||!saved.model_id)throw new Error('JARVIS did not save the transformed model.');
      setWorkflow(2,'active');status('labPrintStatus',background?'STARTING BAMBU STUDIO IN THE BACKGROUND…':'OPENING BAMBU STUDIO FOR FINAL REVIEW…','');
      return api.openInBambu(saved.model_id,{background:!!background,preset:slicePreset()});
    }).then(function(result){
      setWorkflow(3,'active');status('labPrintStatus',(result&&result.message)||(background?'STAGED IN BAMBU STUDIO · FINAL REVIEW REQUIRED':'OPENED IN BAMBU STUDIO · FINAL REVIEW REQUIRED'),'good');tone('print');return result;
    }).catch(function(error){setWorkflow(2,'bad');status('labPrintStatus',error.message||'BAMBU STUDIO HANDOFF FAILED','bad');tone('bad');throw error;});
  }
  function sendToBambu(){
    var button=el('labReviewConfirm');button.disabled=true;button.textContent='SENDING…';
    saveAndOpenBambu(false).then(function(){el('labReview').classList.remove('open');}).catch(function(){}).finally(function(){button.disabled=false;button.textContent='OPEN BAMBU FINAL REVIEW';});
  }
  function prepareBambuBackground(){var button=el('labPrepareBambuBtn');button.disabled=true;button.textContent='PREPARING…';saveAndOpenBambu(true).catch(function(){}).finally(function(){button.disabled=false;button.textContent='PREPARE IN BACKGROUND';});}
  function checkBambuStudio(){if(!api.bambuCapabilities){status('labPrintStatus','LOCAL JARVIS BRIDGE IS NOT READY','bad');return;}status('labPrintStatus','CHECKING BAMBU STUDIO…','');Promise.resolve(api.bambuCapabilities()).then(function(result){var mode=result&&result.cli_available?'CLI + APP READY':result&&result.installed?'APP READY':'NOT FOUND';status('labPrintStatus','BAMBU STUDIO · '+mode+(result&&result.version?' · '+result.version:''),result&&result.installed?'good':'bad');tone(result&&result.installed?'ready':'bad');}).catch(function(error){status('labPrintStatus',error.message||'BAMBU STUDIO CHECK FAILED','bad');tone('bad');});}
  function studioInfo(){checkBambuStudio();}
  function loadFile(file){
    if(!file)return;if(file.size>12*1024*1024){status('labModelStatus','MODEL TOO LARGE FOR IN-APP LAB (12 MB)','bad');tone('bad');return;}
    status('labModelStatus','IMPORTING '+safeName(file.name).toUpperCase()+'…','');
    file.arrayBuffer().then(function(buffer){
      var parsed=parseModel(file,buffer);if(!parsed||!parsed.length)throw new Error('No triangles were found. Use STL or OBJ.');if(parsed.length>300000)throw new Error('Model has more than 300,000 triangles. Simplify it first.');
      pushHistory();triangles=parsed;fileName=safeName(file.name);var b=boundsOf(triangles);modelCenter={x:(b.min.x+b.max.x)/2,y:(b.min.y+b.max.y)/2,z:(b.min.z+b.max.z)/2};resetTransform();snapToBed(false);orbitYaw=-.55;orbitPitch=.38;orbitZoom=1;updateMetrics();status('labModelStatus','LOADED · '+fileName+' · '+triangles.length.toLocaleString()+' TRIANGLES','good');status('labPrintStatus','READY FOR PRINT REVIEW','good');tone('load');
    }).catch(function(error){triangles=[];fileName='';updateMetrics();status('labModelStatus','IMPORT FAILED · '+String(error.message||error),'bad');tone('bad');});
  }
  function manualScaleChanged(){
    var next=clamp(number('labScale',lastScalePercent),1,500,lastScalePercent);if(!triangles.length){lastScalePercent=next;updateMetrics();return;}
    var field=el('labScale');field.value=String(lastScalePercent);var anchor=placementAnchor();field.value=String(next);lastScalePercent=next;restorePlacementAnchor(anchor);updateMetrics();
  }
  function setupPanelResize(handleId,panelSelector,cssVar,storageKey,direction){
    var handle=el(handleId),panel=document.querySelector(panelSelector);if(!handle||!panel)return;
    try{var saved=Number(localStorage.getItem(storageKey));if(Number.isFinite(saved)&&saved>=PANEL_MIN)document.documentElement.style.setProperty(cssVar,Math.min(PANEL_MAX,saved)+'px');}catch(e){}
    handle.addEventListener('pointerdown',function(event){event.preventDefault();event.stopPropagation();var startX=event.clientX,startWidth=panel.getBoundingClientRect().width;panel.classList.add('resizing');try{handle.setPointerCapture(event.pointerId);}catch(e){}
      function move(e){var width=clamp(startWidth+(e.clientX-startX)*direction,PANEL_MIN,Math.min(PANEL_MAX,window.innerWidth*.46),startWidth);document.documentElement.style.setProperty(cssVar,Math.round(width)+'px');try{localStorage.setItem(storageKey,String(Math.round(width)));}catch(x){}}
      function done(){panel.classList.remove('resizing');handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',done);handle.removeEventListener('pointercancel',done);}
      handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',done);handle.addEventListener('pointercancel',done);
    });
  }
  function restoreLabPreferences(){
    try{
      var printer=localStorage.getItem('jarvis_lab_printer_v1'),material=localStorage.getItem('jarvis_lab_material_v1');
      if(printer&&PRINTERS[printer])el('labPrinter').value=printer;if(material&&MATERIALS[material])el('labMaterial').value=material;
    }catch(e){}
    updateFactoryLabels();
  }
  function wire(){
    canvas=el('labCanvas');ctx=canvas.getContext('2d');
    restoreLabPreferences();setupPanelResize('labLeftResize','.labPanel.left','--lab-left-width','jarvis_lab_left_width_v1',1);setupPanelResize('labRightResize','.labPanel.right','--lab-right-width','jarvis_lab_right_width_v1',-1);
    el('labImportBtn').addEventListener('click',function(){el('labFileInput').click();});el('labFileInput').addEventListener('change',function(){loadFile(this.files&&this.files[0]);this.value='';});
    ['labRotX','labRotY','labRotZ','labMoveX','labMoveY','labMoveZ','labLayer','labFirstLayer','labLineWidth','labInfill','labNozzle','labWallGenerator','labWalls','labTopLayers','labBottomLayers','labTopPattern','labBottomPattern','labInfillPattern','labSupports','labSupportStyle','labSupportAngle','labBrim','labBrimWidth','labSkirtLoops','labSeam','labIroning','labElephantFoot','labPlateType','labSequence','labTimelapse','labOuterSpeed','labInnerSpeed','labInfillSpeed','labFirstLayerSpeed','labTravelSpeed'].forEach(function(id){var node=el(id);if(!node)return;node.addEventListener('input',updateMetrics);node.addEventListener('change',updateMetrics);});
    el('labQualityPreset').addEventListener('change',applyQualityPreset);
    el('labScale').addEventListener('change',manualScaleChanged);el('labMaterial').addEventListener('change',function(){updateFactoryLabels();updateMetrics();});el('labPrinter').addEventListener('change',function(){updateFactoryLabels();updateMetrics();orbitZoom=1;tone('node');});
    document.querySelectorAll('[data-lab-primitive]').forEach(function(button){button.addEventListener('click',function(){createPrimitive(button.getAttribute('data-lab-primitive'));});});
    document.querySelectorAll('[data-lab-mirror]').forEach(function(button){button.addEventListener('click',function(){mirrorAxis(button.getAttribute('data-lab-mirror'));});});
    document.querySelectorAll('[data-lab-rotate]').forEach(function(button){button.addEventListener('click',function(){rotatePreset(button.getAttribute('data-lab-rotate'));});});
    document.querySelectorAll('[data-lab-scale]').forEach(function(button){button.addEventListener('click',function(){scalePreset(button.getAttribute('data-lab-scale'));});});
    document.querySelectorAll('[data-lab-view]').forEach(function(button){button.addEventListener('click',function(){setView(button.getAttribute('data-lab-view'));});});
    el('labDesignBtn').addEventListener('click',function(){designFromPrompt(el('labDesignPrompt').value);});el('labDesignPrompt').addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();designFromPrompt(this.value);}});
    el('labUndoBtn').addEventListener('click',undo);el('labRedoBtn').addEventListener('click',redo);el('labDuplicateBtn').addEventListener('click',duplicateModel);el('labClearBtn').addEventListener('click',clearModel);el('labCenterBtn').addEventListener('click',centerXY);el('labBedBtn').addEventListener('click',function(){snapToBed(true);});el('labAutoFitBtn').addEventListener('click',autoFitA1);
    el('labGridBtn').addEventListener('click',function(){showGrid=!showGrid;this.textContent=showGrid?'GRID ON':'GRID OFF';tone('node');});el('labWireBtn').addEventListener('click',function(){wireframe=!wireframe;this.textContent=wireframe?'WIREFRAME':'SOLID';tone('node');});el('labExportBtn').addEventListener('click',downloadStl);el('labSnapshotBtn').addEventListener('click',snapshotPng);el('labCopyStatsBtn').addEventListener('click',copyStats);el('labFitCheckBtn').addEventListener('click',fitCheck);el('labExportPresetBtn').addEventListener('click',exportPreset);el('labStudioInfoBtn').addEventListener('click',studioInfo);el('labPrepareBambuBtn').addEventListener('click',prepareBambuBackground);el('labBambuStatusBtn').addEventListener('click',checkBambuStudio);
    el('labResetTransform').addEventListener('click',function(){resetTransform();tone('ready');});el('labPrintBtn').addEventListener('click',openReview);el('labReviewCancel').addEventListener('click',function(){el('labReview').classList.remove('open');});el('labReviewConfirm').addEventListener('click',sendToBambu);
    canvas.addEventListener('pointerdown',function(e){dragging=true;lastX=e.clientX;lastY=e.clientY;canvas.setPointerCapture(e.pointerId);canvas.classList.add('dragging');});canvas.addEventListener('pointermove',function(e){if(!dragging)return;orbitYaw+=(e.clientX-lastX)*.008;orbitPitch=Math.max(-1.45,Math.min(1.45,orbitPitch+(e.clientY-lastY)*.008));lastX=e.clientX;lastY=e.clientY;});canvas.addEventListener('pointerup',function(e){dragging=false;canvas.classList.remove('dragging');try{canvas.releasePointerCapture(e.pointerId);}catch(x){}});canvas.addEventListener('pointercancel',function(){dragging=false;canvas.classList.remove('dragging');});canvas.addEventListener('wheel',function(e){e.preventDefault();orbitZoom=Math.max(.35,Math.min(3.5,orbitZoom*(e.deltaY>0?.9:1.1)));},{passive:false});
    if(!rafStarted){rafStarted=true;requestAnimationFrame(draw);}
  }
  function attach(next){api=next||{};}
  function enter(){document.body.classList.add('lab-mode');tone('ready');}
  function leave(){document.body.classList.remove('lab-mode');el('labReview').classList.remove('open');}
  window.JarvisLab={attach:attach,enter:enter,leave:leave,handleVoiceCommand:handleVoiceCommand,designFromPrompt:designFromPrompt,createPrimitive:createPrimitive};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',wire);else wire();
})();
