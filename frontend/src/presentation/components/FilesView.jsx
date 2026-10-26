import {useCallback, useEffect, useRef, useState} from 'react'
import {useServices} from '../../application/services.jsx'
import {useToast} from './Toast.jsx'
import {Empty, Spinner} from './ui.jsx'
import {MediaThumb, MediaViewer} from './MediaPreview.jsx'
import {useDebounced, useQuery} from '../../application/hooks.js'
import {accountLabel} from '../../domain/accounts.js'
import {MEDIA_KINDS, MEDIA_STATUSES, mergeById} from '../../domain/chats.js'
import {fmtBytes, fmtDate, fmtNum} from '../../domain/format.js'

const PAGE = 60

const STATUS_FILTERS = [
    ['stored', 'Сохранённые'],
    ['pending', 'В очереди'],
    ['not_stored', 'Не сохранённые'],
    ['any', 'Все'],
]

function FileCard({m, account, showAccount, onOpen, onRetry}) {
    const stored = m.media_status === 'stored'
    return (
        <div className="file-card">
            {stored ? (
                <MediaThumb m={m} onOpen={onOpen}/>
            ) : (
                <div className="media-thumb media-thumb-off">
          <span className={`media-status media-${m.media_status}`} title={m.media_error || ''}>
            {MEDIA_STATUSES[m.media_status] || m.media_status}
          </span>
                </div>
            )}
            <div className="file-card-body">
                <div className="clip" title={m.media_name || ''}>{m.media_name || MEDIA_KINDS[m.media] || m.media}</div>
                <div className="muted small clip">{MEDIA_KINDS[m.media] || m.media} · {fmtBytes(m.media_size)}</div>
                <div className="muted small clip" title={m.chat_title || ''}>{m.chat_title || m.chat_id}</div>
                <div className="muted small clip">
                    {fmtDate(m.date)}{showAccount ? ` · ${accountLabel(account)}` : ''}
                </div>
                {(m.media_status === 'failed' || m.media_status === 'too_large') && (
                    <button className="link-btn" onClick={() => onRetry(m)}
                            title={m.media_error || ''}>повторить</button>
                )}
            </div>
        </div>
    )
}

export default function FilesView({accountId = null}) {
    const toast = useToast()
    const svc = useServices()
    const [account, setAccount] = useState('')
    const [kind, setKind] = useState('')
    const [status, setStatus] = useState('stored')
    const [chat, setChat] = useState(null) // { account_id, chat_id, chat_title }
    const [qRaw, setQRaw] = useState('')
    const [items, setItems] = useState([])
    const [cursor, setCursor] = useState(null)
    const [loading, setLoading] = useState(true)
    const [viewing, setViewing] = useState(null) // index in the stored items
    const q = useDebounced(qRaw)
    const sentinel = useRef(null)
    const busy = useRef(false)
    const reqId = useRef(0)

    const effAccount = accountId || account || null
    const {data: accounts} = useQuery(() => svc.accounts.list(), [])
    const stats = useQuery(() => svc.media.stats(effAccount), [effAccount])
    const byId = Object.fromEntries((accounts || []).map((a) => [a.id, a]))

    const params = useCallback(
        (extra = {}) => ({
            account_id: chat?.account_id || effAccount,
            chat_id: chat?.chat_id,
            media_status: status,
            media_kind: kind,
            q,
            limit: PAGE,
            ...extra,
        }),
        [chat, effAccount, status, kind, q],
    )

    useEffect(() => {
        const id = ++reqId.current
        setLoading(true)
        setItems([])
        setCursor(null)
        svc.messages.feed(params())
            .then((res) => {
                if (id !== reqId.current) return
                setItems(res.items)
                setCursor(res.next_before_id ? {
                    before_date: res.next_before_date,
                    before_id: res.next_before_id
                } : null)
            })
            .catch((e) => toast(e.message, 'error'))
            .finally(() => id === reqId.current && setLoading(false))
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [params])

    const loadMore = useCallback(async () => {
        if (busy.current || !cursor) return
        busy.current = true
        const id = reqId.current
        try {
            const res = await svc.messages.feed(params(cursor))
            if (id !== reqId.current) return
            setItems((prev) => mergeById(prev, res.items))
            setCursor(res.next_before_id ? {before_date: res.next_before_date, before_id: res.next_before_id} : null)
        } catch (e) {
            toast(e.message, 'error')
        } finally {
            busy.current = false
        }
    }, [cursor, params, toast, svc])

    useEffect(() => {
        const el = sentinel.current
        if (!el) return undefined
        const obs = new IntersectionObserver((entries) => entries[0].isIntersecting && loadMore(), {rootMargin: '600px'})
        obs.observe(el)
        return () => obs.disconnect()
    }, [loadMore])

    const retry = async (m) => {
        try {
            const fresh = await svc.messages.retryMedia(m.id)
            setItems((prev) => prev.map((x) => (x.id === fresh.id ? fresh : x)))
            toast('Файл поставлен в очередь на сохранение', 'success')
        } catch (e) {
            toast(e.message, 'error')
        }
    }

    const viewable = items.filter((m) => m.media_status === 'stored' && m.media_url)
    const open = (m) => setViewing(viewable.findIndex((x) => x.id === m.id))
    const current = viewing !== null ? viewable[viewing] : null

    useEffect(() => {
        if (viewing !== null && viewing >= viewable.length - 3) loadMore()
    }, [viewing, viewable.length, loadMore])

    const s = stats.data
    const st = (k) => s?.statuses?.[k] || {count: 0, bytes: 0}
    const notStored = st('failed').count + st('too_large').count
    const total = Object.values(s?.statuses || {}).reduce((sum, x) => sum + x.count, 0)

    return (
        <div>
            {s && !s.enabled && (
                <div className="alert alert-error">
                    Хранилище файлов не настроено - задайте S3_BUCKET в .env. Ниже показаны только уже сохранённые
                    файлы.
                </div>
            )}
            <div className="stats-cards">
                <div className="stat-card"><span>Сохранено в S3</span><strong>{fmtNum(st('stored').count)}</strong>
                    <span className="muted small">{fmtBytes(st('stored').bytes)}</span></div>
                <div className="stat-card"><span>В очереди</span><strong>{fmtNum(st('pending').count)}</strong>
                    <span
                        className="muted small">{st('pending').bytes ? `≈ ${fmtBytes(st('pending').bytes)}` : ' '}</span>
                </div>
                <div className="stat-card"><span>Не сохранено</span><strong>{fmtNum(notStored)}</strong>
                    <span
                        className="muted small">ошибок {fmtNum(st('failed').count)} · больше {s ? fmtBytes(s.max_size) : '-'}: {fmtNum(st('too_large').count)}</span>
                </div>
                <div className="stat-card"><span>Всего файлов</span><strong>{fmtNum(total)}</strong>
                    <span
                        className="muted small">{total ? `сохранено ${Math.round((st('stored').count / total) * 100)}%` : ' '}</span>
                </div>
            </div>

            <div className="files-stats mt">
                <div className="card table-wrap">
                    <table className="table compact hover">
                        <thead>
                        <tr>
                            <th>Тип</th>
                            <th>Сохранено</th>
                            <th>Объём</th>
                            <th>В очереди</th>
                            <th>Не сохранено</th>
                            <th>Всего</th>
                        </tr>
                        </thead>
                        <tbody>
                        {(s?.kinds || []).map((k) => (
                            <tr key={k.kind} className={kind === k.kind ? 'row-active' : ''}
                                onClick={() => setKind(kind === k.kind ? '' : k.kind)}>
                                <td>{MEDIA_KINDS[k.kind] || k.kind}</td>
                                <td>{fmtNum(k.stored)}</td>
                                <td>{fmtBytes(k.stored_bytes)}</td>
                                <td>{fmtNum(k.pending)}</td>
                                <td>{fmtNum(k.failed + k.too_large)}</td>
                                <td>{fmtNum(k.total)}</td>
                            </tr>
                        ))}
                        {s && !s.kinds.length && <tr>
                            <td colSpan={6} className="muted">Файлов пока нет</td>
                        </tr>}
                        </tbody>
                    </table>
                </div>
                <div className="card table-wrap">
                    <table className="table compact hover">
                        <thead>
                        <tr>
                            <th>Чат (больше всего файлов)</th>
                            <th>Файлов</th>
                            <th>Объём</th>
                        </tr>
                        </thead>
                        <tbody>
                        {(s?.chats || []).map((c) => (
                            <tr key={`${c.account_id}:${c.chat_id}`} onClick={() => setChat(c)}
                                className={chat?.chat_id === c.chat_id && chat?.account_id === c.account_id ? 'row-active' : ''}>
                                <td className="clip-cell" title={c.chat_title || ''}>
                                    {c.chat_title || c.chat_id}
                                    {!effAccount &&
                                        <span className="muted small"> · {accountLabel(byId[c.account_id])}</span>}
                                </td>
                                <td>{fmtNum(c.count)}</td>
                                <td>{fmtBytes(c.bytes)}</td>
                            </tr>
                        ))}
                        {s && !s.chats.length && <tr>
                            <td colSpan={3} className="muted">Сохранённых файлов нет</td>
                        </tr>}
                        </tbody>
                    </table>
                </div>
                {!accountId && (s?.accounts || []).length > 0 && (
                    <div className="card table-wrap">
                        <table className="table compact hover">
                            <thead>
                            <tr>
                                <th>Аккаунт</th>
                                <th>Сохранено</th>
                                <th>Объём</th>
                                <th>В очереди</th>
                            </tr>
                            </thead>
                            <tbody>
                            {s.accounts.map((a) => (
                                <tr key={a.account_id} onClick={() => {
                                    setAccount(String(a.account_id));
                                    setChat(null)
                                }}
                                    className={String(a.account_id) === account ? 'row-active' : ''}>
                                    <td>{accountLabel(byId[a.account_id])}</td>
                                    <td>{fmtNum(a.stored)}</td>
                                    <td>{fmtBytes(a.bytes)}</td>
                                    <td>{fmtNum(a.pending)}</td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            <div className="toolbar mt">
                <input className="search" placeholder="Поиск: имя файла, подпись, чат" value={qRaw}
                       onChange={(e) => setQRaw(e.target.value)}/>
                {!accountId && (
                    <select value={account} onChange={(e) => {
                        setAccount(e.target.value);
                        setChat(null)
                    }}>
                        <option value="">Все аккаунты</option>
                        {(accounts || []).map((a) => <option key={a.id} value={a.id}>{accountLabel(a)}</option>)}
                    </select>
                )}
                <select value={kind} onChange={(e) => setKind(e.target.value)}>
                    <option value="">Все типы</option>
                    {Object.entries(MEDIA_KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
                <div className="seg">
                    {STATUS_FILTERS.map(([k, label]) => (
                        <button key={k} className={status === k ? 'active' : ''}
                                onClick={() => setStatus(k)}>{label}</button>
                    ))}
                </div>
                <button className="btn btn-ghost grow-right" onClick={() => stats.reload(true)}>Обновить статистику
                </button>
            </div>

            {chat && (
                <div className="row mb">
          <span className="chip">
            Чат: {chat.chat_title || chat.chat_id}
              <button className="btn-icon" onClick={() => setChat(null)} aria-label="Сбросить">×</button>
          </span>
                </div>
            )}

            <div className="files-grid">
                {items.map((m) => (
                    <FileCard key={m.id} m={m} account={byId[m.account_id]} showAccount={!accountId} onOpen={open}
                              onRetry={retry}/>
                ))}
            </div>
            {loading && <div className="pad center"><Spinner/></div>}
            {!loading && !items.length && <Empty>Файлов не найдено</Empty>}
            <div ref={sentinel}/>
            {cursor && !loading && <div className="pad center"><Spinner/></div>}

            {current && (
                <MediaViewer
                    m={current}
                    onClose={() => setViewing(null)}
                    onPrev={viewing > 0 ? () => setViewing(viewing - 1) : null}
                    onNext={viewing < viewable.length - 1 ? () => setViewing(viewing + 1) : null}
                />
            )}
        </div>
    )
}
