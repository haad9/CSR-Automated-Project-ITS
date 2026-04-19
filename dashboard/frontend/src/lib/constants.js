export const API = import.meta.env.VITE_API_URL || 'https://cfdbtfo5pj.execute-api.us-east-1.amazonaws.com/prod'

export const STATE_META = {
  'Active':                { label: 'Secure',           color: '#4ade80', bg: 'rgba(74,222,128,0.08)', border: 'rgba(74,222,128,0.2)',  icon: '🔒', pct: 100, step: 0 },
  'Expiration Detected':   { label: 'Expiring Soon',    color: '#fb923c', bg: 'rgba(251,146,60,0.08)', border: 'rgba(251,146,60,0.2)',  icon: '⚠️',  pct: 10,  step: 1 },
  'Renewal Initiated':     { label: 'Auto-Renewing',    color: '#60a5fa', bg: 'rgba(96,165,250,0.08)', border: 'rgba(96,165,250,0.2)',  icon: '🔄', pct: 25,  step: 2 },
  'CSR Generated':         { label: 'Building Request', color: '#a78bfa', bg: 'rgba(167,139,250,0.08)',border: 'rgba(167,139,250,0.2)', icon: '📝', pct: 37,  step: 3 },
  'Certificate Issued':    { label: 'Cert Ready',       color: '#c084fc', bg: 'rgba(192,132,252,0.08)',border: 'rgba(192,132,252,0.2)', icon: '✅', pct: 50,  step: 4 },
  'Certificate Deployed':  { label: 'Installing',       color: '#22d3ee', bg: 'rgba(34,211,238,0.08)', border: 'rgba(34,211,238,0.2)',  icon: '🚀', pct: 75,  step: 5 },
  'Certificate Validated': { label: 'Verifying',        color: '#2dd4bf', bg: 'rgba(45,212,191,0.08)', border: 'rgba(45,212,191,0.2)',  icon: '🔍', pct: 87,  step: 6 },
  'Renewal Closed':        { label: 'Complete',         color: '#4ade80', bg: 'rgba(74,222,128,0.08)', border: 'rgba(74,222,128,0.2)',  icon: '🎉', pct: 100, step: 7 },
  'Exception':             { label: 'Needs Attention',  color: '#f87171', bg: 'rgba(248,113,113,0.08)',border: 'rgba(248,113,113,0.2)', icon: '🚨', pct: 0,   step: -1 },
}

export const PIPELINE_STEPS = [
  { key: 'Active',                label: 'Secure',         short: '🔒' },
  { key: 'Expiration Detected',   label: 'Expiring',       short: '⚠️'  },
  { key: 'Renewal Initiated',     label: 'Renewing',       short: '🔄' },
  { key: 'CSR Generated',         label: 'Building',       short: '📝' },
  { key: 'Certificate Issued',    label: 'Issued',         short: '✅' },
  { key: 'Certificate Deployed',  label: 'Deployed',       short: '🚀' },
  { key: 'Certificate Validated', label: 'Verified',       short: '🔍' },
  { key: 'Renewal Closed',        label: 'Done',           short: '🎉' },
]
