import {useEffect, useLayoutEffect, useRef, useState} from 'react'
import {useServices} from '../../../application/services.jsx'
import Icon from '../../components/Icon.jsx'
import {useToast} from '../../components/Toast.jsx'
import {Empty, Modal, Spinner} from '../../components/ui.jsx'
import {useInterval, useQuery} from '../../../application/hooks.js'
import {CHAT_TYPES, isChat as isGroupLike, mergeById, readAllSummary} from '../../../domain/chats.js'
import {fmtDate} from '../../../domain/format.js'
import {linkify} from '../../components/text.jsx'

export function MessageBubble({m, onReply, onReplies}) {
    if (m.is_service) {
        return <div className="msg-service">{m.text} · {fmtDate(m.date)}</div>
    }
    return (
        <div className={`msg${m.out ? ' msg-out' : ''}`}>
            <div className="msg-head">
                <strong>{m.out ? 'Вы' : m.sender_name || m.sender_id || 'Канал'}</strong>
                {m.sender_username && !m.out && <span className="muted small">@{m.sender_username}</span>}
                <span className="muted small">#{m.id}</span>
                {m.reply_to_msg_id && <span className="muted small">↪ ответ на #{m.reply_to_msg_id}</span>}
            </div>
            {m.media && <div className="media-tag">[{m.media}]</div>}
            {m.text && <div className="msg-text">{linkify(m.text)}</div>}
            <div className="msg-foot">
                <span className="muted small">{fmtDate(m.date)}</span>
                {m.views != null && <span className="stat"><Icon name="eye" size={14}/> {m.views}</span>}
                {m.reactions.map((r) => (
                    <span key={r.emoji} className="reaction">{r.emoji} {r.count}</span>
                ))}
                {m.replies != null && <span className="stat"><Icon name="comment" size={14}/> {m.replies}</span>}
                <span className="msg-actions">
          {onReply && <button className="link-btn" onClick={() => onReply(m)}>ответить</button>}
                    {onReplies && <button className="link-btn" onClick={() => onReplies(m)}>ответы</button>}
        </span>
            </div>
        </div>
    )
}

export default function ChatsTab({accountId}) {
    const toast = useToast()
    const svc = useServices()
    const [filter, setFilter] = useState('')
    const [typeFilter, setTypeFilter] = useState('')
    const [selected, setSelected] = useState(null)
    const [joinTarget, setJoinTarget] = useState('')
    const [joining, setJoining] = useState(false)
    const [reading, setReading] = useState(false)
    const dialogs = useQuery(() => svc.chats.dialogs(accountId), [accountId])

    const refreshDialogs = async () => {
        try {
            dialogs.setData(await svc.chats.dialogs(accountId, true))
        } catch (e) {
            toast(e.message, 'error')
        }
    }

    const readAll = async () => {
        setReading(true)
        try {
            const res = await svc.chats.readAll(accountId)
            toast(readAllSummary(res), res.errors ? 'error' : 'success')
            refreshDialogs()
        } catch (e) {
            toast(e.message, 'error')
        } finally {
            setReading(false)
        }
    }

    const join = async (e) => {
        e.preventDefault()
        setJoining(true)
        try {
            const res = await svc.chats.join(accountId, joinTarget)
            toast(res.detail, res.status === 'ok' ? 'success' : 'info')
            setJoinTarget('')
            refreshDialogs()
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setJoining(false)
        }
    }

    const unreadChats = (dialogs.data || []).filter((d) => d.unread > 0 || d.unread_mentions > 0).length
    const needle = filter.trim().toLowerCase()
    const list = (dialogs.data || []).filter(
        (d) =>
            (!typeFilter || d.type === typeFilter) &&
            (!needle || d.title.toLowerCase().includes(needle) || (d.username || '').toLowerCase().includes(needle)),
    )

    return (
        <div className="chats">
            <div className="chat-list card">
                <form className="join-row" onSubmit={join}>
                    <input placeholder="@chat или t.me/+invite" value={joinTarget}
                           onChange={(e) => setJoinTarget(e.target.value)}/>
                    <button className="btn btn-sm btn-primary" disabled={!joinTarget.trim() || joining}>
                        {joining ? <Spinner/> : 'Вступить'}
                    </button>
                </form>
                <div className="join-row">
                    <input placeholder="Поиск чата" value={filter} onChange={(e) => setFilter(e.target.value)}/>
                    <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                        <option value="">Все</option>
                        {Object.entries(CHAT_TYPES).map(([k, v]) => (
                            <option key={k} value={k}>{v}</option>
                        ))}
                    </select>
                    <button className="btn-icon" title="Обновить" onClick={refreshDialogs}>
                        <Icon name="refresh"/>
                    </button>
                </div>
                <div className="join-row">
                    <button
                        className="btn btn-sm btn-ghost grow"
                        onClick={readAll}
                        disabled={reading}
                        title="Отметить прочитанными все чаты аккаунта, включая архив, темы форумов, упоминания и реакции"
                    >
                        {reading ? <Spinner/> : <Icon name="eye" size={14}/>} Прочитать
                        все{unreadChats ? ` (${unreadChats})` : ''}
                    </button>
                </div>
                <div className="chat-items">
                    {dialogs.loading && <div className="pad"><Spinner/></div>}
                    {dialogs.error && <div className="alert alert-error">{dialogs.error.message}</div>}
                    {list.map((d) => (
                        <button key={d.id} className={`chat-item${selected?.id === d.id ? ' active' : ''}`}
                                onClick={() => setSelected(d)}>
                            <span className="avatar">{(d.title || '?').slice(0, 1).toUpperCase()}</span>
                            <span className="chat-item-body">
                <span className="chat-item-top">
                  <strong className="clip">{d.title || 'Без названия'}</strong>
                    {d.unread > 0 && <span className="unread">{d.unread}</span>}
                </span>
                <span className="muted small clip">
                  {CHAT_TYPES[d.type] || d.type}
                    {d.participants ? ` · ${d.participants}` : ''}
                    {d.is_admin ? ' · админ' : ''}
                    {!d.can_send && ' · 🔒'}
                </span>
                <span className="muted small clip">{d.last_text}</span>
              </span>
                        </button>
                    ))}
                    {!dialogs.loading && !list.length && <Empty>Чатов нет</Empty>}
                </div>
            </div>
            <div className="chat-pane card">
                {selected ? (
                    <ChatPane
                        key={selected.id}
                        accountId={accountId}
                        dialog={selected}
                        onLeft={() => {
                            setSelected(null)
                            refreshDialogs()
                        }}
                    />
                ) : (
                    <Empty>Выберите чат слева</Empty>
                )}
            </div>
        </div>
    )
}

const PAGE = 50
const POLL_MS = 5000

function ChatPane({accountId, dialog, onLeft}) {
    const toast = useToast()
    const svc = useServices()
    const [messages, setMessages] = useState([]) // newest first
    const [loadingOlder, setLoadingOlder] = useState(false)
    const [initial, setInitial] = useState(true)
    const [hasMore, setHasMore] = useState(true)
    const [live, setLive] = useState(true)
    const [text, setText] = useState('')
    const [replyTo, setReplyTo] = useState(null)
    const [track, setTrack] = useState(true)
    const [sending, setSending] = useState(false)
    const [repliesFor, setRepliesFor] = useState(null)
    const boxRef = useRef(null)
    const restoreRef = useRef(null) // keeps scroll position when older messages are prepended
    const busyRef = useRef(false)

    const nearBottom = () => {
        const el = boxRef.current
        return !el || el.scrollHeight - el.scrollTop - el.clientHeight < 120
    }
    const scrollToBottom = (smooth = false) =>
        requestAnimationFrame(() => {
            const el = boxRef.current
            if (el) el.scrollTo({top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto'})
        })

    // first page
    useEffect(() => {
        let cancelled = false
        ;(async () => {
            try {
                const res = await svc.chats.history(accountId, dialog.id, {limit: PAGE})
                if (cancelled) return
                setMessages(res)
                setHasMore(res.length === PAGE)
                scrollToBottom()
            } catch (e) {
                toast(e.message, 'error')
            } finally {
                if (!cancelled) setInitial(false)
            }
        })()
        return () => {
            cancelled = true
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dialog.id])

    // older messages – requested from Telegram while scrolling up, saved to DB on the server
    const loadOlder = async () => {
        if (busyRef.current || !hasMore || !messages.length) return
        busyRef.current = true
        setLoadingOlder(true)
        const el = boxRef.current
        restoreRef.current = el ? {height: el.scrollHeight, top: el.scrollTop} : null
        try {
            const oldest = messages[messages.length - 1].id
            const res = await svc.chats.history(accountId, dialog.id, {limit: PAGE, offsetId: oldest})
            setMessages((prev) => mergeById(prev, res))
            setHasMore(res.length === PAGE)
        } catch (e) {
            toast(e.message, 'error')
            restoreRef.current = null
        } finally {
            setLoadingOlder(false)
            busyRef.current = false
        }
    }

    useLayoutEffect(() => {
        const el = boxRef.current
        const r = restoreRef.current
        if (el && r) {
            el.scrollTop = el.scrollHeight - r.height + r.top
            restoreRef.current = null
        }
    }, [messages])

    // if the first pages don't fill the pane there is no scrollbar – keep loading
    useEffect(() => {
        const el = boxRef.current
        if (!initial && el && hasMore && messages.length && el.scrollHeight <= el.clientHeight + 10) loadOlder()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [messages, initial, hasMore])

    const onScroll = () => {
        const el = boxRef.current
        if (el && el.scrollTop < 150) loadOlder()
    }

    // fresh messages – RPC to Telegram with min_id = newest known message
    const pollNew = async () => {
        if (!messages.length || document.hidden) return
        try {
            const stick = nearBottom()
            const res = await svc.chats.newMessages(accountId, dialog.id, messages[0].id)
            if (!res.items.length) return
            setMessages((prev) => {
                const known = new Set(prev.map((m) => m.id))
                const fresh = res.items.filter((m) => !known.has(m.id))
                return fresh.length ? [...fresh, ...prev] : prev
            })
            if (stick) scrollToBottom(true)
        } catch {
            /* temporary errors are ignored while polling */
        }
    }
    useInterval(pollNew, POLL_MS, live && !initial)

    const send = async (e) => {
        e.preventDefault()
        setSending(true)
        try {
            const res = await svc.chats.send(accountId, dialog.id, {text, reply_to: replyTo?.id || null, track})
            setMessages((prev) => (prev.some((m) => m.id === res.message.id) ? prev : [res.message, ...prev]))
            setText('')
            setReplyTo(null)
            scrollToBottom(true)
            if (res.tracked_id) toast('Сообщение отправлено и добавлено в статистику', 'success')
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setSending(false)
        }
    }

    const leave = async () => {
        if (!window.confirm(`Выйти из «${dialog.title}»?`)) return
        try {
            const res = await svc.chats.leave(accountId, String(dialog.id))
            toast(res.detail, 'success')
            onLeft()
        } catch (e) {
            toast(e.message, 'error')
        }
    }

    const ordered = [...messages].reverse()
    const isChat = isGroupLike(dialog)

    return (
        <>
            <div className="chat-pane-head">
                <div>
                    <strong>{dialog.title}</strong>
                    <div className="muted small">
                        {CHAT_TYPES[dialog.type]} {dialog.username && `· @${dialog.username}`} · ID {dialog.id} ·
                        загружено {messages.length}
                    </div>
                </div>
                <div className="row">
                    <label className="check-row small" title="Запрашивать новые сообщения у Telegram каждые 5 секунд">
                        <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)}/>
                        {live && <span className="dot-online live"/>} новые
                    </label>
                    <button className="btn-icon" title="Проверить новые сейчас" onClick={pollNew}>
                        <Icon name="refresh"/>
                    </button>
                    {isChat && (
                        <button className="btn btn-sm btn-danger" onClick={leave}>
                            Выйти из чата
                        </button>
                    )}
                </div>
            </div>
            <div className="messages" ref={boxRef} onScroll={onScroll}>
                {loadingOlder && <div className="center"><Spinner/></div>}
                {!hasMore && messages.length > 0 && <div className="msg-service">Начало истории</div>}
                {initial && <div className="center"><Spinner/></div>}
                {!initial && !messages.length && <Empty>Сообщений нет</Empty>}
                {ordered.map((m) => (
                    <MessageBubble key={m.id} m={m} onReply={dialog.can_send ? setReplyTo : null}
                                   onReplies={setRepliesFor}/>
                ))}
            </div>
            {dialog.can_send ? (
                <form className="composer" onSubmit={send}>
                    {replyTo && (
                        <div className="reply-bar">
                            Ответ на #{replyTo.id}: <span className="clip">{replyTo.text}</span>
                            <button type="button" className="btn-icon" onClick={() => setReplyTo(null)}><Icon
                                name="close" size={14}/></button>
                        </div>
                    )}
                    <div className="composer-row">
            <textarea
                rows={2}
                placeholder="Сообщение... (Ctrl+Enter - отправить)"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (e.ctrlKey || e.metaKey) && text.trim() && send(e)}
            />
                        <button className="btn btn-primary" disabled={!text.trim() || sending}>
                            {sending ? <Spinner/> : <Icon name="send"/>}
                        </button>
                    </div>
                    <label className="check-row small">
                        <input type="checkbox" checked={track}
                               onChange={(e) => setTrack(e.target.checked)}/> отслеживать статистику
                    </label>
                </form>
            ) : (
                <div className="composer muted small">Отправка недоступна: {dialog.cant_send_reason}</div>
            )}
            {repliesFor && <RepliesModal accountId={accountId} peerId={dialog.id} msg={repliesFor}
                                         onClose={() => setRepliesFor(null)}/>}
        </>
    )
}

export function RepliesModal({accountId, peerId, msg, onClose}) {
    const svc = useServices()
    const {data, loading, error} = useQuery(
        () => svc.chats.replies(accountId, peerId, msg.id),
        [msg.id],
    )
    return (
        <Modal title={`Ответы на сообщение #${msg.id}`} onClose={onClose} wide>
            <div className="quote">{msg.text}</div>
            {loading && <Spinner/>}
            {error && <div className="alert alert-error">{error.message}</div>}
            {data && !data.length && <Empty>Ответов нет</Empty>}
            <div className="messages messages-plain">
                {(data || []).map((m) => (
                    <MessageBubble key={m.id} m={m}/>
                ))}
            </div>
        </Modal>
    )
}
