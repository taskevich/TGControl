import {useState} from 'react'
import {Link, useNavigate, useParams} from 'react-router-dom'
import {CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis} from 'recharts'
import {useServices} from '../../application/services.jsx'
import CommentsList from '../components/CommentsList.jsx'
import Icon from '../components/Icon.jsx'
import {useToast} from '../components/Toast.jsx'
import {Empty, PageHeader, Spinner} from '../components/ui.jsx'
import {useQuery} from '../../application/hooks.js'
import {accountLabel} from '../../domain/accounts.js'
import {fmtDate, fmtNum} from '../../domain/format.js'
import {linkify} from '../components/text.jsx'
import {chartColors} from './Stats.jsx'

export default function MessageDetail() {
    const {id} = useParams()
    const navigate = useNavigate()
    const toast = useToast()
    const svc = useServices()
    const [busy, setBusy] = useState(false)
    const {data: m, loading, reload} = useQuery(() => svc.stats.message(id), [id])
    const {data: accounts} = useQuery(() => svc.accounts.list(), [])

    if (loading && !m) return <Spinner/>
    if (!m) return <Empty>Сообщение не найдено</Empty>
    const account = (accounts || []).find((a) => a.id === m.account_id)

    const refresh = async () => {
        setBusy(true)
        try {
            await svc.stats.refresh({ids: [m.id]})
            await reload(true)
            toast('Статистика обновлена', 'success')
        } catch (e) {
            toast(e.message, 'error')
        } finally {
            setBusy(false)
        }
    }
    const remove = async () => {
        if (!window.confirm('Перестать отслеживать сообщение? История статистики будет удалена.')) return
        await svc.stats.untrack(m.id)
        navigate('/stats')
    }

    const history = m.snapshots.map((s) => ({...s, t: fmtDate(s.taken_at)}))

    return (
        <div>
            <PageHeader
                title={m.is_comment ? 'Комментарий' : 'Сообщение'}
                subtitle={<>{m.chat_title} · <Link
                    to={`/accounts/${m.account_id}`}>{accountLabel(account)}</Link> · {fmtDate(m.sent_at)}</>}
            >
                {m.link && <a className="btn btn-ghost" href={m.link} target="_blank" rel="noreferrer"><Icon
                    name="link"/> Открыть</a>}
                <button className="btn btn-primary" onClick={refresh} disabled={busy}>{busy ? <Spinner/> :
                    <Icon name="refresh"/>} Обновить
                </button>
                <button className="btn-icon danger" title="Не отслеживать" onClick={remove}><Icon name="trash"/>
                </button>
            </PageHeader>

            <div className="card pad">
                <div className="quote big">{linkify(m.text) || <span className="muted">[медиа]</span>}</div>
                {m.parent_link && <div className="small muted">Пост: <a href={m.parent_link} target="_blank"
                                                                        rel="noreferrer">{m.parent_link}</a></div>}
                {m.is_deleted && <div className="alert alert-error">Сообщение удалено или недоступно</div>}
                {m.refresh_error && <div className="alert alert-error">{m.refresh_error}</div>}
                <div className="muted small">Обновлено: {fmtDate(m.last_refreshed_at)}</div>
            </div>

            <div className="stats-cards mt">
                <div className="stat-card"><span>Просмотры</span><strong
                    style={{color: chartColors.views}}>{fmtNum(m.views)}</strong>{m.views == null &&
                    <span className="muted small">в группах Telegram не считает просмотры</span>}</div>
                <div className="stat-card"><span>Реакции</span><strong
                    style={{color: chartColors.reactions}}>{fmtNum(m.reactions_total)}</strong>
                    <span className="reactions-row">{m.reactions.map((r) => <span key={r.emoji}
                                                                                  className="reaction">{r.emoji} {r.count}</span>)}</span>
                </div>
                <div className="stat-card"><span>Комментарии / ответы</span><strong
                    style={{color: chartColors.replies}}>{fmtNum(m.replies_count)}</strong></div>
                <div className="stat-card"><span>Репосты</span><strong>{fmtNum(m.forwards)}</strong></div>
            </div>

            {history.length > 1 && (
                <div className="card pad mt">
                    <h3>Динамика</h3>
                    <ResponsiveContainer width="100%" height={240}>
                        <LineChart data={history}>
                            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false}/>
                            <XAxis dataKey="t" stroke="var(--muted)" fontSize={11}/>
                            <YAxis stroke="var(--muted)" fontSize={12}/>
                            <Tooltip contentStyle={{background: 'var(--panel-2)', border: '1px solid var(--border)'}}/>
                            <Legend/>
                            {m.views != null &&
                                <Line dataKey="views" name="Просмотры" stroke={chartColors.views} dot={false}
                                      strokeWidth={2}/>}
                            <Line dataKey="reactions_total" name="Реакции" stroke={chartColors.reactions} dot={false}
                                  strokeWidth={2}/>
                            <Line dataKey="replies_count" name="Комментарии" stroke={chartColors.replies} dot={false}
                                  strokeWidth={2}/>
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}

            <h2 className="mt">Комментарии к сообщению ({m.comments.length})</h2>
            <CommentsList items={m.comments}/>
        </div>
    )
}
