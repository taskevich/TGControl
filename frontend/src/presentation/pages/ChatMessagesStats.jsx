import {useState} from 'react'
import {Link} from 'react-router-dom'
import {Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis} from 'recharts'
import {useServices} from '../../application/services.jsx'
import Icon from '../components/Icon.jsx'
import {Empty, Spinner} from '../components/ui.jsx'
import {useQuery} from '../../application/hooks.js'
import {accountLabel} from '../../domain/accounts.js'
import {CHAT_TYPES} from '../../domain/chats.js'
import {fmtDate, fmtNum} from '../../domain/format.js'
import {linkify} from '../components/text.jsx'

const COLORS = {incoming: '#7c8cff', outgoing: '#2aa3ef', reactions: '#f5a524', replies: '#22c55e'}
const PERIODS = [[1, '24 ч'], [7, '7 дней'], [14, '14 дней'], [30, '30 дней'], [90, '90 дней']]

export default function ChatMessagesStats({accountId, accounts}) {
    const svc = useServices()
    const [days, setDays] = useState(14)
    const {data: s, loading, error} = useQuery(
        () => svc.stats.chatMessages(accountId, days),
        [accountId, days],
    )
    const byId = Object.fromEntries((accounts || []).map((a) => [a.id, a]))

    if (loading && !s) return <Spinner/>
    if (error) return <div className="alert alert-error">{error.message}</div>
    if (!s) return null
    const t = s.totals

    return (
        <div>
            <div className="toolbar">
                <div className="seg">
                    {PERIODS.map(([d, l]) => (
                        <button key={d} className={days === d ? 'active' : ''} onClick={() => setDays(d)}>{l}</button>
                    ))}
                </div>
                {loading && <Spinner/>}
                <span className="muted small grow-right">
          Считается по сообщениям, сохранённым в базе.{' '}
                    <Link to="/messages">Все сообщения →</Link>
        </span>
            </div>

            {!t.messages ? (
                <Empty>
                    За период нет сохранённых сообщений. Откройте чаты аккаунтов или нажмите «Получить новые» в разделе
                    «Все сообщения».
                </Empty>
            ) : (
                <>
                    <div className="stats-cards">
                        <div className="stat-card"><span>Сообщений</span><strong>{fmtNum(t.messages)}</strong></div>
                        <div className="stat-card"><span>Входящие</span><strong
                            style={{color: COLORS.incoming}}>{fmtNum(t.incoming)}</strong></div>
                        <div className="stat-card"><span>Исходящие (наши)</span><strong
                            style={{color: COLORS.outgoing}}>{fmtNum(t.outgoing)}</strong></div>
                        <div className="stat-card"><span>Чатов</span><strong>{fmtNum(t.chats)}</strong></div>
                        <div className="stat-card"><span>Авторов</span><strong>{fmtNum(t.users)}</strong></div>
                    </div>
                    <div className="stats-cards mt">
                        <div className="stat-card">
                            <span>Просмотры наших сообщений</span><strong>{fmtNum(t.out_views)}</strong></div>
                        <div className="stat-card"><span>Реакции на наши сообщения</span><strong
                            style={{color: COLORS.reactions}}>{fmtNum(t.out_reactions)}</strong></div>
                        <div className="stat-card"><span>Ответы на наши сообщения</span><strong
                            style={{color: COLORS.replies}}>{fmtNum(t.out_replies)}</strong></div>
                        <div className="stat-card"><span>Реакции всего</span><strong>{fmtNum(t.reactions)}</strong>
                        </div>
                    </div>

                    <div className="grid-side mt">
                        <div className="card pad">
                            <h3>Активность по дням</h3>
                            <ResponsiveContainer width="100%" height={250}>
                                <BarChart data={s.daily.map((d) => ({...d, date: d.date.slice(5)}))}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false}/>
                                    <XAxis dataKey="date" stroke="var(--muted)" fontSize={12}/>
                                    <YAxis stroke="var(--muted)" fontSize={12}/>
                                    <Tooltip contentStyle={{
                                        background: 'var(--panel-2)',
                                        border: '1px solid var(--border)'
                                    }}/>
                                    <Legend/>
                                    <Bar dataKey="incoming" name="Входящие" stackId="m" fill={COLORS.incoming}/>
                                    <Bar dataKey="outgoing" name="Исходящие" stackId="m" fill={COLORS.outgoing}
                                         radius={[3, 3, 0, 0]}/>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                        <div className="card pad">
                            <h3>По аккаунтам</h3>
                            <table className="table compact">
                                <thead>
                                <tr>
                                    <th>Аккаунт</th>
                                    <th>Вх.</th>
                                    <th>Исх.</th>
                                    <th>👁</th>
                                    <th>❤</th>
                                    <th>💬</th>
                                </tr>
                                </thead>
                                <tbody>
                                {s.per_account.map((r) => (
                                    <tr key={r.account_id}>
                                        <td><Link to={`/accounts/${r.account_id}/messages`}>{r.label}</Link>
                                            <div className="muted small">{r.chats} чатов</div>
                                        </td>
                                        <td>{fmtNum(r.incoming)}</td>
                                        <td>{fmtNum(r.outgoing)}</td>
                                        <td>{fmtNum(r.out_views)}</td>
                                        <td>{fmtNum(r.out_reactions)}</td>
                                        <td>{fmtNum(r.out_replies)}</td>
                                    </tr>
                                ))}
                                </tbody>
                            </table>
                            <div className="muted small">👁 ❤ 💬 - по исходящим сообщениям аккаунта</div>
                        </div>
                    </div>

                    <div className="grid-2 gap mt">
                        <div className="card table-wrap">
                            <div className="pad-h"><h3>Самые активные чаты</h3></div>
                            <table className="table compact">
                                <thead>
                                <tr>
                                    <th>Чат</th>
                                    <th>Сообщ.</th>
                                    <th>Вх. / исх.</th>
                                    <th>Авторов</th>
                                    <th>❤</th>
                                </tr>
                                </thead>
                                <tbody>
                                {s.top_chats.map((c) => (
                                    <tr key={`${c.account_id}:${c.chat_id}`}>
                                        <td>
                                            <strong className="clip">{c.title}</strong>
                                            <div className="muted small">
                                                {CHAT_TYPES[c.type] || c.type}{!accountId && ` · ${accountLabel(byId[c.account_id])}`}
                                            </div>
                                        </td>
                                        <td>{fmtNum(c.messages)}</td>
                                        <td className="small">{fmtNum(c.incoming)} / {fmtNum(c.outgoing)}</td>
                                        <td>{fmtNum(c.authors)}</td>
                                        <td>{fmtNum(c.reactions)}</td>
                                    </tr>
                                ))}
                                </tbody>
                            </table>
                        </div>
                        <div className="card table-wrap">
                            <div className="pad-h"><h3>Самые активные авторы</h3></div>
                            <table className="table compact">
                                <thead>
                                <tr>
                                    <th>Автор</th>
                                    <th>Сообщ.</th>
                                    <th>Чатов</th>
                                    <th>❤</th>
                                    <th>Последнее</th>
                                </tr>
                                </thead>
                                <tbody>
                                {s.top_users.map((u) => (
                                    <tr key={u.id}>
                                        <td>
                                            <strong>{u.name}</strong> {u.is_bot && <span className="tag">бот</span>}
                                            {u.username && (
                                                <div><a className="small" href={`https://t.me/${u.username}`}
                                                        target="_blank" rel="noreferrer">@{u.username}</a></div>
                                            )}
                                        </td>
                                        <td>{fmtNum(u.messages)}</td>
                                        <td>{fmtNum(u.chats)}</td>
                                        <td>{fmtNum(u.reactions)}</td>
                                        <td className="small">{fmtDate(u.last_date)}</td>
                                    </tr>
                                ))}
                                </tbody>
                            </table>
                            {!s.top_users.length && <Empty>Нет входящих сообщений</Empty>}
                        </div>
                    </div>

                    <h2 className="mt">Лучшие сообщения наших аккаунтов</h2>
                    {!s.top_outgoing.length ? (
                        <Empty>За период нет исходящих сообщений</Empty>
                    ) : (
                        <div className="feed">
                            {s.top_outgoing.map((m) => (
                                <div key={m.id} className="feed-msg feed-msg-out">
                                    <div className="feed-msg-head">
                                        <strong>{m.chat_title}</strong>
                                        {!accountId &&
                                            <span className="muted small">· {accountLabel(byId[m.account_id])}</span>}
                                        <span className="muted small grow-right">{fmtDate(m.date)}</span>
                                    </div>
                                    {m.media && <div className="media-tag">[{m.media}]</div>}
                                    {m.text && <div className="msg-text">{linkify(m.text)}</div>}
                                    <div className="msg-foot">
                                        {m.views != null && <span className="stat"><Icon name="eye"
                                                                                         size={14}/> {fmtNum(m.views)}</span>}
                                        {m.reactions.map((r) => <span key={r.emoji}
                                                                      className="reaction">{r.emoji} {r.count}</span>)}
                                        {m.replies != null &&
                                            <span className="stat"><Icon name="comment" size={14}/> {m.replies}</span>}
                                        {m.link && <a className="small grow-right" href={m.link} target="_blank"
                                                      rel="noreferrer">открыть в Telegram</a>}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </>
            )}
        </div>
    )
}
