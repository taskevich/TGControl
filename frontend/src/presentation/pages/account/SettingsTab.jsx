import {useState} from 'react'
import {useNavigate} from 'react-router-dom'
import {useServices} from '../../../application/services.jsx'
import {useToast} from '../../components/Toast.jsx'
import {Badge, SecretValue, Spinner} from '../../components/ui.jsx'
import ProxySelect from '../../components/ProxySelect.jsx'
import {NEW_PASSWORD_MIN_LENGTH} from '../../../domain/accounts.js'
import {fmtDate} from '../../../domain/format.js'
import {saveFile} from '../../download.js'
import {PROXY_BADGE, PROXY_STATUS, proxyLabel, proxyPayload} from '../../../domain/proxies.js'

export default function SettingsTab({account, onSaved}) {
    const toast = useToast()
    const navigate = useNavigate()
    const svc = useServices()
    const [form, setForm] = useState({
        notes: account.notes || '',
        api_id: account.api_id || '',
        api_hash: '',
        twofa: '',
    })
    const [proxySel, setProxySel] = useState({proxy_id: account.proxy_id || null, proxy: '', newMode: false})
    const [busy, setBusy] = useState(false)
    const [newPassword, setNewPassword] = useState('')
    const [pwBusy, setPwBusy] = useState(false)
    const [resetBusy, setResetBusy] = useState(false)
    const [downloadBusy, setDownloadBusy] = useState(false)
    const set = (k) => (e) => setForm((f) => ({...f, [k]: e.target.value}))

    const save = async (e) => {
        e.preventDefault()
        setBusy(true)
        const body = {...proxyPayload(proxySel), notes: form.notes}
        if (String(form.api_id) !== String(account.api_id || '') || form.api_hash) {
            body.api_id = form.api_id ? Number(form.api_id) : null
            if (form.api_hash) body.api_hash = form.api_hash
        }
        if (form.twofa) body.twofa = form.twofa
        try {
            const saved = await svc.accounts.update(account.id, body)
            onSaved(saved)
            setProxySel({proxy_id: saved.proxy_id || null, proxy: '', newMode: false})
            toast('Сохранено', 'success')
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setBusy(false)
        }
    }

    const setPassword = async (e) => {
        e.preventDefault()
        if (!window.confirm('Сменить облачный пароль 2FA этого аккаунта в Telegram?')) return
        setPwBusy(true)
        try {
            onSaved(await svc.accounts.setPassword(account.id, newPassword))
            setNewPassword('')
            toast('Пароль 2FA установлен', 'success')
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setPwBusy(false)
        }
    }

    const resetSessions = async () => {
        if (!window.confirm('Завершить все сеансы этого аккаунта в Telegram, кроме сеанса панели?')) return
        setResetBusy(true)
        try {
            const res = await svc.accounts.resetSessions(account.id)
            toast(res.detail, 'success')
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setResetBusy(false)
        }
    }

    const downloadSession = async () => {
        setDownloadBusy(true)
        try {
            saveFile(await svc.accounts.sessionFile(account.id))
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setDownloadBusy(false)
        }
    }

    const remove = async (logout) => {
        const msg = logout
            ? 'Завершить сессию в Telegram и удалить аккаунт из панели? Сессию будет невозможно восстановить.'
            : 'Удалить аккаунт из панели? Сессия в Telegram останется активной.'
        if (!window.confirm(msg)) return
        try {
            await svc.accounts.remove(account.id, logout)
            toast('Аккаунт удалён', 'success')
            navigate('/accounts')
        } catch (err) {
            toast(err.message, 'error')
        }
    }

    return (
        <div className="grid-2 gap">
            <form className="card pad stack" onSubmit={save}>
                <h3>Параметры подключения</h3>
                <ProxySelect
                    value={proxySel}
                    onChange={setProxySel}
                    hint="Все запросы аккаунта к Telegram идут через выбранный прокси. 'Без прокси' - прямое подключение."
                />
                {account.proxy && (
                    <div className="muted small">
                        Сейчас: {proxyLabel(account.proxy)} · <Badge
                        status={PROXY_BADGE[account.proxy.status]}>{PROXY_STATUS[account.proxy.status]}</Badge>
                        {account.proxy.latency_ms ? ` ${account.proxy.latency_ms} мс` : ''}
                    </div>
                )}
                <div className="grid-2">
                    <label className="field">
                        <span>API ID</span>
                        <input value={form.api_id} onChange={set('api_id')} placeholder="по умолчанию из .env"/>
                    </label>
                    <label className="field">
                        <span>API Hash</span>
                        <input value={form.api_hash} onChange={set('api_hash')}
                               placeholder={account.api_id ? '••• (задан)' : ''}/>
                    </label>
                </div>
                <label className="field">
                    <span>Известный пароль 2FA {account.has_2fa && <span className="muted">(сохранён)</span>} - только запомнить в панели</span>
                    <input type="password" value={form.twofa} onChange={set('twofa')}
                           placeholder="оставьте пустым, чтобы не менять"/>
                </label>
                <label className="field">
                    <span>Заметки</span>
                    <textarea rows={3} value={form.notes} onChange={set('notes')}/>
                </label>
                <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner/> : 'Сохранить'}</button>
            </form>
            <div className="card pad stack">
                <h3>Информация</h3>
                <dl className="kv">
                    <dt>ID в панели</dt>
                    <dd>{account.id}</dd>
                    <dt>Telegram ID</dt>
                    <dd>{account.tg_id || '-'}</dd>
                    <dt>Источник</dt>
                    <dd>{account.source || '-'}</dd>
                    <dt>Добавлен</dt>
                    <dd>{fmtDate(account.created_at)}</dd>
                    <dt>Проверен</dt>
                    <dd>{fmtDate(account.last_checked_at)}</dd>
                    <dt>Статус</dt>
                    <dd>{account.status} {account.status_detail && `- ${account.status_detail}`}</dd>
                    <dt>Пароль 2FA</dt>
                    <dd><SecretValue value={account.twofa} empty="не задан"/></dd>
                </dl>
                <h3>Установить пароль 2FA в Telegram</h3>
                <form className="row" onSubmit={setPassword}>
                    <input value={newPassword} minLength={NEW_PASSWORD_MIN_LENGTH}
                           onChange={(e) => setNewPassword(e.target.value)}
                           placeholder={`новый пароль, не менее ${NEW_PASSWORD_MIN_LENGTH} символов`} required/>
                    <button className="btn btn-primary"
                            disabled={pwBusy || newPassword.length < NEW_PASSWORD_MIN_LENGTH}>{pwBusy ?
                        <Spinner/> : 'Установить'}</button>
                </form>
                <h3>Сеансы</h3>
                <div className="muted small">
                    Выход со всех других устройств и приложений - останется только сеанс панели. Telegram запрещает
                    это в течение первых 24 часов после входа.
                </div>
                <div className="row">
                    <button className="btn btn-ghost" onClick={resetSessions} disabled={resetBusy}>
                        {resetBusy ? <Spinner/> : 'Завершить другие сеансы'}
                    </button>
                    <button className="btn btn-ghost" onClick={downloadSession} disabled={downloadBusy}
                            title="Файл Telethon .session с именем телефон_пароль2FA.session">
                        {downloadBusy ? <Spinner/> : 'Скачать .session'}
                    </button>
                </div>
                <h3>Удаление</h3>
                <div className="row">
                    <button className="btn btn-ghost" onClick={() => remove(false)}>Удалить из панели</button>
                    <button className="btn btn-danger" onClick={() => remove(true)}>Выйти из Telegram и удалить</button>
                </div>
            </div>
        </div>
    )
}
