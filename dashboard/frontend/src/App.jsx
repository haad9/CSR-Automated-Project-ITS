import React, { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import { API, STATE_META } from './lib/constants'
import Overview     from './pages/Overview'
import Certificates from './pages/Certificates'
import Approvals    from './pages/Approvals'
import ActivityLog  from './pages/ActivityLog'
import Exceptions   from './pages/Exceptions'
import Reports      from './pages/Reports'
import DemoPage     from './pages/DemoPage'

import {
  LayoutDashboard, Shield, CheckSquare, Activity,
  AlertTriangle, FileText, Zap, Wifi, WifiOff
} from 'lucide-react'

const NAV = [
  { id: 'overview',     label: 'Overview',      icon: LayoutDashboard, accent: '#3b82f6' },
  { id: 'certificates', label: 'Certificates',  icon: Shield,          accent: '#10b981' },
  { id: 'approvals',    label: 'Approvals',     icon: CheckSquare,     accent: '#f59e0b', badge: 'pendingApprovals' },
  { id: 'activity',     label: 'Activity',      icon: Activity,        accent: '#8b5cf6' },
  { id: 'exceptions',   label: 'Incidents',     icon: AlertTriangle,   accent: '#ef4444', badge: 'exceptionCount' },
  { id: 'reports',      label: 'Reports',       icon: FileText,        accent: '#a855f7' },
  { id: 'demo',         label: '⚡ Demo Mode',  icon: Zap,             accent: '#f59e0b', highlight: true },
]

export default function App() {
  const [page,      setPage]      = useState('overview')
  const [certs,     setCerts]     = useState([])
  const [agencies,  setAgencies]  = useState([])
  const [connected, setConnected] = useState(true)
  const [loading,   setLoading]   = useState(true)
  const [pulse,     setPulse]     = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const [c, a] = await Promise.all([
        axios.get(`${API}/certs`),
        axios.get(`${API}/agencies`),
      ])
      setCerts(c.data.certs || [])
      setAgencies(a.data.agencies || [])
      setConnected(true)
      setPulse(p => !p)
    } catch {
      setConnected(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const t = setInterval(fetchData, 5000)
    return () => clearInterval(t)
  }, [fetchData])

  const stateCounts     = certs.reduce((a, c) => ({ ...a, [c.state]: (a[c.state] || 0) + 1 }), {})
  const pendingApprovals = certs.filter(c => c.governance_task_token && !c.governance_approved).length
  const exceptionCount  = stateCounts['Exception'] || 0
  const inProgress      = certs.filter(c => !['Active','Exception','Renewal Closed'].includes(c.state)).length
  const totalRenewals   = certs.reduce((s, c) => s + (parseInt(c.renewals_count) || 0), 0)
  const timeSavedHours  = totalRenewals * 2
  const agencyMap       = agencies.reduce((m, a) => ({ ...m, [a.agency_id]: a }), {})

  const currentAccent = NAV.find(n => n.id === page)?.accent || '#3b82f6'
  const shared = { certs, agencies, agencyMap, stateCounts, fetchData, loading, totalRenewals }

  return (
    <div style={{ display:'flex', height:'100vh', overflow:'hidden', background:'#050508', fontFamily:'Inter,system-ui,sans-serif', color:'#e2e8f0' }}>

      {/* ── Sidebar ─────────────────────────────── */}
      <aside style={{ width:220, flexShrink:0, display:'flex', flexDirection:'column', background:'#0a0a12', borderRight:'1px solid #1a1a2e' }}>

        {/* Logo */}
        <div style={{ padding:'20px 16px 12px', borderBottom:'1px solid #1a1a2e' }}>
          <div style={{ display:'flex', alignItems:'center', gap:10 }}>
            <div style={{ width:36, height:36, borderRadius:10, background:`linear-gradient(135deg, #1e40af, #3b82f6)`, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
              <Shield size={18} color="white" />
            </div>
            <div>
              <div style={{ fontWeight:700, fontSize:13, color:'#fff', lineHeight:1.2 }}>Mississippi ITS</div>
              <div style={{ fontSize:11, color:'#4b5563', lineHeight:1.2 }}>Cert Lifecycle System</div>
            </div>
          </div>

          {/* Live dot */}
          <div style={{ marginTop:10, display:'flex', alignItems:'center', gap:6, padding:'6px 10px', borderRadius:8, background: connected ? 'rgba(74,222,128,0.06)' : 'rgba(248,113,113,0.06)', border:`1px solid ${connected ? 'rgba(74,222,128,0.15)' : 'rgba(248,113,113,0.15)'}` }}>
            {connected
              ? <><div style={{ width:7, height:7, borderRadius:'50%', background:'#4ade80', boxShadow:'0 0 6px #4ade80', animation:'pulse 2s infinite' }} /><span style={{ fontSize:11, color:'#4ade80' }}>Live — 5s refresh</span></>
              : <><WifiOff size={11} color="#f87171" /><span style={{ fontSize:11, color:'#f87171' }}>Offline</span></>
            }
          </div>
        </div>

        {/* Nav items */}
        <nav style={{ flex:1, padding:'10px 8px', display:'flex', flexDirection:'column', gap:2 }}>
          {NAV.map(item => {
            const Icon    = item.icon
            const active  = page === item.id
            const badgeN  = item.badge === 'pendingApprovals' ? pendingApprovals : item.badge === 'exceptionCount' ? exceptionCount : 0
            return (
              <button key={item.id} onClick={() => setPage(item.id)}
                style={{
                  display:'flex', alignItems:'center', gap:10, padding:'9px 12px', borderRadius:10,
                  border:`1px solid ${active ? item.accent+'44' : 'transparent'}`,
                  background: active ? item.accent+'18' : item.highlight ? '#f59e0b0a' : 'transparent',
                  color: active ? item.accent : item.highlight ? '#fbbf24' : '#6b7280',
                  cursor:'pointer', width:'100%', textAlign:'left', transition:'all 0.15s',
                }}
                onMouseEnter={e => { if(!active) e.currentTarget.style.background = '#ffffff08'; e.currentTarget.style.color = '#e2e8f0' }}
                onMouseLeave={e => { if(!active) { e.currentTarget.style.background = item.highlight ? '#f59e0b0a' : 'transparent'; e.currentTarget.style.color = active ? item.accent : item.highlight ? '#fbbf24' : '#6b7280' }}}
              >
                <Icon size={15} />
                <span style={{ fontSize:13, fontWeight: active ? 600 : 400, flex:1 }}>{item.label}</span>
                {badgeN > 0 && (
                  <span style={{ background:'#ef4444', color:'#fff', fontSize:10, fontWeight:700, borderRadius:99, padding:'1px 6px', minWidth:18, textAlign:'center' }}>
                    {badgeN}
                  </span>
                )}
                {active && <div style={{ width:3, height:16, borderRadius:99, background:item.accent, marginLeft:'auto' }} />}
              </button>
            )
          })}
        </nav>

        {/* Stats footer */}
        <div style={{ padding:'12px 12px 16px', borderTop:'1px solid #1a1a2e' }}>
          <div style={{ textAlign:'center', marginBottom:10 }}>
            <div style={{ fontSize:26, fontWeight:800, background:'linear-gradient(135deg,#fbbf24,#f59e0b)', WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent' }}>
              {timeSavedHours}h
            </div>
            <div style={{ fontSize:11, color:'#4b5563' }}>saved vs manual</div>
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:6, textAlign:'center' }}>
            {[
              { v: certs.length,    l:'Certs',  c:'#60a5fa' },
              { v: inProgress,      l:'Active', c:'#fbbf24' },
              { v: exceptionCount,  l:'Issues', c:'#f87171' },
            ].map(s => (
              <div key={s.l} style={{ background:'#111118', borderRadius:8, padding:'6px 4px' }}>
                <div style={{ fontSize:16, fontWeight:700, color:s.c }}>{s.v}</div>
                <div style={{ fontSize:10, color:'#374151' }}>{s.l}</div>
              </div>
            ))}
          </div>
          {pendingApprovals > 0 && (
            <button onClick={() => setPage('approvals')} style={{ marginTop:8, width:'100%', padding:'8px', borderRadius:8, background:'rgba(245,158,11,0.1)', border:'1px solid rgba(245,158,11,0.3)', color:'#fbbf24', fontSize:12, fontWeight:600, cursor:'pointer' }}>
              ⏳ {pendingApprovals} approval{pendingApprovals > 1 ? 's' : ''} waiting
            </button>
          )}
        </div>
      </aside>

      {/* ── Main ──────────────────────────────────── */}
      <div style={{ flex:1, display:'flex', flexDirection:'column', overflow:'hidden' }}>

        {/* Top bar */}
        <header style={{ padding:'12px 24px', borderBottom:'1px solid #1a1a2e', background:'#080810', display:'flex', alignItems:'center', justifyContent:'space-between', flexShrink:0 }}>
          <div>
            <div style={{ height:2, width:32, borderRadius:99, background:currentAccent, marginBottom:6 }} />
            <h1 style={{ fontWeight:700, fontSize:18, color:'#fff', margin:0 }}>
              {NAV.find(n => n.id === page)?.label.replace('⚡ ', '')}
            </h1>
          </div>
          <div style={{ display:'flex', gap:8 }}>
            <div style={{ padding:'6px 12px', borderRadius:8, background:'#111118', border:'1px solid #1a1a2e', fontSize:12, color:'#6b7280' }}>
              {certs.length} certs · {agencies.length} agencies
            </div>
          </div>
        </header>

        {/* Page */}
        <div style={{ flex:1, overflowY:'auto' }}>
          {page === 'overview'     && <Overview     {...shared} stateMeta={STATE_META} timeSavedHours={timeSavedHours} inProgress={inProgress} onNavigate={setPage} />}
          {page === 'certificates' && <Certificates {...shared} stateMeta={STATE_META} />}
          {page === 'approvals'    && <Approvals    {...shared} />}
          {page === 'activity'     && <ActivityLog  />}
          {page === 'exceptions'   && <Exceptions   {...shared} stateMeta={STATE_META} />}
          {page === 'reports'      && <Reports />}
          {page === 'demo'         && <DemoPage     {...shared} stateMeta={STATE_META} onNavigate={setPage} />}
        </div>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
        * { box-sizing:border-box; margin:0; padding:0; }
        body { font-family:Inter,system-ui,sans-serif; }
        ::-webkit-scrollbar { width:5px; }
        ::-webkit-scrollbar-track { background:#0a0a12; }
        ::-webkit-scrollbar-thumb { background:#2d2d4a; border-radius:99px; }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
        @keyframes spin { to { transform:rotate(360deg); } }
        @keyframes fadeUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
        @keyframes shimmer { 0% { background-position:-200% 0; } 100% { background-position:200% 0; } }
        .fade-up { animation:fadeUp 0.35s ease forwards; }
        .shimmer-box { background:linear-gradient(90deg,#111118 25%,#1a1a2e 50%,#111118 75%); background-size:200% 100%; animation:shimmer 1.4s infinite; }
        button { font-family:inherit; }
      `}</style>
    </div>
  )
}
