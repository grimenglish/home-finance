const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('login bridge rejects foreign messages and returns token only to its own parent',()=>{
  const messages=[],handlers={},status={},scripts=[];
  let initialized=null,rendered=0;
  const parent={postMessage:(value,origin)=>messages.push({value,origin})};
  const google={accounts:{id:{initialize:args=>initialized=args,renderButton:()=>rendered++}}};
  const ctx={location:{origin:'https://finance.streamlit.app'},document:{getElementById:id=>status,createElement:()=>({}),head:{appendChild:s=>scripts.push(s)}},window:{parent,addEventListener:(n,f)=>handlers[n]=f,google},google};
  vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../google_login_component/login.js'),'utf8'),ctx);
  const data={type:'streamlit:render',args:{client_id:'id',nonce:'own-nonce'}};
  handlers.message({source:parent,origin:'https://evil.test',data});assert.equal(rendered,0);
  handlers.message({source:{},origin:ctx.location.origin,data});assert.equal(rendered,0);
  handlers.message({source:parent,origin:ctx.location.origin,data});assert.equal(rendered,1);assert.equal(initialized.nonce,'own-nonce');
  initialized.callback({credential:'mock-token'});
  const value=messages.find(x=>x.value.type==='streamlit:setComponentValue');
  assert.equal(value.origin,ctx.location.origin);assert.equal(value.value.dataType,'json');assert.equal(value.value.value.credential,'mock-token');
  assert.ok(messages.some(x=>x.value.type==='streamlit:componentReady'&&x.value.apiVersion===1));
});
