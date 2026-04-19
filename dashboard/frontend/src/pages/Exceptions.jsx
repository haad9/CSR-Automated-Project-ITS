import React from 'react'
import { AlertTriangle, CheckCircle, Cpu, Clock } from 'lucide-react'

const SEVERITY = {
  CRITICAL: { bg:'rgba(248,113,113,0.06)', border:'rgba(248,113,113,0.3)', color:'#f87171', label:'🚨 Critical' },
  HIGH:     { bg:'rgba(248,113,113,0.06)', border:'rgba(248,113,113,0.3)', color:'#f87171', label:'🔴 High'     },
  MEDIUM:   { bg:'rgba(251,191,36,0.06)',  border:'rgba(251,191,36,0.3)',  color:'#fbbf24', label:'🟡 Medium'   },
  LOW:      { bg:'rgba(156,163,175,0.06)', border:'rgba(156,163,175,0.2)', color:'#9ca3af', label:'⚪ Low'      },
}

export default function Exceptions({ certs, agencyMap }) {
  const exceptions = certs.filter(c => c.state === 'Exception')

  if (exceptions.length === 0) {
    return (
      <div style={{ padding:24, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', minHeight:400 }} className="fade-up">
        <div style={{ width:80, height:80, borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', marginBottom:16, background:'rgba(74,222,128,0.08)', border:'2px solid rgba(74,222,128,0.3)' }}>
          <CheckCircle size={36} color="#4ade80" />
        </div>
        <h2 style={{ fontSize:20, fontWeight:700, color:'#fff', marginBottom:8 }}>No Incidents</h2>
        <p style={{ textAlign:'center', maxWidth:380, color:'#6b7280', fontSize:14, lineHeight:1.6 }}>
          All certificate renewals are running smoothly. When a failure occurs,
          our AI will automatically analyze what went wrong and show it here.
        </p>
        <div style={{ marginTop:24, display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, maxWidth:420, width:'100%' }}>
          {[
            { icon:'🤖', text:'Claude AI analyzes every failure' },
            { icon:'📊', text:'Root cause + fix steps provided' },
            { icon:'🔔', text:'Instant email alert sent' },
            { icon:'🔄', text:'Auto-retry when safe to do so' },
          ].map(item => (
            <div key={item.text} style={{ padding:14, borderRadius:12, background:'#0d0d1a', border:'1px solid #1a1a2e', textAlign:'center' }}>
              <div style={{ fontSize:22, marginBottom:6 }}>{item.icon}</div>
              <div style={{ fontSize:12, color:'#9ca3af' }}>{item.text}</div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding:24, display:'flex', flexDirection:'column', gap:16 }} className="fade-up">

      {/* Accent bar */}
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
        <div style={{ width:3, height:24, borderRadius:99, background:'#ef4444' }} />
        <span style={{ fontSize:12, color:'#ef4444', fontWeight:600, letterSpacing:1 }}>INCIDENTS & EXCEPTIONS</span>
      </div>

      {/* Summary banner */}
      <div style={{ display:'flex', alignItems:'center', gap:10, padding:16, borderRadius:14, background:'rgba(248,113,113,0.06)', border:'1px solid rgba(248,113,113,0.3)' }}>
        <AlertTriangle size={18} color="#f87171" />
        <span style={{ fontWeight:600, color:'#fff', fontSize:14 }}>
          {exceptions.length} certificate{exceptions.length > 1 ? 's' : ''} need attention
        </span>
        <span style={{ fontSize:13, color:'#f87171' }}>— AI analysis available below</span>
      </div>

      {exceptions.map(cert => {
        const a   = cert.exception_analysis || {}
        const sev = SEVERITY[a.severity] || SEVERITY.HIGH
        const agency = agencyMap?.[cert.agency_id]

        return (
          <div key={cert.cert_id} style={{ borderRadius:16, overflow:'hidden', background: sev.bg, border:`1px solid ${sev.border}` }}>

            {/* Header */}
            <div style={{ padding:20 }}>
              <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:16, marginBottom:16 }}>
                <div>
                  <div style={{ fontWeight:700, color:'#fff', fontSize:17 }}>{cert.domain}</div>
                  {agency && <div style={{ fontSize:13, marginTop:2, color:'#9ca3af' }}>{agency.name}</div>}
                  {cert.exception_at && (
                    <div style={{ display:'flex', alignItems:'center', gap:6, fontSize:12, marginTop:4, color:'#6b7280' }}>
                      <Clock size={11} />
                      Failed {new Date(cert.exception_at).toLocaleString()}
                    </div>
                  )}
                </div>
                <div style={{ padding:'6px 12px', borderRadius:99, fontSize:12, fontWeight:700, background:'rgba(0,0,0,0.3)', color: sev.color, border:`1px solid ${sev.border}`, whiteSpace:'nowrap' }}>
                  {sev.label}
                </div>
              </div>

              {/* AI Analysis */}
              {a.ai_analyzed !== false && (
                <div style={{ display:'flex', alignItems:'flex-start', gap:10, marginBottom:16, padding:'12px 14px', borderRadius:12, background:'rgba(0,0,0,0.25)' }}>
                  <Cpu size={14} color={sev.color} style={{ flexShrink:0, marginTop:2 }} />
                  <div>
                    <div style={{ fontSize:12, fontWeight:600, marginBottom:4, color: sev.color }}>
                      Claude AI Analysis {a.ai_model && <span style={{ color:'#6b7280', fontWeight:400 }}>({a.ai_model})</span>}
                    </div>
                    <div style={{ fontSize:13, color:'#e2e8f0', lineHeight:1.6 }}>{a.root_cause || 'Analyzing...'}</div>
                  </div>
                </div>
              )}

              {/* Impact */}
              {a.impact && (
                <div style={{ marginBottom:16 }}>
                  <div style={{ fontSize:11, fontWeight:600, textTransform:'uppercase', letterSpacing:1, color:'#6b7280', marginBottom:6 }}>Impact</div>
                  <div style={{ fontSize:13, color:'#d1d5db', lineHeight:1.6 }}>{a.impact}</div>
                </div>
              )}

              {/* Remediation steps */}
              {a.remediation_steps?.length > 0 && (
                <div>
                  <div style={{ fontSize:11, fontWeight:600, textTransform:'uppercase', letterSpacing:1, color:'#6b7280', marginBottom:8 }}>How to fix it</div>
                  <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
                    {a.remediation_steps.map((step, i) => (
                      <div key={i} style={{ display:'flex', alignItems:'flex-start', gap:12, padding:'10px 12px', borderRadius:10, background:'rgba(0,0,0,0.2)', fontSize:13 }}>
                        <div style={{ width:22, height:22, borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', fontSize:11, fontWeight:700, flexShrink:0, background:`${sev.border}`, color: sev.color }}>
                          {i + 1}
                        </div>
                        <span style={{ color:'#d1d5db', lineHeight:1.5 }}>{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div style={{ padding:'10px 20px', display:'flex', alignItems:'center', justifyContent:'space-between', fontSize:12, borderTop:`1px solid ${sev.border}`, background:'rgba(0,0,0,0.2)' }}>
              <div style={{ display:'flex', gap:16, color:'#6b7280' }}>
                <span>Est. fix time: <strong style={{ color:'#9ca3af' }}>{a.estimated_resolution_time || '—'}</strong></span>
                <span>Auto-retry: <strong style={{ color: a.can_auto_retry ? '#4ade80' : '#f87171' }}>{a.can_auto_retry ? 'Yes' : 'No'}</strong></span>
              </div>
              <span style={{ color:'#4b5563', fontFamily:'monospace' }}>{cert.cert_id}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
