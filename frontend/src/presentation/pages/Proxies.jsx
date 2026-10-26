import {useState} from 'react'
import {useServices} from '../../application/services.jsx'
import Icon from '../components/Icon.jsx'
import {useToast} from '../components/Toast.jsx'
import {Badge, Empty, Modal, PageHeader, Spinner} from '../components/ui.jsx'
import {useQuery} from '../../application/hooks.js'
import {fmtDate} from '../../domain/format.js'
import {PROXY_BADGE, PROXY_STATUS} from '../../domain/proxies.js'

export default function Proxies() {
    const toast = useToast()
    const svc = useServices()
    const {data, loading, reload, setData} = useQuery(() => svc.proxies.list(), [])
    const [busy, setBusy] = useState({})
    const [checkingAll, setCheckingAll] = useState(false)
    const [modal, setModal] = useState(null) // 'add' | 'bulk' | 'assign' | proxy object (edit)

    const replace = (p) => setData((xs) => xs.map((x) => (x.id === p.id ? p : x)))
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

    const check = (p) =>
        run(p.id, async () => {
            const r = await svc.proxies.check(p.id)
            replace(r)
            toast(r.status === 'ok' ? `Прокси работает, ${r.latency_ms} мс` : `Не работает: ${r.status_detail}`, r.status === 'ok' ? 'success' : 'error')
        })

    const toggle = (p) =>
        run(p.id, async () => replace(await svc.proxies.update(p.id, {is_active: !p.is_active})))

    const remove = (p) => {
        const msg = p.accounts_count
            ? `Прокси привязан к ${p.accounts_count} аккаунт(ам). После удаления они будут работать БЕЗ прокси. Удалить?`
            : 'Удалить прокси?'
        if (!window.confirm(msg)) return
        run(p.id, async () => {
            await svc.proxies.remove(p.id, true)
            setData((xs) => xs.filter((x) => x.id !== p.id))
        })
    }

    const checkAll = async () => {
        setCheckingAll(true)
        try {
            const r = await svc.proxies.checkAll()
            toast(`Проверено ${r.checked}: работают ${r.ok}, не работают ${r.error}`, r.error ? 'error' : 'success')
            reload(true)
        } catch (e) {
            toast(e.message, 'error')
        } finally {
            setCheckingAll(false)
        }
    }

    return (
        <div>
            <PageHeader
                title="Прокси"
                subtitle="Прокси привязываются к аккаунтам: клиент Telegram аккаунта работает через свой прокси. Привязка необязательна - без прокси аккаунт подключается напрямую."
            >
                <button className="btn btn-ghost" onClick={checkAll} disabled={checkingAll || !data?.length}>
                    {checkingAll ? <Spinner/> : <Icon name="refresh"/>} Проверить все
                </button>
                <button className="btn btn-ghost" onClick={() => setModal('assign')} disabled={!data?.length}>
                    Привязать к аккаунтам
                </button>
                <button className="btn btn-ghost" onClick={() => setModal('bulk')}>Добавить списком</button>
                <button className="btn btn-primary" onClick={() => setModal('add')}>
                    <Icon name="plus"/> Добавить прокси
                </button>
            </PageHeader>

            <div className="card table-wrap">
                {loading ? (
                    <div className="pad"><Spinner/></div>
                ) : !data?.length ? (
                    <Empty>Прокси нет. Аккаунты работают без прокси.</Empty>
                ) : (
                    <table className="table">
                        <thead>
                        <tr>
                            <th>#</th>
                            <th>Прокси</th>
                            <th>Статус</th>
                            <th>Аккаунтов</th>
                            <th>Проверен</th>
                            <th/>
                        </tr>
                        </thead>
                        <tbody>
                        {data.map((p) => (
                            <tr key={p.id} className={p.is_active ? '' : 'row-disabled'}>
                                <td className="muted">{p.id}</td>
                                <td>
                                    {p.name && <strong className="block">{p.name}</strong>}
                                    <span className="mono small">{p.url_masked}</span>
                                </td>
                                <td>
                                    <Badge status={PROXY_BADGE[p.status]}>{PROXY_STATUS[p.status]}</Badge>
                                    {p.latency_ms != null && <span className="small">{p.latency_ms} мс</span>}
                                    {!p.is_active && <Badge status="disabled">Отключён</Badge>}
                                    {p.status_detail && <div className="muted small clip"
                                                             title={p.status_detail}>{p.status_detail}</div>}
                                </td>
                                <td>{p.accounts_count || <span className="muted">-</span>}</td>
                                <td className="small">{fmtDate(p.checked_at)}</td>
                                <td className="actions">
                                    <button className="btn btn-sm btn-ghost" disabled={busy[p.id]}
                                            onClick={() => check(p)}>
                                        {busy[p.id] ? <Spinner/> : 'Проверить'}
                                    </button>
                                    <button className="btn btn-sm btn-ghost" disabled={busy[p.id]}
                                            onClick={() => setModal(p)}>Изменить
                                    </button>
                                    <button className="btn btn-sm btn-ghost" disabled={busy[p.id]}
                                            onClick={() => toggle(p)}>
                                        {p.is_active ? 'Откл.' : 'Вкл.'}
                                    </button>
                                    <button className="btn-icon danger" title="Удалить" disabled={busy[p.id]}
                                            onClick={() => remove(p)}>
                                        <Icon name="trash"/>
                                    </button>
                                </td>
                            </tr>
                        ))}
                        </tbody>
                    </table>
                )}
            </div>
            <div className="muted small mt">
                Отключённый прокси не используется: привязанные к нему аккаунты не будут подключаться, пока прокси не
                включат или не отвяжут
                (чтобы аккаунт случайно не вышел в Telegram со своего IP).
            </div>

            {modal === 'add' && <ProxyForm onClose={() => setModal(null)} onSaved={() => {
                setModal(null);
                reload(true)
            }}/>}
            {modal && typeof modal === 'object' && (
                <ProxyForm proxy={modal} onClose={() => setModal(null)} onSaved={(p) => {
                    setModal(null);
                    replace(p)
                }}/>
            )}
            {modal === 'bulk' && <BulkForm onClose={() => setModal(null)} onSaved={() => {
                setModal(null);
                reload(true)
            }}/>}
            {modal === 'assign' && <AssignForm onClose={() => setModal(null)} onSaved={() => {
                setModal(null);
                reload(true)
            }}/>}
        </div>
    )
}

function ProxyForm({proxy, onClose, onSaved}) {
    const toast = useToast()
    const svc = useServices()
    const [url, setUrl] = useState('')
    const [name, setName] = useState(proxy?.name || '')
    const [busy, setBusy] = useState(false)
    const submit = async (e) => {
        e.preventDefault()
        setBusy(true)
        try {
            const p = proxy
                ? await svc.proxies.update(proxy.id, {name, ...(url.trim() ? {url: url.trim()} : {})})
                : await svc.proxies.create(url.trim(), name || null)
            if (!proxy) toast(p.status === 'ok' ? `Прокси добавлен и работает (${p.latency_ms} мс)` : `Прокси добавлен, но проверка не прошла: ${p.status_detail}`, p.status === 'ok' ? 'success' : 'error')
            onSaved(p)
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setBusy(false)
        }
    }
    return (
        <Modal title={proxy ? `Прокси #${proxy.id}` : 'Новый прокси'} onClose={onClose}>
            <form className="stack" onSubmit={submit}>
                <label className="field">
                    <span>Адрес {proxy &&
                        <span className="muted">- оставьте пустым, чтобы не менять ({proxy.url_masked})</span>}</span>
                    <input value={url} onChange={(e) => setUrl(e.target.value)}
                           placeholder="socks5://user:pass@host:port" autoFocus/>
                    <span className="muted small">Форматы: socks5://..., socks4://..., http://..., или host:port:user:pass (SOCKS5)</span>
                </label>
                <label className="field">
                    <span>Название <span className="muted">- необязательно</span></span>
                    <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Например: DE-1"/>
                </label>
                <button className="btn btn-primary" disabled={busy || (!proxy && !url.trim())}>{busy ?
                    <Spinner/> : 'Сохранить'}</button>
            </form>
        </Modal>
    )
}

function BulkForm({onClose, onSaved}) {
    const toast = useToast()
    const svc = useServices()
    const [text, setText] = useState('')
    const [busy, setBusy] = useState(false)
    const submit = async (e) => {
        e.preventDefault()
        setBusy(true)
        try {
            const r = await svc.proxies.createMany(text)
            toast(`Добавлено: ${r.created}, уже были: ${r.existing}${r.errors.length ? `, ошибок: ${r.errors.length}` : ''}`, r.errors.length ? 'error' : 'success')
            onSaved()
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setBusy(false)
        }
    }
    return (
        <Modal title="Добавить прокси списком" onClose={onClose}>
            <form className="stack" onSubmit={submit}>
                <label className="field">
                    <span>По одному на строку, после адреса через пробел можно указать название</span>
                    <textarea rows={10} className="mono" value={text} onChange={(e) => setText(e.target.value)}
                              placeholder={'socks5://user:pass@1.2.3.4:1080 DE-1\n5.6.7.8:1080:user:pass'}/>
                </label>
                <div className="muted small">После добавления нажмите «Проверить все».</div>
                <button className="btn btn-primary" disabled={busy || !text.trim()}>{busy ?
                    <Spinner/> : 'Добавить'}</button>
            </form>
        </Modal>
    )
}

function AssignForm({onClose, onSaved}) {
    const toast = useToast()
    const svc = useServices()
    const [max, setMax] = useState(1)
    const [onlyWorking, setOnlyWorking] = useState(true)
    const [busy, setBusy] = useState(false)
    const submit = async (e) => {
        e.preventDefault()
        setBusy(true)
        try {
            const r = await svc.proxies.assign(Number(max), onlyWorking)
            toast(`Привязано аккаунтов: ${r.assigned}${r.left_without_proxy ? `, осталось без прокси: ${r.left_without_proxy}` : ''}`, 'success')
            onSaved()
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setBusy(false)
        }
    }
    return (
        <Modal title="Привязать прокси к аккаунтам" onClose={onClose}>
            <form className="stack" onSubmit={submit}>
                <div className="muted small">
                    Аккаунтам без прокси будут назначены свободные прокси - сначала наименее загруженные. Уже
                    привязанные аккаунты не меняются.
                    Привязать конкретный прокси к конкретному аккаунту можно в настройках аккаунта.
                </div>
                <label className="field">
                    <span>Максимум аккаунтов на один прокси</span>
                    <input type="number" min="1" max="100" value={max} onChange={(e) => setMax(e.target.value)}/>
                </label>
                <label className="check-row">
                    <input type="checkbox" checked={onlyWorking} onChange={(e) => setOnlyWorking(e.target.checked)}/>
                    Только проверенные и работающие прокси
                </label>
                <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner/> : 'Привязать'}</button>
            </form>
        </Modal>
    )
}
