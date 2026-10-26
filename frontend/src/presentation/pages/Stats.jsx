import {useState} from 'react'
import {Link, useNavigate} from 'react-router-dom'
import {Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis} from 'recharts'
import {useServices} from '../../application/services.jsx'
import Icon from '../components/Icon.jsx'
import {useToast} from '../components/Toast.jsx'
import {Empty, Modal, PageHeader, Pagination, Spinner} from '../components/ui.jsx'
import {useQuery} from '../../application/hooks.js'
import {accountLabel} from '../../domain/accounts.js'
import {fmtDate, fmtNum} from '../../domain/format.js'
import ChatMessagesStats from './ChatMessagesStats.jsx'
import FilesStats from './FilesStats.jsx'

const SORT_COLS = [
    ['sent_at', 'Дата'],
    ['views', 'Просмотры'],
    ['reactions', 'Реакции'],
    ['replies', 'Комментарии'],
]

export const chartColors = {messages: '#7c8cff', views: '#2aa3ef', reactions: '#f5a524', replies: '#22c55e'}

export default function Stats() {
    const toast = useToast()
    const navigate = useNavigate()
    const svc = useServices()
    const [accountId, setAccountId] = useState('')
    const [q, setQ] = useState('')
    const [source, setSource] = useState('')
    const [commentsOnly, setCommentsOnly] = useState(false)
    const [sort, setSort] = useState({col: 'sent_at', order: 'desc'})
    const [page, setPage] = useState(1)
    const [refreshing, setRefreshing] = useState(false)
    const [trackOpen, setTrackOpen] = useState(false)
    const [view, setView] = useState('tracked')

    const {data: accounts} = useQuery(() => svc.accounts.list(), [])
    const summary = useQuery(() => svc.stats.summary(accountId), [accountId])
    const list = useQuery(
        () =>
            svc.stats.messages({
                account_id: accountId,
                q,
                source,
                comments_only: commentsOnly || undefined,
                sort: sort.col,
                order: sort.order,
                page,
                page_size: 30,
            }),
        [accountId, q, source, commentsOnly, sort, page],
    )
    const byId = Object.fromEntries((accounts || []).map((a) => [a.id, a]))

    const refresh = async () => {
        setRefreshing(true)
        try {
            const res = await svc.stats.refresh({accountId: accountId ? Number(accountId) : null})
            toast(`Обновлено: ${res.refreshed}, ошибок: ${res.errors}, комментариев: ${res.new_comments}`, 'success')
            summary.reload(true)
            list.reload(true)
        } catch (e) {
            toast(e.message, 'error')
        } finally {
            setRefreshing(false)
        }
    }

    const toggleSort = (col) =>
        setSort((s) => ({col, order: s.col === col && s.order === 'desc' ? 'asc' : 'desc'}))

    const s = summary.data
    return (
        <div>
            <PageHeader title="Статистика"
                        subtitle={s?.auto_refresh_minutes ? `Автообновление каждые ${s.auto_refresh_minutes} мин.` : 'Автообновление выключено'}>
                <select value={accountId} onChange={(e) => {
                    setPage(1);
                    setAccountId(e.target.value)
                }}>
                    <option value="">Все аккаунты</option>
                    {(accounts || []).map((a) => <option key={a.id} value={a.id}>{accountLabel(a)}</option>)}
                </select>
                {view === 'tracked' && (
                    <>
                        <button className="btn btn-ghost" onClick={() => setTrackOpen(true)}>
                            <Icon name="link"/> Отслеживать по ссылке
                        </button>
                        <button className="btn btn-primary" onClick={refresh} disabled={refreshing}>
                            {refreshing ? <Spinner/> : <Icon name="refresh"/>} Обновить статистику
                        </button>
                    </>
                )}
            </PageHeader>

            <div className="tabs">
                <button className={view === 'tracked' ? 'active' : ''} onClick={() => setView('tracked')}>
                    Отправленные из панели
                </button>
                <button className={view === 'chats' ? 'active' : ''} onClick={() => setView('chats')}>
                    Сообщения чатов
                </button>
                <button className={view === 'files' ? 'active' : ''} onClick={() => setView('files')}>
                    Файлы
                </button>
            </div>

            {view === 'files' ? (
                <FilesStats accountId={accountId} accounts={accounts}/>
            ) : view === 'chats' ? (
                <ChatMessagesStats accountId={accountId} accounts={accounts}/>
            ) : (
                <>
                    {s && (
                        <>
                            <div className="stats-cards">
                                <div className="stat-card"><span>Сообщений</span><strong>{fmtNum(s.messages)}</strong>
                                </div>
                                <div className="stat-card"><span>Просмотры</span><strong
                                    style={{color: chartColors.views}}>{fmtNum(s.views)}</strong></div>
                                <div className="stat-card"><span>Реакции</span><strong
                                    style={{color: chartColors.reactions}}>{fmtNum(s.reactions)}</strong></div>
                                <div className="stat-card"><span>Комментарии к сообщениям</span><strong
                                    style={{color: chartColors.replies}}>{fmtNum(s.replies)}</strong></div>
                                <div className="stat-card">
                                    <span>Комментарии за 24 ч</span><strong>{fmtNum(s.comments_24h)}</strong><Link
                                    className="small" to="/comments">все {fmtNum(s.comments_total)} →</Link></div>
                            </div>
                            <div className="grid-side mt">
                                <div className="card pad">
                                    <h3>По дням (14 дней)</h3>
                                    {s.daily.length ? (
                                        <ResponsiveContainer width="100%" height={240}>
                                            <BarChart data={s.daily.map((d) => ({...d, date: d.date.slice(5)}))}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)"
                                                               vertical={false}/>
                                                <XAxis dataKey="date" stroke="var(--muted)" fontSize={12}/>
                                                <YAxis stroke="var(--muted)" fontSize={12}/>
                                                <Tooltip contentStyle={{
                                                    background: 'var(--panel-2)',
                                                    border: '1px solid var(--border)'
                                                }}/>
                                                <Legend/>
                                                <Bar dataKey="messages" name="Сообщения" fill={chartColors.messages}
                                                     radius={[3, 3, 0, 0]}/>
                                                <Bar dataKey="reactions" name="Реакции" fill={chartColors.reactions}
                                                     radius={[3, 3, 0, 0]}/>
                                                <Bar dataKey="replies" name="Комментарии" fill={chartColors.replies}
                                                     radius={[3, 3, 0, 0]}/>
                                            </BarChart>
                                        </ResponsiveContainer>
                                    ) : (
                                        <Empty>Нет данных за период</Empty>
                                    )}
                                </div>
                                <div className="card pad">
                                    <h3>По аккаунтам</h3>
                                    <table className="table compact">
                                        <thead>
                                        <tr>
                                            <th>Аккаунт</th>
                                            <th>Сообщ.</th>
                                            <th>👁</th>
                                            <th>❤</th>
                                            <th>💬</th>
                                        </tr>
                                        </thead>
                                        <tbody>
                                        {s.per_account.map((r) => (
                                            <tr key={r.account_id}>
                                                <td><Link to={`/accounts/${r.account_id}`}>{r.label}</Link></td>
                                                <td>{fmtNum(r.messages)}</td>
                                                <td>{fmtNum(r.views)}</td>
                                                <td>{fmtNum(r.reactions)}</td>
                                                <td>{fmtNum(r.replies)}</td>
                                            </tr>
                                        ))}
                                        </tbody>
                                    </table>
                                    {!s.per_account.length &&
                                        <div className="muted small">Пока нет отслеживаемых сообщений</div>}
                                </div>
                            </div>
                        </>
                    )}

                    <div className="toolbar mt">
                        <input className="search" placeholder="Поиск по тексту или чату" value={q} onChange={(e) => {
                            setPage(1);
                            setQ(e.target.value)
                        }}/>
                        <select value={source} onChange={(e) => {
                            setPage(1);
                            setSource(e.target.value)
                        }}>
                            <option value="">Любой источник</option>
                            <option value="panel">Из панели</option>
                            <option value="bulk">Рассылка</option>
                            <option value="manual">Добавлено по ссылке</option>
                        </select>
                        <label className="check-row">
                            <input type="checkbox" checked={commentsOnly} onChange={(e) => {
                                setPage(1);
                                setCommentsOnly(e.target.checked)
                            }}/> только комментарии к постам
                        </label>
                    </div>
                    <div className="card table-wrap">
                        {list.loading ? (
                            <div className="pad"><Spinner/></div>
                        ) : !list.data?.items.length ? (
                            <Empty>Нет отслеживаемых сообщений. Отправьте сообщение из панели или добавьте его по
                                ссылке.</Empty>
                        ) : (
                            <table className="table hover">
                                <thead>
                                <tr>
                                    <th>Сообщение</th>
                                    <th>Аккаунт</th>
                                    <th>Чат</th>
                                    {SORT_COLS.map(([col, label]) => (
                                        <th key={col} className="sortable" onClick={() => toggleSort(col)}>
                                            {label} {sort.col === col ? (sort.order === 'desc' ? '↓' : '↑') : ''}
                                        </th>
                                    ))}
                                </tr>
                                </thead>
                                <tbody>
                                {list.data.items.map((m) => (
                                    <tr key={m.id} onClick={() => navigate(`/stats/${m.id}`)}>
                                        <td className="clip-wide">
                                            {m.is_comment && <span className="tag">коммент</span>}
                                            {m.is_deleted && <span className="tag tag-err">удалено</span>}
                                            {m.text || <span className="muted">[медиа]</span>}
                                            {m.refresh_error &&
                                                <div className="c-err small clip">{m.refresh_error}</div>}
                                        </td>
                                        <td className="small">{accountLabel(byId[m.account_id])}</td>
                                        <td className="small clip">{m.chat_title}</td>
                                        <td className="small">{fmtDate(m.sent_at)}</td>
                                        <td>{fmtNum(m.views)}</td>
                                        <td title={m.reactions.map((r) => `${r.emoji} ${r.count}`).join('  ')}>
                                            {fmtNum(m.reactions_total)} <span
                                            className="small">{m.reactions.slice(0, 3).map((r) => r.emoji).join('')}</span>
                                        </td>
                                        <td>{fmtNum(m.replies_count)}</td>
                                    </tr>
                                ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                    {list.data && <Pagination page={page} pageSize={30} total={list.data.total} onChange={setPage}/>}
                </>
            )}
            {trackOpen && (
                <TrackModal
                    accounts={accounts}
                    onClose={() => setTrackOpen(false)}
                    onDone={(tm) => navigate(`/stats/${tm.id}`)}
                />
            )}
        </div>
    )
}

function TrackModal({accounts, onClose, onDone}) {
    const toast = useToast()
    const svc = useServices()
    const [accountId, setAccountId] = useState(accounts?.[0]?.id || '')
    const [link, setLink] = useState('')
    const [busy, setBusy] = useState(false)
    const submit = async (e) => {
        e.preventDefault()
        setBusy(true)
        try {
            onDone(await svc.stats.track(Number(accountId), link))
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setBusy(false)
        }
    }
    return (
        <Modal title="Отслеживать сообщение по ссылке" onClose={onClose}>
            <form className="stack" onSubmit={submit}>
                <div className="muted small">
                    Например, комментарий, написанный вручную: https://t.me/channel/123?comment=456 или сообщение
                    https://t.me/chat/789.
                </div>
                <label className="field">
                    <span>Аккаунт, которым читать сообщение</span>
                    <select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                        {(accounts || []).map((a) => <option key={a.id} value={a.id}>{accountLabel(a)}</option>)}
                    </select>
                </label>
                <label className="field">
                    <span>Ссылка</span>
                    <input value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://t.me/..."
                           autoFocus/>
                </label>
                <button className="btn btn-primary" disabled={busy || !link.trim() || !accountId}>{busy ?
                    <Spinner/> : 'Добавить'}</button>
            </form>
        </Modal>
    )
}
