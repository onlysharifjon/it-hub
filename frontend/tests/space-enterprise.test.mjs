import assert from 'node:assert/strict';
import test,{after} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {rm} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('..',import.meta.url));
const vite=await createServer({configFile:false,root,cacheDir:'/tmp/space-admin-vite-'+process.pid,optimizeDeps:{noDiscovery:true,include:[]},appType:'custom',esbuild:{jsx:'automatic'},server:{middlewareMode:true,hmr:false,ws:false}});
globalThis.localStorage={getItem:()=>null,setItem(){}};
after(async()=>{await vite.close();await rm('/tmp/space-admin-vite-'+process.pid,{recursive:true,force:true});delete globalThis.window;delete globalThis.localStorage});
const {default:Accounts}=await vite.ssrLoadModule('/src/components/MinarAccounts.jsx');
const {default:Workflows}=await vite.ssrLoadModule('/src/components/SpaceWorkflows.jsx');
const i18n=await vite.ssrLoadModule('/src/space-design/i18n.js');
globalThis.window={matchMedia:()=>({matches:false})};
test('teacher retains group credential creation while admin-only controls stay hidden',()=>{
 const html=renderToStaticMarkup(React.createElement(Accounts,{currentUser:{role:'teacher'}}));
 assert.match(html,/Guruh bo&#x27;yicha ochish/);assert.doesNotMatch(html,/>Hisob ochish</);assert.doesNotMatch(html,/>QR kartalar</);assert.match(html,/Barcha guruhlar/);assert.match(html,/Barcha holatlar/);
});
test('administrator retains single, bulk and QR access controls',()=>{
 const html=renderToStaticMarkup(React.createElement(Accounts,{currentUser:{role:'admin'}}));
 assert.match(html,/>Hisob ochish</);assert.match(html,/>QR kartalar</);assert.match(html,/Guruh bo&#x27;yicha ochish/);
});
test('Russian administration translates account actions and filter labels',()=>{
 i18n.setLocale('ru');const html=renderToStaticMarkup(React.createElement(Accounts,{currentUser:{role:'admin'}}));
 assert.match(html,/Создать аккаунт/);assert.match(html,/Создать для группы/);assert.match(html,/Все группы/);assert.match(html,/Поиск по имени/);i18n.setLocale('uz');
});
test('teacher teaching workspace preserves review access and excludes content and group administration',()=>{
 const html=renderToStaticMarkup(React.createElement(Workflows,{currentUser:{role:'teacher'}}));
 assert.match(html,/Uy vazifalari/);assert.match(html,/Ustozga savollar/);assert.doesNotMatch(html,/>Dars materiallari</);assert.doesNotMatch(html,/>Guruhlar va nazorat</);
});
