// Isolated rendering fixture: no API, worker, model or user service.
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import WorldScene from '../../src/v2/WorldScene';
import Graph from '../../src/v2/Graph';
import '../../src/v2/style.css';
const protocol = { label: '录制验收 · 独立观察场景', sensors: [], geometries: [
  { id:'floor', shape:'plane', size:[1,1,.01], rgba:[.75,.85,.78,1] },
  { id:'body', body_id:'body', shape:'capsule', size:[.12,.16,0], rgba:[.15,.55,.4,1] },
] };
function App() {
  const [time,setTime]=useState(0);
  useEffect(()=>{const id=setInterval(()=>setTime(t=>t+.1),100);return()=>clearInterval(id);},[]);
  const observation={ physical_time_us:Math.round(time*1e6),geometries:[
    {id:'floor',position:[0,0,0],rotation_matrix:[1,0,0,0,1,0,0,0,1]},
    {id:'body',position:[.3*Math.sin(time),0,.2],rotation_matrix:[1,0,0,0,1,0,0,0,1]},
  ]};
  const graph=new URLSearchParams(location.search).has('graph');
  return <main style={{maxWidth:1000,margin:'16px auto',padding:12}}><h1>截图与录屏验收</h1>{graph
    ? <Graph project="fixture" run="fixture" polling={false} endpoint="/e2e/fixtures/capture-graph.json"/>
    : <WorldScene protocol={protocol} observation={observation}/>}</main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
