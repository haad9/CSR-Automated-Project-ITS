import React, { useState } from 'react'
import axios from 'axios'
import { CheckCircle, XCircle, Clock, Shield, Building, Calendar, Check, X } from 'lucide-react'
import { API } from '../lib/constants'

export default function Approvals({ certs, agencyMap, fetchData }) {
  const pending = certs.filter(c => c.governance_task_token && !c.governance_approved && c.state === 'Certificate Issued')
  const [decisions, setDecisions] = useState({})
  const [loading,   setLoading]   = useState({})

  const decide = async (cert, action) => {
    setLoading(d => ({ ...d, [cert.cert_id]: true }))
    try {
      await axios.post(`${API}/governance/approve`, {
        cert_id: cert.cert_id,
        task_token: cert.governance_task_token,
        action,
      })
      setDecisions(d => ({ ...d, [cert.cert_id]: action }))
      setTimeout(fetchData, 1500)
    } catch(e) { console.error(e) }
    finally { setLoading(d => ({ ...d, [cert.cert_id]: false })) }
  }

  if (pending.length === 0) {
    return (
      <div style={{ padding:24, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', minHeight:400 }} className="fade-up">
        <div style={{ width:80, height:80, borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', marginBottom:16, background:'#052e16', border:'2px solid #166534' }}>
          <CheckCircle size={36} color="#4ade80" />
        </div>
        <h2 style={{ fontSize:20, fontWeight:700, color:'#fff', marginBottom:8 }}>All Clear!</h2>
        <p style={{ textAlign:'center', maxWidth:380, color:'#6b7280', fontSize:14, lineHeight:1.6 }}>
          No certificate deployments waiting for your approval right now.
          You'll be notified here (and by email) when one needs review.
        </p>
        <div style={{ marginTop:24, padding:'12px 16px', borderRadius:12, background:'#0d0d1a', border:'1px solid #1a1a2e', color:'#9ca3af', fontSize:13, textAlign:'center', maxWidth:420 }}>
          💡 The system renews certificates automatically — you only need to approve the final <strong style={{ color:'#e2e8f0' }}>deployment step</strong>.
        </div>
        <div style={{ marginTop:24, display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, width:'100%', maxWidth:420 }}>
          {[
            { icon:'🛡️', text:'Human approval required before any cert goes live' },
            { icon:'📧', text:'You get an email notification too' },
            { icon:'⚡', text:'One click to deploy — system does the rest' },
            { icon:'📋', text:'Every decision is logged in the audit trail' },
          ].map((item, i) => (
            <div key={i} style={{ padding:'12px', borderRadius:12, background:'#0d0d1a', border:'1px solid #1a1a2e', textAlign:'center' }}>
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
        <div style={{ width:3, height:24, borderRadius:99, background:'#f59e0b' }} />
        <span style={{ fontSize:12, color:'#f59e0b', fontWeight:600, letterSpacing:1 }}>GOVERNANCE APPROVALS</span>
      </div>

      {/* Explanation banner */}
      <div style={{ borderRadius:16, padding:16, display:'flex', alignItems:'flex-start', gap:12, background:'#1c1000', border:'1px solid #92400e' }}>
        <div style={{ fontSize:24 }}>🛡️</div>
        <div>
          <div style={{ fontWeight:600, color:'#fff', fontSize:14 }}>Your approval is needed before deploying</div>
          <div style={{ fontSize:13, marginTop:4, color:'#d97706', lineHeight:1.6 }}>
            The system has automatically generated and validated new certificates below.
            As the security officer, you choose when they go live on the server.
            Approving takes 2 seconds — deploying is then fully automatic.
          </div>
        </div>
      </div>

      {/* Approval cards */}
      {pending.map(cert => {
        const agency      = agencyMap?.[cert.agency_id]
        const decided     = decisions[cert.cert_id]
        const isLoading   = loading[cert.cert_id]
        const hoursWaiting = cert.governance_requested_at
          ? Math.round((new Date() - new Date(cert.governance_requested_at)) / 3600000)
          : 0

        return (
          <div key={cert.cert_id} style={{ borderRadius:16, overflow:'hidden', background:'#0d0d1a', border:'1px solid #92400e' }}>

            {/* Header */}
            <div style={{ padding:'18px 20px', borderBottom:'1px solid #1a1a2e' }}>
              <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:16 }}>
                <div>
                  <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
                    <Shield size={16} color="#fbbf24" />
                    <span style={{ fontWeight:700, color:'#fff', fontSize:17 }}>{cert.domain}</span>
                  </div>
                  <div style={{ display:'flex', alignItems:'center', gap:16, fontSize:13, color:'#9ca3af' }}>
                    {agency && (
                      <span style={{ display:'flex', alignItems:'center', gap:4 }}>
                        <Building size={12} /> {agency.name || agency.short_name}
                      </span>
                    )}
                    <span style={{ display:'flex', alignItems:'center', gap:4 }}>
                      <Clock size={12} /> Waiting {hoursWaiting > 0 ? `${hoursWaiting}h` : 'just now'}
                    </span>
                  </div>
                </div>
                <div style={{ padding:'6px 12px', borderRadius:99, fontSize:12, fontWeight:600, background:'#431407', color:'#fb923c', border:'1px solid #9a3412', whiteSpace:'nowrap' }}>
                  ⏳ Awaiting Approval
                </div>
              </div>
            </div>

            {/* What's being deployed */}
            <div style={{ padding:20 }}>
              <div style={{ fontSize:11, fontWeight:600, textTransform:'uppercase', letterSpacing:1, color:'#6b7280', marginBottom:12 }}>What will be deployed</div>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:10 }}>
                {[
                  { label:'Current Expiry', value: cert.expiry_date || '—' },
                  { label:'New Expiry',     value: cert.new_expiry_date || '—', accent:true },
                  { label:'Certificate ID', value: cert.cert_id?.slice(-8) + '...' },
                ].map(({ label, value, accent }) => (
                  <div key={label} style={{ borderRadius:10, padding:'10px 12px', background:'#111118', border:`1px solid ${accent ? '#166534' : '#1e1e2e'}` }}>
                    <div style={{ fontSize:11, color:'#6b7280', marginBottom:4 }}>{label}</div>
                    <div style={{ fontSize:13, fontWeight:600, color: accent ? '#4ade80' : '#e2e8f0' }}>{value}</div>
                  </div>
                ))}
              </div>

              <div style={{ marginTop:14, padding:'12px 14px', borderRadius:12, background:'#052e16', border:'1px solid #166534' }}>
                <div style={{ fontWeight:600, color:'#fff', fontSize:13, marginBottom:6 }}>✅ What's already done automatically:</div>
                <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
                  {[
                    'New private key generated and secured in S3',
                    'Certificate signed by the Certificate Authority',
                    'Certificate cryptographically validated',
                    'Ready to install — awaiting your approval',
                  ].map(text => (
                    <div key={text} style={{ fontSize:12, color:'#4ade80' }}>• {text}</div>
                  ))}
                </div>
              </div>
            </div>

            {/* Action buttons */}
            <div style={{ padding:'0 20px 20px' }}>
              {decided ? (
                <div style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:12, padding:'16px', borderRadius:12, background: decided === 'approve' ? '#052e16' : '#2d0a0a' }}>
                  {decided === 'approve'
                    ? <><CheckCircle size={20} color="#4ade80" /><span style={{ fontWeight:600, color:'#4ade80' }}>Approved! Deploying now automatically...</span></>
                    : <><XCircle size={20} color="#f87171" /><span style={{ fontWeight:600, color:'#f87171' }}>Rejected — workflow stopped</span></>
                  }
                </div>
              ) : (
                <div style={{ display:'flex', gap:12 }}>
                  <button onClick={() => decide(cert, 'approve')} disabled={isLoading}
                    style={{
                      flex:1, display:'flex', alignItems:'center', justifyContent:'center', gap:8,
                      padding:'12px', borderRadius:12, fontWeight:700, fontSize:15, cursor:'pointer',
                      background:'linear-gradient(135deg, #059669, #10b981)',
                      color:'#fff', border:'none', fontFamily:'inherit',
                      opacity: isLoading ? 0.7 : 1, transition:'all 0.15s',
                      boxShadow:'0 4px 15px rgba(16,185,129,0.3)',
                    }}>
                    {isLoading
                      ? <RefreshIcon />
                      : <Check size={18} />
                    }
                    Approve Deployment
                  </button>
                  <button onClick={() => decide(cert, 'reject')} disabled={isLoading}
                    style={{
                      flex:1, display:'flex', alignItems:'center', justifyContent:'center', gap:8,
                      padding:'12px', borderRadius:12, fontWeight:700, fontSize:15, cursor:'pointer',
                      background:'rgba(239,68,68,0.1)', color:'#f87171',
                      border:'1px solid rgba(239,68,68,0.3)', fontFamily:'inherit',
                    }}>
                    <X size={18} />
                    Reject
                  </button>
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function RefreshIcon() {
  return <div style={{ width:16, height:16, border:'2px solid rgba(255,255,255,0.3)', borderTopColor:'#fff', borderRadius:'50%', animation:'spin 1s linear infinite' }} />
}
