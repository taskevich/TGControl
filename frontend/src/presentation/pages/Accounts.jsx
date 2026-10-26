import {useState} from 'react'
import {Link} from 'react-router-dom'
import {useServices} from '../../application/services.jsx'
import Icon from '../components/Icon.jsx'
import {useToast} from '../components/Toast.jsx'
import {Badge, Empty, Modal, PageHeader, SecretValue, Spinner} from '../components/ui.jsx'
import {useQuery} from '../../application/hooks.js'
import {
    ACCOUNT_STATUSES,
    NEW_PASSWORD_MIN_LENGTH,
    STATUS_LABELS,
    accountInitial,
    accountLabel,
    matchesAccount
} from '../../domain/accounts.js'
import {fmtDate} from '../../domain/format.js'
import {readAllSummary} from '../../domain/chats.js'
import AddAccountModal from './AddAccountModal.jsx'
import {proxyLabel} from '../../domain/proxies.js'

export default function Accounts() {
    const toast = useToast()
    const svc = useServices()
    const [status, setStatus] = useState('')
    const [q, setQ] = useState('')
    const [adding, setAdding] = useState(false)
    const [busy, setBusy] = useState({})
    const [checkingAll, setCheckingAll] = useState(false)
    const [readingAll, setReadingAll] = useState(false)
    const [settingPassword, setSettingPassword] = useState(false)
    const {data, loading, reload, setData} = useQuery(() => svc.accounts.list(status), [status])

    const replace = (acc) => setData((xs) => xs.map((x) => (x.id === acc.id ? acc : x)))

    const run = async (id, fn) => {
        setBusy((b) => ({...b, [id]: true}))
        try {
            await fn()
        } catch (e) {
            toast(e.message, 'error')
        } finally {
            setBusy((b) => ({...b, [id]: false}))
        }
    }

    const check = (a) =>
        run(a.id, async () => {
            const acc = await svc.accounts.check(a.id)
            replace(acc)
            toast(`${accountLabel(acc)}: ${STATUS_LABELS[acc.status]}`, acc.status === 'active' ? 'success' : 'error')
        })

    const toggle = (a) =>
        run(a.id, async () => replace(await svc.accounts.update(a.id, {is_enabled: !a.is_enabled})))

    const remove = (a) => {
        if (!window.confirm(`Удалить аккаунт ${accountLabel(a)} из панели?`)) return
        run(a.id, async () => {
            await svc.accounts.remove(a.id)
            setData((xs) => xs.filter((x) => x.id !== a.id))
        })
    }

    const checkAll = async () => {
        setCheckingAll(true)
        try {
            const list = await svc.accounts.checkAll()
            setData(status ? list.filter((a) => a.status === status) : list)
            toast('Проверка завершена', 'success')
        } catch (e) {
            toast(e.message, 'error')
        } finally {
            setCheckingAll(false)
        }
    }

    const readAll = async () => {
        if (!window.confirm('Отметить прочитанными все сообщения во всех активных аккаунтах?')) return
        setReadingAll(true)
        try {
            const res = await svc.messages.readAll()
            toast(readAllSummary(res), res.errors ? 'error' : 'success')
        } catch (e) {
            toast(e.message, 'error')
        } finally {
            setReadingAll(false)
        }
    }

    const needle = q.trim().toLowerCase()
    const rows = (data || []).filter((a) => matchesAccount(a, needle))

    return (
        <div>
            <PageHeader title="Аккаунты" subtitle="Telegram-аккаунты, сохранённые в базе">
                <button className="btn btn-ghost" onClick={checkAll} disabled={checkingAll}>
                    {checkingAll ? <Spinner/> : <Icon name="refresh"/>} Проверить все
                </button>
                <button className="btn btn-ghost" onClick={readAll} disabled={readingAll}
                        title="Архив, темы форумов, упоминания и реакции тоже отмечаются прочитанными">
                    {readingAll ? <Spinner/> : <Icon name="eye"/>} Прочитать все
                </button>
                <button className="btn btn-ghost" onClick={() => setSettingPassword(true)}>
                    <Icon name="key"/> Пароль 2FA всем
                </button>
                <button className="btn btn-primary" onClick={() => setAdding(true)}>
                    <Icon name="plus"/> Добавить аккаунт
                </button>
            </PageHeader>

            <div className="toolbar">
                <input className="search" placeholder="Поиск: телефон, username, имя..." value={q}
                       onChange={(e) => setQ(e.target.value)}/>
                <select value={status} onChange={(e) => setStatus(e.target.value)}>
                    <option value="">Все статусы</option>
                    {ACCOUNT_STATUSES.map((s) => (
                        <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                    ))}
                </select>
            </div>

            <div className="card table-wrap">
                {loading ? (
                    <div className="pad"><Spinner/></div>
                ) : !rows.length ? (
                    <Empty>Аккаунтов нет. Нажмите «Добавить аккаунт».</Empty>
                ) : (
                    <table className="table">
                        <thead>
                        <tr>
                            <th>#</th>
                            <th>Аккаунт</th>
                            <th>Телефон</th>
                            <th>Статус</th>
                            <th>Пароль 2FA</th>
                            <th>Прокси</th>
                            <th>Проверен</th>
                            <th/>
                        </tr>
                        </thead>
                        <tbody>
                        {rows.map((a) => (
                            <tr key={a.id} className={a.is_enabled ? '' : 'row-disabled'}>
                                <td className="muted">{a.id}</td>
                                <td>
                                    <Link to={`/accounts/${a.id}`} className="acc-cell">
                                        <span className="avatar">{accountInitial(a)}</span>
                                        <span>
                        <strong>{accountLabel(a)}</strong>
                        <span className="muted small block">
                          {a.username ? `@${a.username}` : 'без username'} {a.has_2fa && '· 2FA'}
                            {a.connected && <span className="dot-online" title="Подключён"/>}
                        </span>
                      </span>
                                    </Link>
                                </td>
                                <td className="mono">{a.phone || '-'}</td>
                                <td>
                                    <Badge status={a.status}/>
                                    {!a.is_enabled && <Badge status="disabled">Отключён</Badge>}
                                    {a.status_detail && <div className="muted small clip"
                                                             title={a.status_detail}>{a.status_detail}</div>}
                                </td>
                                <td className="small"><SecretValue value={a.twofa}/></td>
                                <td className="small">
                                    {a.proxy ? (
                                        <span className="clip" title={proxyLabel(a.proxy)}>
                        <span className={`dot-status dot-${a.proxy.is_active ? a.proxy.status : 'off'}`}/>
                                            {a.proxy.name || `${a.proxy.host}:${a.proxy.port}`}
                      </span>
                                    ) : (
                                        <span className="muted">без прокси</span>
                                    )}
                                </td>
                                <td className="small">{fmtDate(a.last_checked_at)}</td>
                                <td className="actions">
                                    <Link className="btn btn-sm btn-primary" to={`/accounts/${a.id}`}>Чаты</Link>
                                    <button className="btn btn-sm btn-ghost" disabled={busy[a.id]}
                                            onClick={() => check(a)}>
                                        {busy[a.id] ? <Spinner/> : 'Проверить'}
                                    </button>
                                    <button className="btn btn-sm btn-ghost" disabled={busy[a.id]}
                                            onClick={() => toggle(a)}>
                                        {a.is_enabled ? 'Откл.' : 'Вкл.'}
                                    </button>
                                    <button className="btn-icon danger" title="Удалить" disabled={busy[a.id]}
                                            onClick={() => remove(a)}>
                                        <Icon name="trash"/>
                                    </button>
                                </td>
                            </tr>
                        ))}
                        </tbody>
                    </table>
                )}
            </div>

            {settingPassword && (
                <SetPasswordAllModal
                    onClose={() => setSettingPassword(false)}
                    onDone={() => reload(true)}
                />
            )}

            {adding && (
                <AddAccountModal
                    onClose={() => setAdding(false)}
                    onAdded={() => reload(true)}
                />
            )}
        </div>
    )
}

function SetPasswordAllModal({onClose, onDone}) {
    const toast = useToast()
    const svc = useServices()
    const [password, setPassword] = useState('')
    const [busy, setBusy] = useState(false)
    const [results, setResults] = useState(null)

    const submit = async (e) => {
        e.preventDefault()
        if (!window.confirm('Сменить облачный пароль 2FA в Telegram у всех включённых активных аккаунтов?')) return
        setBusy(true)
        try {
            const res = await svc.accounts.setPasswordAll(password)
            setResults(res)
            const ok = res.filter((r) => r.status === 'ok').length
            toast(`Пароль установлен: ${ok} из ${res.length}`, ok === res.length ? 'success' : 'error')
            onDone()
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setBusy(false)
        }
    }

    return (
        <Modal title="Пароль 2FA всем аккаунтам" onClose={onClose}>
            <form className="stack" onSubmit={submit}>
                <label className="field">
                    <span>Новый пароль (не менее {NEW_PASSWORD_MIN_LENGTH} символов)</span>
                    <input value={password} minLength={NEW_PASSWORD_MIN_LENGTH}
                           onChange={(e) => setPassword(e.target.value)} autoFocus required/>
                </label>
                <div className="muted small">
                    Пароль меняется в Telegram у всех включённых аккаунтов в статусе «Активен» / «Новый». Если у
                    аккаунта уже
                    есть пароль 2FA, используется сохранённый в панели текущий пароль.
                </div>
                <button className="btn btn-primary" disabled={busy || password.length < NEW_PASSWORD_MIN_LENGTH}>{busy ?
                    <Spinner/> : 'Установить'}</button>
            </form>
            {results && (
                <table className="table">
                    <tbody>
                    {results.map((r) => (
                        <tr key={r.account_id}>
                            <td>{r.label}</td>
                            <td><Badge status={r.status === 'ok' ? 'ok' : 'error'}/></td>
                            <td className="small">{r.detail}</td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            )}
        </Modal>
    )
}
