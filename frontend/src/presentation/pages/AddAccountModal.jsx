import {useState} from 'react'
import {useServices} from '../../application/services.jsx'
import {useToast} from '../components/Toast.jsx'
import {Badge, Modal, Spinner} from '../components/ui.jsx'
import {accountLabel} from '../../domain/accounts.js'
import ProxySelect from '../components/ProxySelect.jsx'
import {NO_PROXY, proxyPayload} from '../../domain/proxies.js'

function PhoneLogin({onAdded}) {
    const toast = useToast()
    const svc = useServices()
    const [step, setStep] = useState('phone')
    const [flowId, setFlowId] = useState(null)
    const [form, setForm] = useState({phone: '', api_id: '', api_hash: '', code: '', password: ''})
    const [proxySel, setProxySel] = useState(NO_PROXY)
    const [info, setInfo] = useState('')
    const [busy, setBusy] = useState(false)
    const [advanced, setAdvanced] = useState(false)
    const set = (k) => (e) => setForm((f) => ({...f, [k]: e.target.value}))

    const handle = (res) => {
        setFlowId(res.flow_id)
        setInfo(res.detail || '')
        setStep(res.step)
        if (res.step === 'done') {
            toast(`Аккаунт ${accountLabel(res.account)} добавлен`, 'success')
            onAdded()
        }
    }

    const submit = async (e) => {
        e.preventDefault()
        setBusy(true)
        try {
            if (step === 'phone') {
                handle(
                    await svc.accounts.loginStart({
                        phone: form.phone,
                        api_id: form.api_id ? Number(form.api_id) : null,
                        api_hash: form.api_hash || null,
                        ...proxyPayload(proxySel),
                        password: form.password || null,
                    }),
                )
            } else if (step === 'code') {
                handle(await svc.accounts.loginCode(flowId, form.code))
            } else if (step === 'password') {
                handle(await svc.accounts.loginPassword(flowId, form.password))
            }
        } catch (err) {
            toast(err.message, 'error')
            if (err.kind === 'expired') setStep('phone')
        } finally {
            setBusy(false)
        }
    }

    if (step === 'done') {
        return (
            <div className="stack">
                <div className="alert alert-success">{info}</div>
                <button className="btn btn-ghost" onClick={() => {
                    setStep('phone');
                    setForm({...form, phone: '', code: '', password: ''})
                }}>
                    Добавить ещё
                </button>
            </div>
        )
    }

    return (
        <form className="stack" onSubmit={submit}>
            <label className="field">
                <span>Номер телефона</span>
                <input value={form.phone} onChange={set('phone')} placeholder="+79991234567" disabled={step !== 'phone'}
                       autoFocus/>
            </label>
            {step === 'phone' && (
                <>
                    <label className="field">
                        <span>Пароль 2FA <span className="muted">- необязательно</span></span>
                        <input
                            type="password"
                            value={form.password}
                            onChange={set('password')}
                            placeholder="если включён облачный пароль"
                            autoComplete="new-password"
                        />
                        <span className="muted small">Если указать, вход завершится сразу после ввода кода; пароль сохранится в зашифрованном виде.</span>
                    </label>
                    <ProxySelect
                        value={proxySel}
                        onChange={setProxySel}
                        hint="Аккаунт будет работать через этот прокси. Без прокси клиент подключается к Telegram напрямую."
                    />
                    <button type="button" className="link-btn" onClick={() => setAdvanced(!advanced)}>
                        {advanced ? 'Скрыть' : 'Дополнительно: API ID / API Hash'}
                    </button>
                    {advanced && (
                        <div className="grid-2">
                            <label className="field">
                                <span>API ID</span>
                                <input value={form.api_id} onChange={set('api_id')} placeholder="из .env по умолчанию"/>
                            </label>
                            <label className="field">
                                <span>API Hash</span>
                                <input value={form.api_hash} onChange={set('api_hash')}/>
                            </label>
                        </div>
                    )}
                </>
            )}
            {info && <div className="alert">{info}</div>}
            {step === 'code' && (
                <label className="field">
                    <span>Код из Telegram / SMS</span>
                    <input value={form.code} onChange={set('code')} autoFocus inputMode="numeric"/>
                </label>
            )}
            {step === 'password' && (
                <label className="field">
                    <span>Облачный пароль (2FA)</span>
                    <input type="password" value={form.password} onChange={set('password')} autoFocus/>
                </label>
            )}
            <button className="btn btn-primary" disabled={busy}>
                {busy ? <Spinner/> : step === 'phone' ? 'Получить код' : 'Войти'}
            </button>
        </form>
    )
}

function ImportForm({mode, onAdded}) {
    const toast = useToast()
    const svc = useServices()
    const [files, setFiles] = useState([])
    const [strings, setStrings] = useState('')
    const [proxySel, setProxySel] = useState(NO_PROXY)
    const [twofa, setTwofa] = useState('')
    const [busy, setBusy] = useState(false)
    const [results, setResults] = useState(null)

    const submit = async (e) => {
        e.preventDefault()
        const px = proxyPayload(proxySel)
        setBusy(true)
        setResults(null)
        try {
            const res = await svc.accounts.importSessions({
                files,
                strings,
                proxyId: px.proxy_id,
                proxy: px.proxy,
                twofa
            })
            setResults(res)
            const ok = res.filter((r) => r.status !== 'error').length
            toast(`Импортировано: ${ok} из ${res.length}`, ok ? 'success' : 'error')
            if (ok) onAdded()
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setBusy(false)
        }
    }

    return (
        <form className="stack" onSubmit={submit}>
            {mode === 'files' ? (
                <>
                    <div className="muted small">
                        Поддерживаются файлы <b>.session</b> (Telethon и Pyrogram), парные <b>.json</b> с
                        app_id/app_hash/2FA/прокси,
                        <b> .zip</b>-архивы с ними и <b>.txt</b> со строковыми сессиями. Аккаунты будут проверены и
                        сохранены в БД.
                    </div>
                    <label className="dropzone">
                        <input type="file" multiple accept=".session,.json,.zip,.txt"
                               onChange={(e) => setFiles([...e.target.files])}/>
                        {files.length ? `Выбрано файлов: ${files.length}` : 'Нажмите, чтобы выбрать файлы'}
                    </label>
                </>
            ) : (
                <label className="field">
                    <span>Строковые сессии (Telethon или Pyrogram), по одной на строку</span>
                    <textarea rows={7} value={strings} onChange={(e) => setStrings(e.target.value)} className="mono"/>
                </label>
            )}
            <ProxySelect
                value={proxySel}
                onChange={setProxySel}
                label="Прокси для импортируемых аккаунтов"
                hint="Если прокси указан в .json аккаунта, используется он. Без прокси - прямое подключение."
            />
            <label className="field">
                <span>Пароль 2FA <span className="muted">- необязательно, для всех, у кого его нет в .json</span></span>
                <input type="password" value={twofa} onChange={(e) => setTwofa(e.target.value)}
                       autoComplete="new-password"/>
            </label>
            <button className="btn btn-primary" disabled={busy || (mode === 'files' ? !files.length : !strings.trim())}>
                {busy ? <><Spinner/> Проверяем сессии...</> : 'Импортировать'}
            </button>
            {results && (
                <table className="table compact">
                    <tbody>
                    {results.map((r, i) => (
                        <tr key={i}>
                            <td className="small clip">{r.name}</td>
                            <td><Badge
                                status={r.status === 'error' ? 'error' : 'active'}>{r.status === 'created' ? 'Добавлен' : r.status === 'updated' ? 'Обновлён' : 'Ошибка'}</Badge>
                            </td>
                            <td className="small">{r.detail}</td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            )}
        </form>
    )
}

export default function AddAccountModal({onClose, onAdded}) {
    const [tab, setTab] = useState('phone')
    return (
        <Modal title="Добавить аккаунт" onClose={onClose}>
            <div className="tabs">
                {[
                    ['phone', 'По номеру'],
                    ['files', 'Файлы сессий'],
                    ['strings', 'Строки сессий'],
                ].map(([k, l]) => (
                    <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{l}</button>
                ))}
            </div>
            {tab === 'phone' ? <PhoneLogin onAdded={onAdded}/> : <ImportForm key={tab} mode={tab} onAdded={onAdded}/>}
        </Modal>
    )
}
