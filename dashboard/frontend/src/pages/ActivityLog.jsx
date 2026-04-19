import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Search, Activity } from 'lucide-react'
import { API } from '../lib/constants'

const ACTION_META = {
  RENEWAL_INITIATED:      { icon: '🔄', label: 'Renewal Started',       color: '#60a5fa', bg: 'rgba(96,165,250,0.08)'   },
  CSR_GENERATED:          { icon: '📝', label: 'Request Built',          color: '#a78bfa', bg: 'rgba(167,139,250,0.08)'  },
  CERTIFICATE_ISSUED:     { icon: '✅', label: 'Certificate Issued',     color: '#c084fc', bg: 'rgba(192,132,252,0.08)'  },
  GOVERNANCE_REQUESTED:   { icon: '🛡️', label: 'Approval Requested',    color: '#fbbf24', bg: 'rgba(251,191,36,0.08)'   },
  GOVERNANCE_DECISION:    { icon: '👤', label: 'Officer Decision',       color: '#fb923c', bg: 'rgba(251,146,60,0.08)'   },
  CERTIFICATE_DEPLOYED:   { icon: '🚀', label: 'Deployed to Server',     color: '#22d3ee', bg: 'rgba(34,211,238,0.08)'  },
  CERTIFICATE_VALIDATED:  { icon: '🔍', label: 'Validation Confirmed',   color: '#2dd4bf', bg: 'rgba(45,212,191,0.08)'  },
  RENEWAL_CLOSED:         { icon: '🎉', label: 'Renewal Complete',       color: '#4ade80', bg: 'rgba(74,222,128,0.08)'  },
  EXCEPTION_ANALYZED:     { icon: '🤖', label: 'AI Analysis',            color: '#f87171', bg: 'rgba(248,113,113,0.08)' },
  STATE_CHANGE:           { icon: '↗️', label: 'State Changed',          color: '#9ca3af', bg: 'rgba(156,163,175,0.08)' },
  CERT_CREATED:           { icon: '🆕', label: 'Certificate Added',      color: '#60a5fa', bg: 'rgba(96,165,250,0.08)'  },
}

const inp = { background:'#0d0d1a', border:'1px solid #1e1e2e', color:'#e2e8f0', borderRadius:10, padding:'9px 12px', fontSize:13, fontFamily:'inherit', outline:'none' }

export default function ActivityLog() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [search,  setSearch]  = useState('')

  const load = async () => {
    try {
      const resp = await axios.get(`${API}/audit?limit=200`)
      setEntries(resp.data.entries || [])
    } catch(e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  const sorted = [...entries]
    .sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''))
    .filter(e => {
      const q = search.toLowerCase()
      return !q || e.cert_id?.includes(q) || e.action?.toLowerCase().includes(q)
        || e.details?.domain?.toLowerCase().includes(q)
    })

  const groupedByDate = sorted.reduce((acc, e) => {
    const date = e.timestamp
      ? new Date(e.timestamp).toLocaleDateString('en-US', { weekday:'long', month:'short', day:'numeric' })
      : 'Unknown'
    if (!acc[date]) acc[date] = []
    acc[date].push(e)
    return acc
  }, {})

  return (
    <div style={{ padding:24, display:'flex', flexDirection:'column', gap:16 }} className="fade-up">

      {/* Accent bar */}
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
        <div style={{ width:3, height:24, borderRadius:99, background:'#8b5cf6' }} />
        <span style={{ fontSize:12, color:'#8b5cf6', fontWeight:600, letterSpacing:1 }}>ACTIVITY LOG</span>
      </div>

      {/* Search + count */}
      <div style={{ display:'flex', alignItems:'center', gap:12 }}>
        <div style={{ position:'relative', flex:1 }}>
          <Search size={14} color="#4b5563" style={{ position:'absolute', left:12, top:'50%', transform:'translateY(-50%)' }} />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search by domain, action, or cert ID..."
            style={{ ...inp, paddingLeft:36, width:'100%' }}
            onFocus={e => e.target.style.borderColor = '#8b5cf6'}
            onBlur={e => e.target.style.borderColor = '#1e1e2e'} />
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:6, fontSize:13, color:'#6b7280', whiteSpace:'nowrap' }}>
          <Activity size={14} />
          {sorted.length} events
        </div>
      </div>

      {/* Loading shimmer */}
      {loading && [1,2,3,4,5].map(i => (
        <div key={i} className="shimmer-box" style={{ height:64, borderRadius:12, border:'1px solid #1a1a2e' }} />
      ))}

      {/* Grouped entries */}
      {Object.entries(groupedByDate).map(([date, dayEntries]) => (
        <div key={date}>
          <div style={{ fontSize:11, fontWeight:600, textTransform:'uppercase', letterSpacing:1, color:'#4b5563', marginBottom:8, paddingLeft:4 }}>{date}</div>
          <div style={{ borderRadius:16, overflow:'hidden', background:'#0d0d1a', border:'1px solid #1a1a2e' }}>
            {dayEntries.map((entry, i) => {
              const meta   = ACTION_META[entry.action] || ACTION_META.STATE_CHANGE
              const time   = entry.timestamp
                ? new Date(entry.timestamp).toLocaleTimeString('en-US', { hour:'2-digit', minute:'2-digit' })
                : ''
              const domain    = entry.details?.domain
              const decision  = entry.details?.decision
              const newState  = entry.details?.new_state

              return (
                <div key={i} style={{
                  display:'flex', alignItems:'center', gap:14, padding:'12px 16px',
                  borderBottom: i < dayEntries.length - 1 ? '1px solid #111118' : 'none',
                  transition:'background 0.15s',
                }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>

                  {/* Icon blob */}
                  <div style={{ width:34, height:34, borderRadius:10, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0, fontSize:16, background: meta.bg }}>
                    {meta.icon}
                  </div>

                  {/* Content */}
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ display:'flex', alignItems:'center', gap:8, flexWrap:'wrap' }}>
                      <span style={{ fontWeight:600, fontSize:13, color: meta.color }}>{meta.label}</span>
                      {domain && <span style={{ fontSize:13, fontWeight:500, color:'#fff' }}>{domain}</span>}
                      {newState && (
                        <span style={{ fontSize:11, padding:'2px 8px', borderRadius:99, background:'#1a1a2e', color:'#9ca3af' }}>→ {newState}</span>
                      )}
                      {decision && (
                        <span style={{ fontSize:11, padding:'2px 8px', borderRadius:99, fontWeight:600,
                          background: decision === 'approve' ? 'rgba(74,222,128,0.1)' : 'rgba(248,113,113,0.1)',
                          color: decision === 'approve' ? '#4ade80' : '#f87171',
                          border: `1px solid ${decision === 'approve' ? 'rgba(74,222,128,0.3)' : 'rgba(248,113,113,0.3)'}`,
                        }}>
                          {decision === 'approve' ? '✓ Approved' : '✗ Rejected'}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize:11, marginTop:2, color:'#4b5563', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                      {entry.cert_id}
                      {entry.actor && entry.actor !== 'system' && <span> · by {entry.actor}</span>}
                    </div>
                  </div>

                  {/* Time */}
                  <div style={{ fontSize:11, flexShrink:0, fontFamily:'monospace', color:'#4b5563' }}>{time}</div>
                </div>
              )
            })}
          </div>
        </div>
      ))}

      {!loading && sorted.length === 0 && (
        <div style={{ textAlign:'center', padding:'60px 0', color:'#374151' }}>
          <Activity size={40} color="#1f2937" style={{ margin:'0 auto 12px' }} />
          <div style={{ fontSize:16, fontWeight:600, color:'#6b7280' }}>No activity yet</div>
          <div style={{ fontSize:13, color:'#374151', marginTop:4 }}>Events will appear here as the system processes certificates</div>
        </div>
      )}
    </div>
  )
}
