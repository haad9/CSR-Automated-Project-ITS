import React, { useState } from 'react'
import axios from 'axios'
import { Play, RefreshCw, Eye, CheckCircle } from 'lucide-react'
import { API } from '../lib/constants'

const DEMO_STEPS = [
  { icon:'👁️',  label:'Monitor runs',         desc:'System detects certificates expiring soon' },
  { icon:'🔄',  label:'Workflows start',       desc:'Step Functions launches parallel renewals' },
  { icon:'📝',  label:'CSRs generated',        desc:'New private keys + signing requests created' },
  { icon:'✅',  label:'CA issues certs',       desc:'Pebble CA signs and returns certificates' },
  { icon:'🛡️', label:'Approval requested',    desc:'Security officer gets email notification' },
  { icon:'👤',  label:'Officer approves',      desc:'One click in the Approvals tab' },
  { icon:'🚀',  label:'Auto-deployed',         desc:'Cert pushed to Nginx via SSM — no SSH needed' },
  { icon:'🔍',  label:'Validated',             desc:'System confirms padlock is working' },
  { icon:'🎉',  label:'Done in ~90 seconds',   desc:'Full audit trail logged. Cert active again.' },
]

const sleep = ms => new Promise(r => setTimeout(r, ms))

export default function DemoPage({ certs, onNavigate, fetchData }) {
  const [running,    setRunning]    = useState(false)
  const [step,       setStep]       = useState(-1)
  const [executions, setExecutions] = useState([])
  const [done,       setDone]       = useState(false)
  const [error,      setError]      = useState(null)

  const demoCerts = certs.filter(c => c.demo_cert && c.state === 'Active').slice(0, 3)
  const canRun = demoCerts.length > 0

  const runDemo = async () => {
    setRunning(true)
    setStep(0)
    setDone(false)
    setError(null)
    setExecutions([])
    try {
      const resp = await axios.post(`${API}/demo/run`)
      setExecutions(resp.data.executions || [])
      for (let i = 0; i < DEMO_STEPS.length; i++) {
        setStep(i)
        await sleep(900)
        fetchData()
      }
      setDone(true)
      fetchData()
    } catch(e) {
      setError(e.message || 'Demo failed — check AWS connection')
    } finally {
      setRunning(false)
    }
  }

  const reset = () => {
    setStep(-1)
    setDone(false)
    setExecutions([])
    setError(null)
    fetchData()
  }

  return (
    <div style={{ padding:24, display:'flex', flexDirection:'column', gap:20 }} className="fade-up">

      {/* Accent bar */}
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
        <div style={{ width:3, height:24, borderRadius:99, background:'#f59e0b' }} />
        <span style={{ fontSize:12, color:'#f59e0b', fontWeight:600, letterSpacing:1 }}>DEMO MODE</span>
      </div>

      {/* Hero banner */}
      <div style={{ borderRadius:16, padding:'28px 24px', textAlign:'center', background:'linear-gradient(135deg,#1c1000,#0c1a4a)', border:'1px solid rgba(59,130,246,0.3)' }}>
        <div style={{ fontSize:52, marginBottom:12 }}>⚡</div>
        <h2 style={{ fontWeight:800, color:'#fff', fontSize:24, marginBottom:10 }}>One-Button Demo</h2>
        <p style={{ fontSize:15, color:'#93c5fd', maxWidth:520, margin:'0 auto', lineHeight:1.7 }}>
          Watch the system automatically renew {demoCerts.length > 0 ? demoCerts.length : 3} expiring certificates
          — from detection to live deployment — in about 90 seconds.
          <br />No commands. No SSH. Zero manual steps.
        </p>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20 }}>

        {/* Left: Steps walkthrough */}
        <div style={{ borderRadius:16, padding:20, background:'#0d0d1a', border:'1px solid #1a1a2e' }}>
          <h3 style={{ fontWeight:700, color:'#fff', fontSize:14, marginBottom:16 }}>What happens step by step</h3>
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {DEMO_STEPS.map((s, i) => {
              const isActive   = i === step
              const isComplete = done ? true : i < step
              return (
                <div key={i} style={{
                  display:'flex', alignItems:'center', gap:12, padding:'10px 14px', borderRadius:12,
                  transition:'all 0.4s ease',
                  background: isActive ? 'rgba(96,165,250,0.1)' : isComplete ? 'rgba(74,222,128,0.06)' : '#111118',
                  border: `1px solid ${isActive ? 'rgba(96,165,250,0.4)' : isComplete ? 'rgba(74,222,128,0.3)' : '#1e1e2e'}`,
                  transform: isActive ? 'translateX(4px)' : 'none',
                }}>
                  <div style={{ fontSize:18, width:28, textAlign:'center', flexShrink:0 }}>
                    {isComplete ? '✅' : s.icon}
                  </div>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ fontWeight:600, fontSize:13, color: isActive ? '#60a5fa' : isComplete ? '#4ade80' : '#9ca3af' }}>
                      {s.label}
                    </div>
                    <div style={{ fontSize:11, marginTop:2, color:'#4b5563' }}>{s.desc}</div>
                  </div>
                  {isActive && (
                    <div style={{ width:16, height:16, border:'2px solid rgba(96,165,250,0.3)', borderTopColor:'#60a5fa', borderRadius:'50%', flexShrink:0, animation:'spin 1s linear infinite' }} />
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Right: Controls */}
        <div style={{ display:'flex', flexDirection:'column', gap:16 }}>

          {/* Main button area */}
          <div style={{ borderRadius:16, padding:24, background:'#0d0d1a', border:'1px solid #1a1a2e' }}>
            {!running && !done && !error && (
              <>
                <button onClick={runDemo} disabled={!canRun}
                  style={{
                    width:'100%', padding:'16px', borderRadius:14, fontWeight:800, fontSize:18,
                    display:'flex', alignItems:'center', justifyContent:'center', gap:12,
                    background: canRun ? 'linear-gradient(135deg,#d97706,#f59e0b)' : '#1a1a2e',
                    color: canRun ? '#000' : '#4b5563',
                    border:'none', cursor: canRun ? 'pointer' : 'not-allowed', fontFamily:'inherit',
                    boxShadow: canRun ? '0 8px 30px rgba(217,119,6,0.4)' : 'none',
                    transition:'all 0.2s',
                  }}>
                  <Play size={22} />
                  Launch Full Demo
                </button>
                {!canRun && (
                  <div style={{ marginTop:12, padding:12, borderRadius:10, background:'#111118', color:'#6b7280', fontSize:13, textAlign:'center' }}>
                    No demo certs available. Seed the database first.
                  </div>
                )}
              </>
            )}

            {running && (
              <div style={{ textAlign:'center', padding:'8px 0' }}>
                <div style={{ width:48, height:48, border:'4px solid rgba(96,165,250,0.2)', borderTopColor:'#60a5fa', borderRadius:'50%', animation:'spin 1s linear infinite', margin:'0 auto 16px' }} />
                <div style={{ fontWeight:600, color:'#fff', fontSize:16 }}>Running demo...</div>
                <div style={{ fontSize:13, marginTop:6, color:'#60a5fa' }}>{DEMO_STEPS[step]?.label}</div>
              </div>
            )}

            {done && (
              <div style={{ textAlign:'center', padding:'8px 0' }} className="fade-up">
                <div style={{ fontSize:48, marginBottom:12 }}>🎉</div>
                <div style={{ fontWeight:700, color:'#fff', fontSize:18 }}>Demo Complete!</div>
                <div style={{ fontSize:14, marginTop:6, marginBottom:20, color:'#4ade80' }}>
                  All certificates renewed automatically
                </div>
                <div style={{ display:'flex', gap:10 }}>
                  <button onClick={() => onNavigate('certificates')}
                    style={{
                      flex:1, display:'flex', alignItems:'center', justifyContent:'center', gap:8,
                      padding:'10px', borderRadius:10, fontSize:13, fontWeight:600, cursor:'pointer',
                      background:'rgba(16,185,129,0.1)', color:'#4ade80',
                      border:'1px solid rgba(16,185,129,0.3)', fontFamily:'inherit',
                    }}>
                    <Eye size={14} /> View Certificates
                  </button>
                  <button onClick={reset}
                    style={{
                      flex:1, display:'flex', alignItems:'center', justifyContent:'center', gap:8,
                      padding:'10px', borderRadius:10, fontSize:13, fontWeight:600, cursor:'pointer',
                      background:'#111118', color:'#9ca3af',
                      border:'1px solid #1e1e2e', fontFamily:'inherit',
                    }}>
                    <RefreshCw size={14} /> Reset
                  </button>
                </div>
              </div>
            )}

            {error && (
              <div style={{ textAlign:'center', padding:'8px 0' }}>
                <div style={{ fontSize:36, marginBottom:8 }}>⚠️</div>
                <div style={{ fontSize:13, color:'#f87171', marginBottom:12 }}>{error}</div>
                <button onClick={reset}
                  style={{ padding:'8px 16px', borderRadius:10, fontSize:13, cursor:'pointer', background:'#111118', color:'#9ca3af', border:'1px solid #1e1e2e', fontFamily:'inherit' }}>
                  Try again
                </button>
              </div>
            )}
          </div>

          {/* Certs being renewed */}
          <div style={{ borderRadius:16, padding:16, background:'#0d0d1a', border:'1px solid #1a1a2e' }}>
            <div style={{ fontWeight:600, color:'#fff', fontSize:14, marginBottom:14 }}>Certificates in this demo</div>
            {demoCerts.length > 0 ? demoCerts.map((cert, i) => {
              const days = cert.expiry_date ? Math.ceil((new Date(cert.expiry_date) - new Date()) / 86400000) : null
              return (
                <div key={cert.cert_id} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'10px 0', borderBottom: i < demoCerts.length - 1 ? '1px solid #111118' : 'none' }}>
                  <div>
                    <div style={{ fontWeight:600, color:'#fff', fontSize:13 }}>{cert.domain}</div>
                    <div style={{ fontSize:11, color:'#6b7280', marginTop:2 }}>Currently: {cert.state}</div>
                  </div>
                  {days !== null && (
                    <div style={{ fontWeight:700, fontSize:14, color: days <= 7 ? '#ef4444' : '#f59e0b' }}>
                      {days}d left
                    </div>
                  )}
                </div>
              )
            }) : (
              <div style={{ fontSize:13, textAlign:'center', padding:'16px 0', color:'#6b7280' }}>No demo certs found</div>
            )}
          </div>

          {/* Execution links */}
          {executions.length > 0 && (
            <div style={{ borderRadius:16, padding:16, background:'#0d0d1a', border:'1px solid #1a1a2e' }}>
              <div style={{ fontWeight:600, color:'#fff', fontSize:13, marginBottom:10 }}>Live Step Functions executions</div>
              {executions.map((e, i) => (
                <div key={i} style={{ fontSize:12, padding:'4px 0', color:'#60a5fa' }}>
                  <span style={{ color:'#9ca3af' }}>→ </span>{e.domain}
                  <span style={{ marginLeft:8, color:'#4b5563', fontSize:10, fontFamily:'monospace' }}>
                    {e.execution_arn?.split(':').pop()?.slice(0, 30)}...
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* What this proves */}
      <div style={{ borderRadius:16, padding:20, background:'#0d0d1a', border:'1px solid #1a1a2e' }}>
        <h3 style={{ fontWeight:700, color:'#fff', fontSize:14, marginBottom:16, textAlign:'center' }}>What this proves to state agencies</h3>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12 }}>
          {[
            { icon:'🕐', title:'~90 seconds',      desc:'vs. 2+ hours manual per certificate' },
            { icon:'🔒', title:'Zero SSH',          desc:'No server access needed. All automated.' },
            { icon:'📋', title:'Full audit trail',  desc:'Every action logged with timestamps' },
            { icon:'🤖', title:'AI-powered',        desc:'Claude analyzes any failure instantly' },
          ].map(item => (
            <div key={item.title} style={{ textAlign:'center', padding:'16px 12px', borderRadius:14, background:'#111118', border:'1px solid #1e1e2e' }}>
              <div style={{ fontSize:28, marginBottom:8 }}>{item.icon}</div>
              <div style={{ fontWeight:700, color:'#fff', fontSize:13, marginBottom:4 }}>{item.title}</div>
              <div style={{ fontSize:12, color:'#6b7280', lineHeight:1.5 }}>{item.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
