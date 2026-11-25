import { Camera, Clock, FilePenLine, LoaderCircle, ScanFace, ShieldCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import api, { readableError } from '../services/api'

export default function AttendancePage() {
  const { employee, refresh } = useAuth(); const [records, setRecords] = useState([]); const [notice, setNotice] = useState(''); const [error, setError] = useState(''); const [reason, setReason] = useState(''); const [kind, setKind] = useState('check_in')
  const load = () => api.get('/attendance').then(({ data }) => setRecords(data.items)).catch((err) => setError(readableError(err)))
  useEffect(() => {
    load()
  }, [])
  const requestManual = async (event) => { event.preventDefault(); setError(''); try { const { data } = await api.post('/attendance/manual-request', { reason, kind }); setNotice(data.message); setReason('') } catch (err) { setError(readableError(err)) } }
  const consent = async () => { try { await api.post('/employees/me/biometric-consent', { consent: true }); await refresh(); setNotice('Biometric consent recorded. You can enrol your face template now.') } catch (err) { setError(readableError(err)) } }
  return <><section className="page-title"><div><p className="eyebrow">TIME & ATTENDANCE</p><h1>My attendance</h1><p>Verify your attendance with consent, or send a manual request for HR authorization.</p></div></section>{notice && <div className="alert success">{notice}</div>}{error && <div className="alert error">{error}</div>}<section className="attendance-top"><FaceCard hasConsent={Boolean(employee?.biometricConsentAt)} onConsent={consent} onDone={() => { setNotice('Attendance updated successfully.'); load() }} onError={setError} /><article className="panel manual-card"><div className="section-icon"><FilePenLine /></div><p className="eyebrow">FALLBACK METHOD</p><h2>Request manual attendance</h2><p>Your request is never treated as attendance until HR has reviewed and authorized it.</p><form onSubmit={requestManual}><label>Request type<select value={kind} onChange={(e) => setKind(e.target.value)}><option value="check_in">Check in</option><option value="check_out">Check out</option></select></label><label>Reason<textarea required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why do you need manual attendance?" /></label><button className="secondary-button">Submit for approval</button></form></article></section><section className="panel"><div className="panel-title"><div><h2>Attendance history</h2><p>Up to the latest 366 attendance records</p></div></div><div className="table-wrap"><table><thead><tr><th>Date</th><th>Check in</th><th>Check out</th><th>Work hours</th><th>Late</th><th>Status</th></tr></thead><tbody>{records.map((item) => <tr key={item.id}><td>{item.date}</td><td>{formattedTime(item.checkInAt)}</td><td>{formattedTime(item.checkOutAt)}</td><td>{item.workMinutes ? `${(item.workMinutes / 60).toFixed(1)} hrs` : '—'}</td><td>{item.lateMinutes ? `${item.lateMinutes} min` : '—'}</td><td><span className={`status ${item.status}`}>{item.status}</span></td></tr>)}{!records.length && <tr><td colSpan="6" className="empty-cell">No attendance records yet.</td></tr>}</tbody></table></div></section></>
}

function FaceCard({ hasConsent, onConsent, onDone, onError }) {
  const video = useRef(null); const stream = useRef(null); const [active, setActive] = useState(false); const [busy, setBusy] = useState(false); const [enrolled, setEnrolled] = useState(false)
  useEffect(() => () => stream.current?.getTracks().forEach((track) => track.stop()), [])
  const openCamera = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      onError('This browser does not support camera access. Use a current version of Chrome or Edge.')
      return
    }
    try {
      // Prefer a front-facing camera when the device exposes that information.
      // External USB webcams often do not, so fall back to any available camera.
      try {
        stream.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'user' } }, audio: false })
      } catch {
        stream.current = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      }
      video.current.srcObject = stream.current
      await video.current.play()
      setActive(true)
    } catch (err) {
      const reason = err?.name === 'NotReadableError'
        ? 'The camera is busy in another application. Close Camera, Zoom, Teams, or WhatsApp and try again.'
        : err?.name === 'NotAllowedError'
          ? 'Camera permission was blocked. Allow camera access for localhost:5173 in your browser settings, then refresh.'
          : 'Camera access could not be started. Check that the selected webcam is available, then try again.'
      onError(reason)
    }
  }
  const capture = () => { const canvas = document.createElement('canvas'); canvas.width = video.current.videoWidth; canvas.height = video.current.videoHeight; canvas.getContext('2d').drawImage(video.current, 0, 0); return canvas.toDataURL('image/jpeg', .9) }
  const frames = async () => { const values = []; for (let i = 0; i < 3; i += 1) { values.push(capture()); if (i < 2) await new Promise((resolve) => setTimeout(resolve, 750)) } return values }
  const enrol = async () => { if (!active) return openCamera(); setBusy(true); try { await api.post('/biometrics/enrol', { image: capture(), consentVersion: 'v1' }); setEnrolled(true) } catch (err) { onError(readableError(err)) } finally { setBusy(false) } }
  const verify = async (action) => { if (!active) return openCamera(); setBusy(true); try { const sequence = await frames(); await api.post('/biometrics/verify-attendance', { action, image: sequence[2], frames: sequence }); onDone() } catch (err) { onError(readableError(err)) } finally { setBusy(false) } }
  return <article className="panel face-card"><div className="section-icon"><ScanFace /></div><p className="eyebrow">SECURE BIOMETRICS</p><h2>Face verification</h2><p>Attendance is recorded only after a registered face match and basic multi-frame liveness signal. It never records an unverified match.</p>{!hasConsent ? <button className="secondary-button" onClick={onConsent}><ShieldCheck size={17} /> Give biometric consent</button> : <>{active ? <div className="camera"><video ref={video} autoPlay muted playsInline /><span><Camera size={15} /> Move slightly during capture</span></div> : <button className="secondary-button" onClick={openCamera}><Camera size={17} /> Open camera</button>}<div className="face-actions"><button className="outline-button" disabled={!active || busy} onClick={enrol}>{busy ? <LoaderCircle className="spin" size={16} /> : 'Enrol or update face'}</button><button className="primary-button" disabled={!active || busy} onClick={() => verify('check_in')}>Check in</button><button className="outline-button" disabled={!active || busy} onClick={() => verify('check_out')}>Check out</button></div><small className="privacy-note">Template is encrypted; you can withdraw consent, which deactivates your templates. Production deployments should use independently validated anti-spoofing.</small></>}</article>
}
function formattedTime(value) { return value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—' }
