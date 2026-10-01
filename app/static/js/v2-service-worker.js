const CACHE="nasora-v2-terrain-v2";
const DB="nasora-offline";
const STORE="requests";
const ASSETS=["/static/css/styles.css","/static/css/nasora-phone-responsive.css","/static/js/nasora-phone-responsive.js"];

function openDb(){return new Promise((resolve,reject)=>{const r=indexedDB.open(DB,1);r.onupgradeneeded=()=>r.result.createObjectStore(STORE,{autoIncrement:true});r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});}
async function queueRequest(request){const body=await request.clone().arrayBuffer();const db=await openDb();await new Promise((resolve,reject)=>{const tx=db.transaction(STORE,"readwrite");tx.objectStore(STORE).add({url:request.url,method:request.method,headers:[...request.headers.entries()],body});tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});}
async function flushQueue(){const db=await openDb();const items=await new Promise((resolve,reject)=>{const tx=db.transaction(STORE,"readonly");const req=tx.objectStore(STORE).getAll();req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});for(const item of items){try{const response=await fetch(new Request(item.url,{method:item.method,headers:Object.fromEntries(item.headers),body:item.body,credentials:"include"}));if(response.ok){await new Promise((resolve,reject)=>{const tx=db.transaction(STORE,"readwrite");const store=tx.objectStore(STORE);store.delete(item.__key);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});}}catch(_){break;}}}
self.addEventListener("install",event=>event.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener("activate",event=>event.waitUntil(self.clients.claim()));
self.addEventListener("sync",event=>{if(event.tag==="nasora-v2-sync")event.waitUntil(flushQueue());});
self.addEventListener("fetch",event=>{
  const req=event.request;
  if(req.method==="POST" && new URL(req.url).pathname.startsWith("/v2/")){
    event.respondWith(fetch(req.clone()).catch(async()=>{await queueRequest(req);if("sync" in self.registration){try{await self.registration.sync.register("nasora-v2-sync");}catch(_){}}return new Response(JSON.stringify({queued:true}),{status:202,headers:{"Content-Type":"application/json"}})}));
    return;
  }
  if(req.method!=="GET") return;
  event.respondWith(caches.match(req).then(cached=>cached||fetch(req).then(response=>{const copy=response.clone();caches.open(CACHE).then(c=>c.put(req,copy));return response;}).catch(()=>cached)));
});