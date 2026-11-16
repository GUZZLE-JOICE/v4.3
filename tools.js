(function(){
  'use strict';

  var api=null,catalog=null,activeCategory='ALL',selected=null,busy=false,lastOutput='';

  function el(id){return document.getElementById(id);}
  function tone(kind){if(window.JarvisFX)window.JarvisFX.tone(kind||'click');}
  function safeMessage(error){return String(error&&error.message||error||'The local tool could not run.');}
  function categoryShort(name){return String(name||'').slice(0,3).toUpperCase();}

  function loadCatalog(force){
    if(catalog&&!force)return Promise.resolve(catalog);
    if(!api||typeof api.catalog!=='function')return Promise.reject(new Error('Local tool bridge is not attached.'));
    el('toolsSideStatus').textContent='CHECKING LOCAL BRIDGE…';
    return api.catalog().then(function(data){
      if(!data||!Array.isArray(data.tools))throw new Error('The local tool catalog was invalid.');
      catalog=data;
      el('toolsSideStatus').textContent=data.count+' TOOLS READY';
      renderCategories();renderTools();
      if(!selected&&data.tools.length)selectTool(data.tools[0].name,false);
      return data;
    }).catch(function(error){
      el('toolsSideStatus').textContent='TOOL BRIDGE OFFLINE';
      el('toolsGrid').textContent=safeMessage(error);
      throw error;
    });
  }

  function categoryCounts(){
    var counts={ALL:catalog?catalog.tools.length:0};
    (catalog&&catalog.tools||[]).forEach(function(tool){counts[tool.category]=(counts[tool.category]||0)+1;});
    return counts;
  }

  function renderCategories(){
    var list=el('toolsCategoryList'),counts=categoryCounts();list.innerHTML='';
    ['ALL'].concat(catalog.categories||[]).forEach(function(name){
      var button=document.createElement('button');button.type='button';button.className='toolsCategoryBtn'+(name===activeCategory?' active':'');button.dataset.short=categoryShort(name);
      var label=document.createElement('b');label.textContent=name;var count=document.createElement('span');count.textContent=String(counts[name]||0);button.appendChild(label);button.appendChild(count);
      button.addEventListener('click',function(){activeCategory=name;renderCategories();renderTools();tone('mode');});list.appendChild(button);
    });
  }

  function visibleTools(){
    var query=String(el('toolsSearch').value||'').trim().toLowerCase();
    return (catalog&&catalog.tools||[]).filter(function(tool){
      if(activeCategory!=='ALL'&&tool.category!==activeCategory)return false;
      if(!query)return true;
      return [tool.name,tool.label,tool.category,tool.description].join(' ').toLowerCase().indexOf(query)>=0;
    });
  }

  function renderTools(){
    var grid=el('toolsGrid'),tools=visibleTools();grid.innerHTML='';el('toolsCount').textContent=tools.length+' / '+(catalog?catalog.count:0)+' TOOLS';
    if(!tools.length){var empty=document.createElement('div');empty.className='toolsInspectorEmpty';empty.textContent='NO LOCAL TOOLS MATCH THAT SEARCH';grid.appendChild(empty);return;}
    tools.forEach(function(tool){
      var card=document.createElement('button');card.type='button';card.className='toolCard'+(selected&&selected.name===tool.name?' active':'');card.dataset.tool=tool.name;
      var cat=document.createElement('div');cat.className='toolCardCategory';cat.textContent=tool.category;
      var title=document.createElement('div');title.className='toolCardTitle';title.textContent=tool.label;
      var description=document.createElement('div');description.className='toolCardDescription';description.textContent=tool.description;
      var flag=document.createElement('div');flag.className='toolCardFlag';flag.textContent=tool.writes_files?'LOCAL OUTPUT FOLDER':'READ-ONLY / IN-MEMORY';
      card.appendChild(cat);card.appendChild(title);card.appendChild(description);card.appendChild(flag);
      card.addEventListener('click',function(){selectTool(tool.name,true);});grid.appendChild(card);
    });
  }

  function makeInput(field){
    var wrap=document.createElement('label');wrap.className='toolField';wrap.dataset.field=field.name;
    if(field.type==='checkbox'){
      wrap.className='toolCheckbox toolField';var checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.name=field.name;checkbox.checked=field.value===true||field.value==='true';var text=document.createElement('span');text.textContent=field.label;wrap.appendChild(checkbox);wrap.appendChild(text);return wrap;
    }
    var label=document.createElement('span');label.className='toolFieldLabel';label.textContent=field.label;wrap.appendChild(label);
    var input;
    if(field.type==='textarea'){input=document.createElement('textarea');}
    else if(field.type==='select'){
      input=document.createElement('select');(field.options||[]).forEach(function(option){var choice=document.createElement('option');choice.value=String(option);choice.textContent=String(option).replace(/_/g,' ').toUpperCase();input.appendChild(choice);});
    }else{input=document.createElement('input');input.type=field.type==='number'?'number':'text';}
    input.className='toolInput';input.name=field.name;if(field.placeholder)input.placeholder=field.placeholder;if(field.value!==undefined&&field.value!==null)input.value=String(field.value);wrap.appendChild(input);return wrap;
  }

  function selectTool(name,focus){
    if(!catalog)return;
    var tool=catalog.tools.find(function(item){return item.name===name;});if(!tool)return;selected=tool;
    el('toolsInspectorEmpty').style.display='none';el('toolsInspectorBody').classList.add('open');el('toolsInspector').classList.add('open-mobile');
    el('toolsToolCategory').textContent=tool.category+' · '+(tool.writes_files?'SAVES LOCALLY':'NO FILE CHANGES');el('toolsToolTitle').textContent=tool.label;el('toolsToolDescription').textContent=tool.description;
    var form=el('toolsForm');form.innerHTML='';(tool.inputs||[]).forEach(function(field){form.appendChild(makeInput(field));});
    el('toolsOutput').classList.remove('open');el('toolsOutputText').classList.remove('toolsError');lastOutput='';renderTools();tone('node');
    if(focus){var first=form.querySelector('input:not([type="checkbox"]),textarea,select');if(first)setTimeout(function(){first.focus();},0);}
  }

  function argumentsFromForm(){
    var values={};if(!selected)return values;
    (selected.inputs||[]).forEach(function(field){var input=el('toolsForm').querySelector('[name="'+CSS.escape(field.name)+'"]');if(!input)return;values[field.name]=field.type==='checkbox'?!!input.checked:input.value;});return values;
  }

  function showOutput(result,error){
    var output=el('toolsOutput'),text=el('toolsOutputText');output.classList.add('open');text.classList.toggle('toolsError',!!error);
    el('toolsOutputStatus').textContent=error?'TOOL ERROR':('READY · '+String(result&&result.elapsed_ms||0)+' MS');
    if(error)lastOutput=safeMessage(error);
    else{
      var payload=result&&result.result!==undefined?result.result:result;
      lastOutput=typeof payload==='string'?payload:JSON.stringify(payload,null,2);
    }
    text.textContent=lastOutput;
    if(api&&api.caption)api.caption(error?lastOutput:(result.result&&result.result.summary)||selected.label+' finished.');tone(error?'error':'success');
  }

  function runSelected(){
    if(!selected||busy||!api)return;busy=true;var button=el('toolsRunBtn');button.disabled=true;button.textContent='RUNNING LOCALLY…';
    api.run(selected.name,argumentsFromForm()).then(function(result){showOutput(result,null);}).catch(function(error){showOutput(null,error);}).finally(function(){busy=false;button.disabled=false;button.textContent='RUN TOOL';});
  }

  function command(utterance){
    if(!api||typeof api.command!=='function')return Promise.resolve({matched:false});
    return api.command(utterance).then(function(result){
      if(result&&result.open_tools){if(api.setMode)api.setMode('tools');return result;}
      if(result&&result.matched){if(api.setMode)api.setMode('tools');var toolName=result.tool;if(toolName&&catalog)selectTool(toolName,false);showOutput(result,null);if(api.speak)api.speak((result.result&&result.result.summary)||result.message||'Local tool finished.');}
      return result;
    });
  }

  function enter(){loadCatalog(false).catch(function(){});}
  function leave(){el('toolsInspector').classList.remove('open-mobile');}
  function attach(value){
    api=value||{};
    el('toolsSearch').addEventListener('input',renderTools);
    el('toolsClearSearch').addEventListener('click',function(){el('toolsSearch').value='';activeCategory='ALL';renderCategories();renderTools();});
    el('toolsRunBtn').addEventListener('click',runSelected);
    el('toolsForm').addEventListener('submit',function(event){event.preventDefault();runSelected();});
    el('toolsCopyBtn').addEventListener('click',function(){if(!lastOutput)return;navigator.clipboard.writeText(lastOutput).then(function(){el('toolsOutputStatus').textContent='COPIED';tone('confirm');}).catch(function(){el('toolsOutputStatus').textContent='SELECT RESULT AND COPY';});});
    loadCatalog(false).catch(function(){});
  }

  window.JarvisTools={attach:attach,enter:enter,leave:leave,command:command,openTool:function(name){loadCatalog(false).then(function(){selectTool(name,true);});},catalog:function(){return catalog;}};
})();
