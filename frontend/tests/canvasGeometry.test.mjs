import test from 'node:test'
import assert from 'node:assert/strict'
import { canvasGraph, connectNodes, validPositions, layoutHistory, zoomCamera, fitCamera, graphBounds, CANVAS_NODE_W, CANVAS_NODE_H } from '../src/components/tree/canvasGeometry.js'

const stages = ['new','demo','won','lost'].map((key,i) => ({ key, name: key, kind: key === 'won' || key === 'lost' ? key : 'open', count: 20-i*4, percent: 100-i*20, lead_ids: [1,2] }))
const links = [{ from_key: 'new', to_key: 'demo', count: 16, percent: 80, kind: 'normal' }, { from_key: 'demo', to_key: 'won', count: 12, percent: 75, kind: 'won' }, { from_key: 'new', to_key: 'lost', count: 4, percent: 20, kind: 'lost' }]
test('Dragging a node keeps all lead data and reroutes only its attached links', () => {
 const original = canvasGraph(stages, links)
 const moved = canvasGraph(stages, links, { demo: { x: 50, y: 650 } })
 assert.equal(moved.nodes.find(n => n.key === 'demo').y,650)
 assert.deepEqual(moved.nodes.map(n=>[n.key,n.count,n.lead_ids]),original.nodes.map(n=>[n.key,n.count,n.lead_ids]))
 for(let i=0;i<links.length;i++) {
  const same=links[i].from_key!=='demo'&&links[i].to_key!=='demo'
  assert.equal(moved.links[i].d===original.links[i].d,same)
  assert.equal(moved.links[i].count,original.links[i].count)
 }
})
test('Directional connections anchor at the correct card boundaries, including loops', () => {
 const a={key:'a',x:0,y:0}
 assert.ok(connectNodes(a,{key:'b',x:700,y:0}).d.startsWith(`M ${CANVAS_NODE_W} ${CANVAS_NODE_H/2}`))
 assert.ok(connectNodes(a,{key:'b',x:0,y:700}).d.startsWith(`M ${CANVAS_NODE_W/2} ${CANVAS_NODE_H}`))
 for(const b of [{key:'b',x:-700,y:0},{key:'b',x:0,y:-700},a])assert.doesNotMatch(connectNodes(a,b).d,/NaN|Infinity/)
})
test('Cursor-centred zoom retains its world point and respects limits', () => {
 const c={zoom:.8,x:30,y:-50},p={x:200,y:180},z=zoomCamera(c,1.25,p)
 assert.equal((p.x-z.x)/z.zoom,(p.x-c.x)/c.zoom)
 assert.equal((p.y-z.y)/z.zoom,(p.y-c.y)/c.zoom)
 assert.equal(zoomCamera(c,999,p).zoom,2.5)
 assert.equal(zoomCamera(c,.001,p).zoom,.2)
 const fit=fitCamera(graphBounds(canvasGraph(stages,links)),1200,600)
 assert.ok(fit.zoom<=1&&fit.zoom>=.2)
})
test('Undo, redo, reset, branch edits and bounded history restore exact positions', () => {
 let s={entries:[{}],index:0}
 const move=(key,x,y)=>{s=layoutHistory(s,{type:'move',key,position:{x,y}})}
 move('demo',10,20);move('won',300,400)
 s=layoutHistory(s,{type:'undo'});assert.deepEqual(s.entries[s.index],{demo:{x:10,y:20}})
 s=layoutHistory(s,{type:'redo'});assert.equal(s.entries[s.index].won.x,300)
 s=layoutHistory(s,{type:'reset'});assert.deepEqual(s.entries[s.index],{})
 s=layoutHistory(s,{type:'undo'});assert.equal(s.entries[s.index].won.y,400)
 move('lost',-10,-20);assert.equal(s.index,s.entries.length-1)
 assert.equal(layoutHistory(s,{type:'redo'}).index,s.index)
 for(let i=0;i<60;i++)move('demo',i,i)
 assert.equal(s.entries.length,40)
})
test('Corrupt browser layouts are rejected and no-op changes do not add history', () => {
 assert.deepEqual(validPositions(null),{})
 assert.deepEqual(validPositions({a:{x:1,y:2,extra:true},b:{x:NaN,y:2},c:{x:100001,y:0},d:{x:'10',y:5}}),{a:{x:1,y:2}})
 const state={entries:[{a:{x:1,y:2}}],index:0}
 assert.equal(layoutHistory(state,{type:'move',key:'a',position:{x:1,y:2}}),state)
})
