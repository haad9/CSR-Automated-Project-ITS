import React, { useState } from 'react'
import axios from 'axios'
import { Search, Play, RefreshCw, ChevronDown, ChevronUp, Lock, Calendar, Building2 } from 'lucide-react'
import { API, STATE_META } from '../lib/constants'

export default function Certificates({ certs, agencies, agencyMap, fetchData, loading }) {
  const [search,       setSearch]       = useState('')
  const [stateFilter,  setStateFilter]  = useState('all')
  const [agencyFilter, setAgencyFilter] = useState('all')
  const [expanded,     setExpanded]     = useState(null)
  const [triggering,   setTriggering]   = useState({})

  const filtered = certs.filter(c => {
    const q = search.toLowerCase()
    return (!q || c.domain?.toLowerCase().includes(q) || c.cert_id?.includes(q))
        && (stateFilter  === 'all' || c.state      === stateFilter)
        && (agencyFilter === 'all' || c.agency_id  === agencyFilter)
  })

  const triggerRenewal = async (cert_id) => {
    setTriggering(t => ({ ...t, [cert_id]: true }))
    try {
      await axios.post(`${API}/certs/${cert_id}/trigger`, { triggered_by: 'dashboard' })
      await fetchData()
    } catch(e) { alert('Failed to trigger renewal: ' + e.message) }
    finally { setTriggering(t => ({ ...t, [cert_id]: false })) }
  }

  const inp = { background:'#0d0d1a', border:'1px solid #1e1e2e', color:'#e2e8f0', borderRadius:10, padding:'9px 12px', fontSize:13, fontFamily:'inherit', outline:'none', transition:'border-color 0.2s' }

  return (
    <div style={{ padding:24, display:'flex', flexDirection:'column', gap:16 }} className="fade-up">

      {/* Accent bar */}
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
        <div style={{ width:3, height:24, borderRadius:99, background:'#10b981' }} />
        <span style={{ fontSize:12, color:'#10b981', fontWeight:600, letterSpacing:1 }}>CERTIFICATE MANAGER</span>
      </div>

      {/* Filters */}
      <div style={{ display:'flex', gap:10 }}>
        <div style={{ position:'relative', flex:1 }}>
          <Search size={14} color="#4b5563" style={{ position:'absolute', left:12, top:'50%', transform:'translateY(-50%)' }} />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search domain or cert ID..."
            style={{ ...inp, paddingLeft:36, width:'100%' }}
            onFocus={e => e.target.style.borderColor = '#10b981'}
            onBlur={e => e.target.style.borderColor = '#1e1e2e'} />
        </div>
        <select value={stateFilter} onChange={e => setStateFilter(e.target.value)} style={{ ...inp, cursor:'pointer' }}>
          <option value="all">All States</option>
          {[...new Set(certs.map(c => c.state))].map(s => <option key={s} value={s}>{STATE_META[s]?.label || s}</option>)}
        </select>
        <select value={agencyFilter} onChange={e => setAgencyFilter(e.target.value)} style={{ ...inp, cursor:'pointer' }}>
          <option value="all">All Agencies</option>
          {agencies.map(a => <option key={a.agency_id} value={a.agency_id}>{a.short_name || a.name}</option>)}
        </select>
      </div>

      <div style={{ fontSize:12, color:'#4b5563' }}>{filtered.length} certificate{filtered.length !== 1 ? 's' : ''}</div>

      {/* Cards grid */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:14 }}>

        {loading && [1,2,3,4].map(i => (
          <div key={i} className="shimmer-box" style={{ height:180, borderRadius:16, border:'1px solid #1a1a2e' }} />
        ))}

        {!loading && filtered.map(cert => {
          const meta  = STATE_META[cert.state] || {}
          const days  = cert.expiry_date ? Math.ceil((new Date(cert.expiry_date) - new Date()) / 86400000) : null
          const agency = agencyMap?.[cert.agency_id]
          const open  = expanded === cert.cert_id

          return (
            <div key={cert.cert_id} style={{
              background:'#0d0d1a', borderRadius:16, overflow:'hidden',
              border:`1px solid ${open ? meta.border || '#2d2d4a' : '#1a1a2e'}`,
              transition:'all 0.25s', cursor:'default',
            }}
              onMouseEnter={e => { if (!open) e.currentTarget.style.borderColor = '#2d2d4a'; e.currentTarget.style.transform = 'translateY(-2px)' }}
              onMouseLeave={e => { if (!open) e.currentTarget.style.borderColor = '#1a1a2e'; e.currentTarget.style.transform = 'none' }}>

              {/* State color stripe */}
              <div style={{ height:3, background: meta.color || '#374151', opacity:0.6 }} />

              <div style={{ padding:'16px 18px' }}>
                {/* Header */}
                <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:10, marginBottom:12 }}>
                  <div style={{ minWidth:0, flex:1 }}>
                    <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:4 }}>
                      <Lock size={13} color={meta.color || '#6b7280'} style={{ flexShrink:0 }} />
                      <span style={{ fontWeight:700, fontSize:15, color:'#fff', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{cert.domain}</span>
                    </div>
                    {agency && (
                      <div style={{ display:'flex', alignItems:'center', gap:4, fontSize:11, color:'#4b5563' }}>
                        <Building2 size={10} />
                        {agency.short_name || agency.name}
                      </div>
                    )}
                  </div>

                  {/* State badge */}
                  <div style={{ flexShrink:0, padding:'5px 10px', borderRadius:20, fontSize:12, fontWeight:700, background:meta.bg, color:meta.color, border:`1px solid ${meta.border}`, whiteSpace:'nowrap' }}>
                    {meta.icon} {meta.label || cert.state}
                  </div>
                </div>

                {/* Progress bar */}
                {cert.state !== 'Exception' && (
                  <div style={{ marginBottom:12 }}>
                    <div style={{ height:6, borderRadius:99, background:'#1a1a2e', overflow:'hidden' }}>
                      <div style={{ height:'100%', width:`${meta.pct || 0}%`, borderRadius:99, transition:'width 0.8s ease',
                        background: cert.state === 'Active' ? 'linear-gradient(90deg,#059669,#4ade80)' : `linear-gradient(90deg,#3b82f6,${meta.color || '#60a5fa'})` }} />
                    </div>
                    <div style={{ display:'flex', justifyContent:'space-between', fontSize:10, color:'#374151', marginTop:3 }}>
                      <span>Renewal progress</span><span>{meta.pct || 0}%</span>
                    </div>
                  </div>
                )}

                {/* Expiry */}
                {days !== null && (
                  <div style={{ display:'flex', alignItems:'center', gap:6, fontSize:13 }}>
                    <Calendar size={12} color={days <= 7 ? '#ef4444' : days <= 30 ? '#f59e0b' : '#4b5563'} />
                    <span style={{ fontWeight:600, color: days <= 7 ? '#ef4444' : days <= 30 ? '#fbbf24' : '#6b7280' }}>
                      {days < 0 ? `Expired ${Math.abs(days)}d ago` : `${days} days until expiry`}
                    </span>
                    <span style={{ fontSize:11, color:'#374151' }}>({cert.expiry_date})</span>
                  </div>
                )}
              </div>

              {/* Footer actions */}
              <div style={{ padding:'10px 18px 14px', borderTop:'1px solid #111118', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
                <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                  <button onClick={() => triggerRenewal(cert.cert_id)}
                    disabled={!!triggering[cert.cert_id] || cert.state !== 'Active'}
                    style={{
                      display:'flex', alignItems:'center', gap:6, padding:'6px 12px', borderRadius:8, fontSize:12, fontWeight:600, cursor: cert.state === 'Active' ? 'pointer' : 'not-allowed',
                      background: cert.state === 'Active' ? 'rgba(16,185,129,0.1)' : '#111118',
                      color:      cert.state === 'Active' ? '#4ade80' : '#374151',
                      border:    `1px solid ${cert.state === 'Active' ? 'rgba(16,185,129,0.3)' : '#1e1e2e'}`,
                      transition:'all 0.15s', opacity: triggering[cert.cert_id] ? 0.6 : 1,
                    }}
                    onMouseEnter={e => { if(cert.state === 'Active') e.currentTarget.style.background = 'rgba(16,185,129,0.2)' }}
                    onMouseLeave={e => { e.currentTarget.style.background = cert.state === 'Active' ? 'rgba(16,185,129,0.1)' : '#111118' }}>
                    {triggering[cert.cert_id] ? <RefreshCw size={11} style={{ animation:'spin 1s linear infinite' }} /> : <Play size={11} />}
                    Renew Now
                  </button>
                  {(parseInt(cert.renewals_count) || 0) > 0 && (
                    <span style={{ fontSize:11, color:'#374151' }}>{cert.renewals_count} done</span>
                  )}
                </div>
                <button onClick={() => setExpanded(open ? null : cert.cert_id)}
                  style={{ background:'#111118', border:'1px solid #1e1e2e', color:'#6b7280', borderRadius:8, padding:'5px 8px', cursor:'pointer', display:'flex', alignItems:'center' }}>
                  {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                </button>
              </div>

              {/* Expanded detail */}
              {open && (
                <div style={{ padding:'0 18px 18px', borderTop:'1px solid #111118', paddingTop:14 }} className="fade-up">
                  <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
                    {[
                      ['Cert ID', cert.cert_id],
                      ['Agency', agency?.name || cert.agency_id || '—'],
                      ['State', cert.state],
                      ['Expiry Date', cert.expiry_date || '—'],
                      ['Last Renewed', cert.last_renewed_at ? new Date(cert.last_renewed_at).toLocaleDateString() : '—'],
                      ['Total Renewals', cert.renewals_count || 0],
                    ].map(([k,v]) => (
                      <div key={k} style={{ background:'#111118', borderRadius:8, padding:'9px 10px' }}>
                        <div style={{ fontSize:10, color:'#4b5563', marginBottom:2 }}>{k}</div>
                        <div style={{ fontSize:12, fontWeight:600, color:'#e2e8f0', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{String(v)}</div>
                      </div>
                    ))}
                  </div>
                  {cert.exception_analysis && (
                    <div style={{ marginTop:10, padding:'10px 12px', borderRadius:10, background:'rgba(248,113,113,0.06)', border:'1px solid rgba(248,113,113,0.2)' }}>
                      <div style={{ fontSize:11, fontWeight:700, color:'#f87171', marginBottom:4 }}>🤖 AI Exception Analysis</div>
                      <div style={{ fontSize:12, color:'#fca5a5' }}>{cert.exception_analysis.root_cause}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {!loading && filtered.length === 0 && (
        <div style={{ textAlign:'center', padding:'60px 0', color:'#374151' }}>
          <Lock size={40} color="#1f2937" style={{ margin:'0 auto 12px' }} />
          <div style={{ fontSize:16, fontWeight:600, color:'#6b7280' }}>No certificates found</div>
          <div style={{ fontSize:13, color:'#374151', marginTop:4 }}>Try adjusting your search or filters</div>
        </div>
      )}
    </div>
  )
}
