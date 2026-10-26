import {useCallback, useEffect, useRef, useState} from 'react'
import {Link} from 'react-router-dom'
import {useServices} from '../../application/services.jsx'
import Icon from './Icon.jsx'
import {useToast} from './Toast.jsx'
import {Empty, Spinner} from './ui.jsx'
import {useDebounced, useInterval, useQuery} from '../../application/hooks.js'
import {accountLabel} from '../../domain/accounts.js'
import {CHAT_TYPES, MEDIA_STATUSES, downloadUrl, mergeById, senderTitle} from '../../domain/chats.js'
import {fmtBytes, fmtDate, fmtNum} from '../../domain/format.js'
import {linkify} from './text.jsx'
import {InlineMedia, MediaViewer} from './MediaPreview.jsx'

const PAGE = 50
const AUTO_MS = 30000

function MediaBlock({m, onChange, onOpen}) {
    const toast = useToast()
    const svc = useServices()
    const [busy, setBusy] = useState(false)

    const retry = async () => {
        setBusy(true)
        try {
            onChange(await svc.messages.retryMedia(m.id))
            toast('Файл поставлен в очередь на сохранение', 'success')
        } catch (e) {
            toast(e.message, 'error')
        } finally {
            setBusy(false)
        }
    }

    const st = m.media_status
    const stored = st === 'stored' && m.media_url
    return (
        <>
            {stored && <InlineMedia m={m} onOpen={onOpen}/>}
            <div className="media-tag media-row">
                <span>[{m.media}]</span>
                {m.media_name && <span className="clip">{m.media_name}</span>}
                {m.media_size != null && <span>{fmtBytes(m.media_size)}</span>}
                {st && st !== 'stored' && (
                    <span className={`media-status media-${st}`}
                          title={m.media_error || ''}>{MEDIA_STATUSES[st] || st}</span>
                )}
                {stored && <button className="link-btn" onClick={() => onOpen(m)}>открыть</button>}
                {stored && <a className="link-btn" href={downloadUrl(m)}>скачать</a>}
                {(st === 'failed' || st === 'too_large') && (
                    <button className="link-btn" onClick={retry} disabled={busy}>повторить</button>
                )}
            </div>
        </>
    )
}

function MessageCard({m, account, showAccount, onSender, onChat, onChange, onOpen}) {
    const u = m.tg_user
    return (
        <div className={`feed-msg${m.out ? ' feed-msg-out' : ''}`}>
            <div className="feed-msg-head">
                <button className="link-btn chat-link" onClick={() => onChat(m)} title="Только этот чат">
                    {m.chat_title || m.chat_id}
                </button>
                <span className="muted small">{CHAT_TYPES[m.chat_type] || m.chat_type}</span>
                {showAccount && (
                    <Link className="small" to={`/accounts/${m.account_id}`}>· {accountLabel(account)}</Link>
                )}
                <span className="muted small grow-right">{fmtDate(m.date)}{m.edit_date ? ' · изм.' : ''}</span>
            </div>
            <div className="feed-msg-sender">
                {m.sender_id && !m.out ? (
                    <button className="link-btn" onClick={() => onSender(m)} title="Все сообщения автора">
                        <strong>{senderTitle(m)}</strong>
                    </button>
                ) : (
                    <strong>{senderTitle(m)}</strong>
                )}
                {u?.username && <a className="muted small" href={`https://t.me/${u.username}`} target="_blank"
                                   rel="noreferrer">@{u.username}</a>}
                {u?.is_bot && <span className="tag">бот</span>}
                {u?.is_premium && <span className="tag">premium</span>}
                {m.reply_to_msg_id && <span className="muted small">↪ #{m.reply_to_msg_id}</span>}
            </div>
            {m.media && <MediaBlock m={m} onChange={onChange} onOpen={onOpen}/>}
            {m.text && <div className={`msg-text${m.is_service ? ' muted' : ''}`}>{linkify(m.text)}</div>}
            <div className="msg-foot">
                <span className="muted small">#{m.msg_id}</span>
                {m.views != null && <span className="stat"><Icon name="eye" size={14}/> {fmtNum(m.views)}</span>}
                {m.reactions.map((r) => <span key={r.emoji} className="reaction">{r.emoji} {r.count}</span>)}
                {m.replies != null && <span className="stat"><Icon name="comment" size={14}/> {m.replies}</span>}
                {m.link && (
                    <a className="small grow-right" href={m.link} target="_blank" rel="noreferrer">открыть в
                        Telegram</a>
                )}
            </div>
        </div>
    )
}

export default function MessagesFeed({accountId = null}) {
    const toast = useToast()
    const svc = useServices()
    const [account, setAccount] = useState(accountId ? String(accountId) : '')
    const [chat, setChat] = useState('') // "accountId:chatId"
    const [qRaw, setQRaw] = useState('')
    const [out, setOut] = useState('')
    const [chatType, setChatType] = useState('')
    const [sender, setSender] = useState(null)
    const [items, setItems] = useState([])
    const [cursor, setCursor] = useState(null)
    const [loading, setLoading] = useState(true)
    const [syncing, setSyncing] = useState(false)
    const [auto, setAuto] = useState(false)
    const [freshIds, setFreshIds] = useState(new Set())
    const [viewing, setViewing] = useState(null)
    const q = useDebounced(qRaw)
    const sentinel = useRef(null)
    const busy = useRef(false)
    const reqId = useRef(0)

    const effAccount = accountId || account || null
    const [chatAcc, chatId] = chat ? chat.split(':') : [null, null]

    const {data: accounts} = useQuery(() => svc.accounts.list(), [])
    const chats = useQuery(() => svc.messages.chats(effAccount), [effAccount])
    const summary = useQuery(() => svc.messages.summary(effAccount), [effAccount])
    const byId = Object.fromEntries((accounts || []).map((a) => [a.id, a]))

    const params = useCallback(
        (extra = {}) => ({
            account_id: chatAcc || effAccount,
            chat_id: chatId,
            sender_id: sender?.id,
            q,
            out,
            chat_type: chatType,
            limit: PAGE,
            ...extra,
        }),
        [chatAcc, chatId, effAccount, sender, q, out, chatType],
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
        const obs = new IntersectionObserver((entries) => entries[0].isIntersecting && loadMore(), {rootMargin: '400px'})
        obs.observe(el)
        return () => obs.disconnect()
    }, [loadMore])

    const pullFresh = async () => {
        const maxId = items.reduce((mx, m) => Math.max(mx, m.id), 0)
        if (!maxId) {
            const res = await svc.messages.feed(params())
            setItems(res.items)
            setCursor(res.next_before_id ? {before_date: res.next_before_date, before_id: res.next_before_id} : null)
            return res.items.length
        }
        const res = await svc.messages.feed(params({after_id: maxId, limit: 200}))
        if (res.items.length) {
            setItems((prev) => {
                const known = new Set(prev.map((m) => m.id))
                const fresh = res.items.filter((m) => !known.has(m.id))
                return [...fresh, ...prev].sort((a, b) => (b.date || '').localeCompare(a.date || '') || b.id - a.id)
            })
            setFreshIds(new Set(res.items.map((m) => m.id)))
        }
        return res.items.length
    }

    const sync = async (silent = false) => {
        if (syncing) return
        setSyncing(true)
        try {
            const res = await svc.messages.sync(effAccount ? Number(effAccount) : null, 50)
            await pullFresh()
            summary.reload(true)
            chats.reload(true)
            if (!silent || res.new) {
                toast(`Новых сообщений: ${res.new} в ${res.chats} чатах${res.errors ? `, ошибок: ${res.errors}` : ''}`, res.errors ? 'error' : 'success')
            }
        } catch (e) {
            if (!silent) toast(e.message, 'error')
        } finally {
            setSyncing(false)
        }
    }
    useInterval(() => !document.hidden && sync(true), AUTO_MS, auto)

    const s = summary.data
    return (
        <div>
            <div className="stats-cards">
                <div className="stat-card"><span>Сохранено сообщений</span><strong>{fmtNum(s?.messages)}</strong></div>
                <div className="stat-card"><span>Чатов</span><strong>{fmtNum(s?.chats)}</strong></div>
                <div className="stat-card"><span>Авторов (tg_user)</span><strong>{fmtNum(s?.users)}</strong></div>
                <div className="stat-card"><span>Последнее сообщение</span><strong
                    className="small-strong">{fmtDate(s?.last_date)}</strong></div>
                {s?.media_enabled && (
                    <div className="stat-card" title="Медиа и файлы сообщений в хранилище S3">
                        <span>Файлов в S3</span>
                        <strong>{fmtNum(s.media_stored)}</strong>
                        <span
                            className="muted small">{fmtBytes(s.media_bytes)}{s.media_pending ? ` · в очереди ${fmtNum(s.media_pending)}` : ''}</span>
                    </div>
                )}
            </div>

            <div className="toolbar mt">
                <input className="search" placeholder="Поиск: текст, автор, чат" value={qRaw}
                       onChange={(e) => setQRaw(e.target.value)}/>
                {!accountId && (
                    <select value={account} onChange={(e) => {
                        setAccount(e.target.value);
                        setChat('')
                    }}>
                        <option value="">Все аккаунты</option>
                        {(accounts || []).map((a) => <option key={a.id} value={a.id}>{accountLabel(a)}</option>)}
                    </select>
                )}
                <select value={chat} onChange={(e) => setChat(e.target.value)} className="select-wide">
                    <option value="">Все чаты</option>
                    {(chats.data || []).map((c) => (
                        <option key={`${c.account_id}:${c.chat_id}`} value={`${c.account_id}:${c.chat_id}`}>
                            {c.chat_title || c.chat_id} ({c.count}){!effAccount ? ` - ${accountLabel(byId[c.account_id])}` : ''}
                        </option>
                    ))}
                </select>
                <select value={chatType} onChange={(e) => setChatType(e.target.value)}>
                    <option value="">Любой тип</option>
                    {Object.entries(CHAT_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
                <select value={out} onChange={(e) => setOut(e.target.value)}>
                    <option value="">Все авторы</option>
                    <option value="false">Входящие</option>
                    <option value="true">Наши аккаунты</option>
                </select>
                <span className="grow-right row">
          <label className="check-row small" title="Каждые 30 секунд запрашивать новые сообщения у Telegram">
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)}/>
              {auto && <span className="dot-online live"/>} автообновление
          </label>
          <button className="btn btn-primary" onClick={() => sync(false)} disabled={syncing}>
            {syncing ? <Spinner/> : <Icon name="refresh"/>} Получить новые
          </button>
        </span>
            </div>

            {(sender || chat) && (
                <div className="row mb">
                    {sender && (
                        <span className="chip">
              Автор: {sender.name}
                            <button className="btn-icon" onClick={() => setSender(null)}><Icon name="close" size={12}/></button>
            </span>
                    )}
                    {chat && (
                        <span className="chip">
              Чат: {(chats.data || []).find((c) => `${c.account_id}:${c.chat_id}` === chat)?.chat_title || chatId}
                            <button className="btn-icon" onClick={() => setChat('')}><Icon name="close"
                                                                                           size={12}/></button>
            </span>
                    )}
                </div>
            )}

            <div className="feed">
                {items.map((m) => (
                    <div key={m.id} className={freshIds.has(m.id) ? 'fresh' : ''}>
                        <MessageCard
                            m={m}
                            account={byId[m.account_id]}
                            showAccount={!accountId}
                            onSender={(x) => setSender({id: x.sender_id, name: senderTitle(x)})}
                            onChat={(x) => setChat(`${x.account_id}:${x.chat_id}`)}
                            onChange={(x) => setItems((prev) => prev.map((y) => (y.id === x.id ? x : y)))}
                            onOpen={setViewing}
                        />
                    </div>
                ))}
                {loading && <div className="pad center"><Spinner/></div>}
                {!loading && !items.length && (
                    <Empty>
                        Сохранённых сообщений нет. Откройте чат на вкладке «Чаты» аккаунта (сообщения сохраняются при
                        прокрутке) или нажмите «Получить новые».
                    </Empty>
                )}
                <div ref={sentinel}/>
                {cursor && !loading && <div className="pad center"><Spinner/></div>}
                {!cursor && !loading && items.length > 0 &&
                    <div className="muted small center pad">Больше сообщений нет</div>}
            </div>
            {viewing && <MediaViewer m={viewing} onClose={() => setViewing(null)}/>}
        </div>
    )
}
