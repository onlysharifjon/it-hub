'use client';
import {useSyncExternalStore} from 'react';
import core from './locales/ru.js';
import legacy from './locales/ru-legacy.js';
import admin from './locales/ru-admin.js';
const ru={...legacy,...core,...admin};
export const LOCALE_KEY='space-locale';
const listeners=new Set();
let current='uz';
let initialized=false;
export function getLocale(){return current}
export function initializeLocale(){
  if(initialized || typeof document==='undefined')return;
  initialized=true;
  try{current=localStorage.getItem(LOCALE_KEY)==='ru'?'ru':'uz'}catch{current=document.documentElement.lang==='ru'?'ru':'uz'}
  document.documentElement.lang=current;
  for(const fn of listeners)fn();
}
export function setLocale(locale){
  if(!['uz','ru'].includes(locale))return;
  current=locale;
  if(typeof document!=='undefined')document.documentElement.lang=locale;
  try{localStorage.setItem(LOCALE_KEY,locale)}catch{}
  for(const fn of listeners)fn();
}
const subscribe=fn=>{listeners.add(fn);return()=>listeners.delete(fn)};
export function t(text,values={},locale=current){
  const translated=locale==='ru'?(ru[text]??text):text;
  return typeof translated==='string'?translated.replace(/\{(\w+)\}/g,(m,key)=>Object.hasOwn(values,key)?String(values[key]):m):translated;
}
export function localeTag(){return current==='ru'?'ru-RU':'uz-UZ'}
export function useI18n(){const locale=useSyncExternalStore(subscribe,getLocale,()=> 'uz');return {locale,t:(text,values)=>t(text,values,locale),setLocale,localeTag:locale==='ru'?'ru-RU':'uz-UZ'}}
