export const THEME_KEY = 'minar-theme';
export const ACCENT_KEY = 'space-accent';
export const ACCENTS = [
  {id:'indigo',name:'Neon Indigo',color:'#7367f0'},
  {id:'emerald',name:'Cyber Emerald',color:'#12856d'},
  {id:'amber',name:'Solar Amber',color:'#a66a08'},
  {id:'obsidian',name:'Deep Obsidian',color:'#526174'},
  {id:'blue',name:'Ocean Blue',color:'#2973d5'},
  {id:'rose',name:'Nova Rose',color:'#bd436b'},
  {id:'violet',name:'Orbit Violet',color:'#9251d1'},
  {id:'cyan',name:'Arctic Cyan',color:'#087e90'},
  {id:'orange',name:'Sunset Orange',color:'#bb5927'},
  {id:'lime',name:'Quantum Lime',color:'#5b7d17'},
];

export function readTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'day' || saved === 'night') return saved;
  } catch {}
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'night' : 'day';
}

export function saveTheme(theme) {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {}
}

// layout.tsx <head> ichida: birinchi chizishdan oldin rejimni qo'yadi (yorug' "miltillash" bo'lmasin)
export function readAccent(){try{const value=localStorage.getItem(ACCENT_KEY);return ACCENTS.some(a=>a.id===value)?value:'indigo'}catch{return 'indigo'}}
export function saveAccent(value){if(!ACCENTS.some(a=>a.id===value))return;document.documentElement.dataset.accent=value;try{localStorage.setItem(ACCENT_KEY,value)}catch{}}
export const themeBootScript = `(()=>{let t='day',a='indigo',l='uz';try{t=matchMedia('(prefers-color-scheme: dark)').matches?'night':'day';const s=localStorage.getItem('${THEME_KEY}');if(s==='day'||s==='night')t=s;a=localStorage.getItem('${ACCENT_KEY}')||a;l=localStorage.getItem('space-locale')||l}catch{}const r=document.documentElement;r.dataset.theme=t;r.dataset.accent=${JSON.stringify(ACCENTS.map(a=>a.id))}.includes(a)?a:'indigo';r.lang=l==='ru'?'ru':'uz';r.style.colorScheme=t==='night'?'dark':'light'})()`;
