import {useState} from 'react'
import {Link} from 'react-router-dom'
import {useServices} from '../../../application/services.jsx'
import {useToast} from '../../components/Toast.jsx'
import {Spinner} from '../../components/ui.jsx'

function ActionCard({title, hint, children}) {
    return (
        <div className="card pad">
            <h3>{title}</h3>
            {hint && <div className="muted small mb">{hint}</div>}
            {children}
        </div>
    )
}

export default function ActionsTab({accountId}) {
    const toast = useToast()
    const svc = useServices()
    const [busy, setBusy] = useState('')
    const [target, setTarget] = useState('')
    const [sendTarget, setSendTarget] = useState('')
    const [sendText, setSendText] = useState('')
    const [postLink, setPostLink] = useState('')
    const [commentText, setCommentText] = useState('')
    const [joinIfNeeded, setJoinIfNeeded] = useState(true)
    const [last, setLast] = useState(null)

    const run = async (key, fn) => {
        setBusy(key)
        try {
            await fn()
        } catch (e) {
            toast(e.message, 'error')
        } finally {
            setBusy('')
        }
    }

    const joinLeave = (action) =>
        run(action, async () => {
            const res = await (action === 'join' ? svc.chats.join(accountId, target) : svc.chats.leave(accountId, target))
            toast(res.detail, res.status === 'ok' ? 'success' : 'info')
        })

    const sendTo = (e) => {
        e.preventDefault()
        run('send', async () => {
            const res = await svc.chats.sendTo(accountId, sendTarget, sendText)
            toast('Сообщение отправлено', 'success')
            setSendText('')
            setLast(res)
        })
    }

    const comment = (e) => {
        e.preventDefault()
        run('comment', async () => {
            const res = await svc.chats.comment(accountId, {
                post_link: postLink,
                text: commentText,
                join_if_needed: joinIfNeeded
            })
            toast('Комментарий оставлен', 'success')
            setCommentText('')
            setLast(res)
        })
    }

    return (
        <div className="grid-2 gap">
            <ActionCard title="Вступить / выйти" hint="@username, ссылка t.me/chat, инвайт t.me/+hash или ID чата">
                <div className="stack">
                    <input value={target} onChange={(e) => setTarget(e.target.value)}
                           placeholder="https://t.me/+AbCdEf..."/>
                    <div className="row">
                        <button className="btn btn-primary" disabled={!target.trim() || busy}
                                onClick={() => joinLeave('join')}>
                            {busy === 'join' ? <Spinner/> : 'Вступить'}
                        </button>
                        <button className="btn btn-danger" disabled={!target.trim() || busy}
                                onClick={() => joinLeave('leave')}>
                            {busy === 'leave' ? <Spinner/> : 'Выйти'}
                        </button>
                    </div>
                </div>
            </ActionCard>

            <ActionCard title="Написать в чат / пользователю"
                        hint="Если указать ссылку на сообщение - будет отправлен ответ на него">
                <form className="stack" onSubmit={sendTo}>
                    <input value={sendTarget} onChange={(e) => setSendTarget(e.target.value)}
                           placeholder="@chat, @user или t.me/chat/123"/>
                    <textarea rows={3} value={sendText} onChange={(e) => setSendText(e.target.value)}
                              placeholder="Текст сообщения"/>
                    <button className="btn btn-primary" disabled={!sendTarget.trim() || !sendText.trim() || busy}>
                        {busy === 'send' ? <Spinner/> : 'Отправить'}
                    </button>
                </form>
            </ActionCard>

            <ActionCard title="Комментарий к посту канала"
                        hint="Ссылка на пост: t.me/channel/123. Ссылка вида ...?comment=456 - ответ на конкретный комментарий">
                <form className="stack" onSubmit={comment}>
                    <input value={postLink} onChange={(e) => setPostLink(e.target.value)}
                           placeholder="https://t.me/channel/123"/>
                    <textarea rows={3} value={commentText} onChange={(e) => setCommentText(e.target.value)}
                              placeholder="Текст комментария"/>
                    <label className="check-row small">
                        <input type="checkbox" checked={joinIfNeeded}
                               onChange={(e) => setJoinIfNeeded(e.target.checked)}/>
                        вступить в группу обсуждения, если требуется
                    </label>
                    <button className="btn btn-primary" disabled={!postLink.trim() || !commentText.trim() || busy}>
                        {busy === 'comment' ? <Spinner/> : 'Комментировать'}
                    </button>
                </form>
            </ActionCard>

            {last && (
                <ActionCard title="Последнее отправленное">
                    <div className="quote">{last.message?.text}</div>
                    <div className="row small">
                        {last.link && <a href={last.link} target="_blank" rel="noreferrer">открыть в Telegram</a>}
                        {last.tracked_id && <Link to={`/stats/${last.tracked_id}`}>статистика</Link>}
                    </div>
                </ActionCard>
            )}
        </div>
    )
}
