import {Link} from 'react-router-dom'
import {Badge, Empty} from './ui.jsx'
import {accountLabel} from '../../domain/accounts.js'
import {fmtDate} from '../../domain/format.js'
import {linkify} from './text.jsx'

export default function CommentsList({items, accounts}) {
    if (!items?.length) return <Empty>Комментариев пока нет. Нажмите «Собрать комментарии».</Empty>
    const byId = Object.fromEntries((accounts || []).map((a) => [a.id, a]))
    return (
        <div className="comments">
            {items.map((c) => (
                <div key={c.id} className="comment">
                    <div className="comment-head">
                        <strong>{c.sender_name || c.sender_id || 'Аноним'}</strong>
                        {c.sender_username && (
                            <a className="muted small" href={`https://t.me/${c.sender_username}`} target="_blank"
                               rel="noreferrer">
                                @{c.sender_username}
                            </a>
                        )}
                        <Badge
                            status={c.kind === 'reply' ? 'active' : 'new'}>{c.kind === 'reply' ? 'ответ на сообщение' : 'упоминание'}</Badge>
                        {accounts && <span className="muted small">→ {accountLabel(byId[c.account_id])}</span>}
                        <span className="muted small grow-right">{fmtDate(c.date)}</span>
                    </div>
                    <div className="comment-text">{linkify(c.text) || <span className="muted">[медиа]</span>}</div>
                    <div className="muted small row">
                        <span>{c.chat_title}</span>
                        {c.link && (
                            <a href={c.link} target="_blank" rel="noreferrer">открыть в Telegram</a>
                        )}
                        {c.tracked_id && <Link to={`/stats/${c.tracked_id}`}>к сообщению</Link>}
                    </div>
                </div>
            ))}
        </div>
    )
}
