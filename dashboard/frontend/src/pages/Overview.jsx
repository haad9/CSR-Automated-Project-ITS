import React from 'react'
import { ArrowRight, TrendingUp, Shield, AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import { STATE_META, PIPELINE_STEPS } from '../lib/constants'

export default function Overview({ certs, agencies, stateCounts, timeSavedHours, inProgress, totalRenewals, onNavigate, loading }) {
  const active      = stateCounts['Active'] || 0
  const exceptions  = stateCounts['Exception'] || 0
  const expiringSoon = certs.filter(c => {
    if (!c.expiry_date || c.state !== 'Active') return false
    return Math.ceil((new Date(c.expiry_date) - new Date()) / 86400000) <= 14
  })
  const renewingNow = certs.filter(c => !['Active','Exception','Renewal Closed'].includes(c.state))

  return (
    <div style={{ padding:24, display:'flex', flexDirection:'column', gap:20 }} className="fade-up">

      {/* Stat cards */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:14 }}>
        {[
          { icon:'🔒', value:certs.length,    label:'Total Certificates', sub:`${agencies.length} agencies`,       color:'#3b82f6', glow:true },
          { icon:'✅', value:active,           label:'Secure Right Now',   sub:'valid & active',                   color:'#10b981' },
          { icon:'⚠️', value:expiringSoon.length, label:'Expiring in 14d', sub:'auto-renewal will trigger',       color:'#f59e0b', urgent:expiringSoon.length>0 },
          { icon:'⏱️', value:`${timeSavedHours}h`, label:'Hours Saved',   sub:`${totalRenewals} auto-renewals`,   color:'#a855f7' },
        ].map((s,i) => (
          <div key={i} style={{
            background:'#0d0d1a', borderRadius:16, padding:'20px', position:'relative', overflow:'hidden',
            border:`1px solid ${s.urgent ? 'rgba(245,158,11,0.3)' : '#1a1a2e'}`,
            boxShadow: s.glow ? `0 0 40px ${s.color}12` : 'none',
          }}>
            {/* glow blob */}
            <div style={{ position:'absolute', top:-20, right:-20, width:80, height:80, borderRadius:'50%', background:s.color, opacity:0.06, filter:'blur(20px)' }} />
            <div style={{ fontSize:24, marginBottom:12 }}>{s.icon}</div>
            <div style={{ fontSize:28, fontWeight:800, color:'#fff', marginBottom:2 }}>{s.value}</div>
            <div style={{ fontSize:13, fontWeight:600, color:'#d1d5db' }}>{s.label}</div>
            <div style={{ fontSize:11, color:'#4b5563', marginTop:2 }}>{s.sub}</div>
            {s.urgent && <div style={{ position:'absolute', top:12, right:12, width:8, height:8, borderRadius:'50%', background:'#f59e0b', animation:'pulse 1.5s infinite' }} />}
          </div>
        ))}
      </div>

      {/* Pipeline */}
      <div style={{ background:'#0d0d1a', borderRadius:16, padding:20, border:'1px solid #1a1a2e' }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:16 }}>
          <div>
            <h2 style={{ fontWeight:700, fontSize:15, color:'#fff' }}>The 8-Stage Automatic Pipeline</h2>
            <p style={{ fontSize:12, color:'#4b5563', marginTop:2 }}>Every certificate flows through these stages — zero manual work required</p>
          </div>
          {inProgress > 0 && (
            <div style={{ display:'flex', alignItems:'center', gap:6, padding:'6px 12px', borderRadius:20, background:'rgba(96,165,250,0.1)', border:'1px solid rgba(96,165,250,0.25)', fontSize:12, color:'#60a5fa' }}>
              <div style={{ width:6, height:6, borderRadius:'50%', background:'#60a5fa', animation:'pulse 1.5s infinite' }} />
              {inProgress} renewing now
            </div>
          )}
        </div>

        <div style={{ display:'flex', alignItems:'center', gap:4 }}>
          {PIPELINE_STEPS.map((step, i) => {
            const count = stateCounts[step.key] || 0
            const meta  = STATE_META[step.key] || {}
            const active = count > 0
            return (
              <React.Fragment key={step.key}>
                <div style={{
                  flex:1, textAlign:'center', padding:'12px 8px', borderRadius:12, transition:'all 0.3s',
                  background: active ? meta.bg : '#111118',
                  border:`1px solid ${active ? meta.border : '#1e1e2e'}`,
                  transform: active ? 'translateY(-2px)' : 'none',
                  boxShadow: active ? `0 4px 20px ${meta.color}18` : 'none',
                }}>
                  <div style={{ fontSize:18, marginBottom:4 }}>{step.short}</div>
                  <div style={{ fontSize:10, fontWeight:600, color: active ? meta.color : '#374151', lineHeight:1.2 }}>{step.label}</div>
                  <div style={{ marginTop:6, fontSize: active ? 18 : 14, fontWeight:800, color: active ? meta.color : '#1f2937' }}>
                    {active ? count : '—'}
                  </div>
                </div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <ArrowRight size={11} color="#1f2937" style={{ flexShrink:0 }} />
                )}
              </React.Fragment>
            )
          })}
        </div>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 }}>

        {/* Renewing now */}
        <div style={{ background:'#0d0d1a', borderRadius:16, padding:20, border:'1px solid #1a1a2e' }}>
          <h3 style={{ fontWeight:700, fontSize:14, color:'#fff', marginBottom:14, display:'flex', alignItems:'center', gap:8 }}>
            <div style={{ width:8, height:8, borderRadius:'50%', background:'#60a5fa', animation:'pulse 1.5s infinite' }} />
            Currently Renewing
            {renewingNow.length === 0 && <span style={{ fontSize:12, fontWeight:400, color:'#4b5563' }}>— all quiet</span>}
          </h3>
          {renewingNow.length === 0 ? (
            <div style={{ textAlign:'center', padding:'20px 0', color:'#374151' }}>
              <CheckCircle size={32} color="#4ade80" style={{ margin:'0 auto 8px' }} />
              <div style={{ fontSize:13, color:'#6b7280' }}>All certs are Active</div>
            </div>
          ) : renewingNow.map(cert => {
            const meta = STATE_META[cert.state] || {}
            return (
              <div key={cert.cert_id} style={{ display:'flex', alignItems:'center', gap:12, padding:'10px 12px', borderRadius:10, background:'#111118', marginBottom:6 }}>
                <div style={{ fontSize:18 }}>{meta.icon}</div>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontSize:13, fontWeight:600, color:'#fff', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{cert.domain}</div>
                  <div style={{ marginTop:4, height:4, borderRadius:99, background:'#1a1a2e', overflow:'hidden' }}>
                    <div style={{ height:'100%', borderRadius:99, width:`${meta.pct || 0}%`, background:`linear-gradient(90deg,#3b82f6,${meta.color})`, transition:'width 0.8s ease' }} />
                  </div>
                </div>
                <div style={{ fontSize:11, color:meta.color, fontWeight:600, whiteSpace:'nowrap' }}>{meta.label}</div>
              </div>
            )
          })}
        </div>

        {/* Agency breakdown */}
        <div style={{ background:'#0d0d1a', borderRadius:16, padding:20, border:'1px solid #1a1a2e' }}>
          <h3 style={{ fontWeight:700, fontSize:14, color:'#fff', marginBottom:14 }}>Agency Breakdown</h3>
          {agencies.map(agency => {
            const agencyCerts = certs.filter(c => c.agency_id === agency.agency_id)
            const secureCount = agencyCerts.filter(c => c.state === 'Active').length
            const pct = agencyCerts.length ? Math.round((secureCount / agencyCerts.length) * 100) : 0
            return (
              <div key={agency.agency_id} style={{ marginBottom:14 }}>
                <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
                  <span style={{ fontSize:13, fontWeight:600, color:'#d1d5db' }}>{agency.short_name || agency.name}</span>
                  <span style={{ fontSize:12, color:'#6b7280' }}>{secureCount}/{agencyCerts.length} secure</span>
                </div>
                <div style={{ height:6, borderRadius:99, background:'#1a1a2e', overflow:'hidden' }}>
                  <div style={{ height:'100%', width:`${pct}%`, borderRadius:99, background:'linear-gradient(90deg,#059669,#4ade80)', transition:'width 0.8s ease' }} />
                </div>
              </div>
            )
          })}
          <button onClick={() => onNavigate('certificates')}
            style={{ marginTop:8, width:'100%', padding:'9px', borderRadius:10, background:'rgba(16,185,129,0.08)', border:'1px solid rgba(16,185,129,0.2)', color:'#4ade80', fontSize:13, fontWeight:600, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', gap:6 }}>
            View all certificates <ArrowRight size={14} />
          </button>
        </div>
      </div>

      {/* Expiring soon */}
      {expiringSoon.length > 0 && (
        <div style={{ background:'rgba(245,158,11,0.05)', borderRadius:16, padding:20, border:'1px solid rgba(245,158,11,0.2)' }}>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:14 }}>
            <AlertTriangle size={16} color="#fbbf24" />
            <h3 style={{ fontWeight:700, fontSize:14, color:'#fff' }}>Expiring Within 14 Days</h3>
            <span style={{ fontSize:12, color:'#f59e0b' }}>— auto-renewal will start automatically</span>
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(180px,1fr))', gap:10 }}>
            {expiringSoon.map(cert => {
              const days = Math.ceil((new Date(cert.expiry_date) - new Date()) / 86400000)
              return (
                <div key={cert.cert_id} style={{ background:'rgba(0,0,0,0.3)', borderRadius:10, padding:'12px', border:'1px solid rgba(245,158,11,0.15)' }}>
                  <div style={{ fontSize:13, fontWeight:600, color:'#fff', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{cert.domain}</div>
                  <div style={{ fontSize:20, fontWeight:800, marginTop:6, color: days <= 7 ? '#ef4444' : '#fbbf24' }}>{days}d left</div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
