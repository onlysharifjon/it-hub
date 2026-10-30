import {useEffect,useState} from 'react'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {faPalette,faLanguage,faArrowUpRightFromSquare,faSun,faMoon} from '@fortawesome/free-solid-svg-icons'
import {useI18n,initializeLocale} from './i18n'
import {ACCENTS} from './presets'
import {useTheme,setTheme} from '../theme'
import './space-enterprise.css'
export default function SpaceControls(){
 const mode=useTheme();
 const {locale,t,setLocale}=useI18n(),[accent,setAccent]=useState(()=>{try{return localStorage.getItem('space-accent')||'indigo'}catch{return 'indigo'}})
 useEffect(()=>{initializeLocale();document.documentElement.dataset.spaceAccent=ACCENTS.some(a=>a.id===accent)?accent:'indigo'},[accent])
 return <div className="space-control-bar"><span className="space-control-brand">SPACE <small>COMMAND CENTER</small></span><div><label><FontAwesomeIcon icon={faLanguage}/><span className="sr-only">{t('Interfeys tili')}</span><select value={locale} onChange={e=>setLocale(e.target.value)}><option value="uz">O‘zbekcha</option><option value="ru">Русский</option></select></label><label><FontAwesomeIcon icon={faPalette}/><span className="sr-only">{t('Rang mavzusi')}</span><select value={accent} onChange={e=>{setAccent(e.target.value);try{localStorage.setItem('space-accent',e.target.value)}catch{}}}>{ACCENTS.map(a=><option value={a.id} key={a.id}>{a.name}</option>)}</select></label><button className="btn-icon" aria-label={t(mode==='dark'?'Kunduzgi rejimga o‘tish':'Tungi rejimga o‘tish')} onClick={()=>setTheme(mode==='dark'?'light':'dark')}><FontAwesomeIcon icon={mode==='dark'?faSun:faMoon}/></button><a href="https://space.minaracademy.uz" target="_blank" rel="noopener noreferrer" aria-label="SPACE student portal"><FontAwesomeIcon icon={faArrowUpRightFromSquare}/></a></div></div>
}
