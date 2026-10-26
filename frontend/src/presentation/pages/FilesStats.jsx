import {useState} from 'react'
import {Link} from 'react-router-dom'
import {Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis} from 'recharts'
import {useServices} from '../../application/services.jsx'
import {Empty, Spinner} from '../components/ui.jsx'
import {useQuery} from '../../application/hooks.js'
import {accountLabel} from '../../domain/accounts.js'
import {MEDIA_KINDS} from '../../domain/chats.js'
import {fmtBytes, fmtNum} from '../../domain/format.js'

const COLORS = {stored: '#22c55e', notStored: '#7c8cff', bytes: '#2aa3ef', pending: '#f5a524', failed: '#ef4444'}
const PERIODS = [[7, '7 дней'], [14, '14 дней'], [30, '30 дней'], [90, '90 дней'], [0, 'Всё время']]
const TOOLTIP = {background: 'var(--panel-2)', border: '1px solid var(--border)'}
const MB = 2 ** 20


export default function FilesStats({accountId, accounts}) {
    const svc = useServices()
    const [days, setDays] = useState(30)
    const {data: s, loading, error} = useQuery(() => svc.media.stats(accountId, days || undefined), [accountId, days])
    const byId = Object.fromEntries((accounts || []).map((a) => [a.id, a]))

    if (loading && !s) return <Spinner/>
    if (error) return <div className="alert alert-error">{error.message}</div>
    if (!s) return null

    const st = (k) => s.statuses[k] || {count: 0, bytes: 0}
    const total = Object.values(s.statuses).reduce((sum, x) => sum + x.count, 0)
    const stored = st('stored')
    const daily = s.daily.map((d) => ({
        date: d.date.slice(5),
        stored: d.stored,
        notStored: d.total - d.stored,
        mb: Math.round((d.bytes / MB) * 10) / 10,
    }))
    const kinds = s.kinds.map((k) => ({
        ...k,
        name: MEDIA_KINDS[k.kind] || k.kind,
        mb: Math.round((k.stored_bytes / MB) * 10) / 10,
        rest: k.total - k.stored,
    }))

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
          По дате сообщения.{' '}<Link to={accountId ? `/accounts/${accountId}/files` : '/files'}>Все файлы →</Link>
        </span>
            </div>

            {!s.enabled && (
                <div className="alert alert-error">Хранилище файлов не настроено - задайте S3_BUCKET в .env.</div>
            )}

            {!total ? (
                <Empty>За период нет сообщений с файлами.</Empty>
            ) : (
                <>
                    <div className="stats-cards">
                        <div className="stat-card"><span>Файлов в сообщениях</span><strong>{fmtNum(total)}</strong>
                        </div>
                        <div className="stat-card"><span>Сохранено в S3</span><strong
                            style={{color: COLORS.stored}}>{fmtNum(stored.count)}</strong>
                            <span className="muted small">{Math.round((stored.count / total) * 100)}% от всех</span>
                        </div>
                        <div className="stat-card"><span>Объём в S3</span><strong
                            style={{color: COLORS.bytes}}>{fmtBytes(stored.bytes)}</strong>
                            <span
                                className="muted small">в среднем {fmtBytes(stored.count ? Math.round(stored.bytes / stored.count) : 0)}</span>
                        </div>
                        <div className="stat-card"><span>В очереди</span><strong
                            style={{color: COLORS.pending}}>{fmtNum(st('pending').count)}</strong>
                            <span
                                className="muted small">{st('pending').bytes ? `≈ ${fmtBytes(st('pending').bytes)}` : ' '}</span>
                        </div>
                        <div className="stat-card"><span>Не сохранено</span><strong
                            style={{color: COLORS.failed}}>{fmtNum(st('failed').count + st('too_large').count)}</strong>
                            <span
                                className="muted small">ошибок {fmtNum(st('failed').count)} · больше {fmtBytes(s.max_size)}: {fmtNum(st('too_large').count)}</span>
                        </div>
                    </div>

                    <div className="grid-2 gap mt">
                        <div className="card pad">
                            <h3>Файлы по дням</h3>
                            <ResponsiveContainer width="100%" height={250}>
                                <BarChart data={daily}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false}/>
                                    <XAxis dataKey="date" stroke="var(--muted)" fontSize={12}/>
                                    <YAxis stroke="var(--muted)" fontSize={12} allowDecimals={false}/>
                                    <Tooltip contentStyle={TOOLTIP}/>
                                    <Legend/>
                                    <Bar dataKey="stored" name="Сохранено" stackId="f" fill={COLORS.stored}/>
                                    <Bar dataKey="notStored" name="Не сохранено / в очереди" stackId="f"
                                         fill={COLORS.notStored} radius={[3, 3, 0, 0]}/>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                        <div className="card pad">
                            <h3>Объём сохранённого по дням, МБ</h3>
                            <ResponsiveContainer width="100%" height={250}>
                                <BarChart data={daily}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false}/>
                                    <XAxis dataKey="date" stroke="var(--muted)" fontSize={12}/>
                                    <YAxis stroke="var(--muted)" fontSize={12}/>
                                    <Tooltip contentStyle={TOOLTIP} formatter={(v) => `${v} МБ`}/>
                                    <Bar dataKey="mb" name="Объём" fill={COLORS.bytes} radius={[3, 3, 0, 0]}/>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <div className="grid-2 gap mt">
                        <div className="card pad">
                            <h3>По типам</h3>
                            <ResponsiveContainer width="100%" height={Math.max(160, kinds.length * 38)}>
                                <BarChart data={kinds} layout="vertical" margin={{left: 20}}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false}/>
                                    <XAxis type="number" stroke="var(--muted)" fontSize={12} allowDecimals={false}/>
                                    <YAxis type="category" dataKey="name" stroke="var(--muted)" fontSize={12}
                                           width={90}/>
                                    <Tooltip contentStyle={TOOLTIP}/>
                                    <Legend/>
                                    <Bar dataKey="stored" name="Сохранено" stackId="k" fill={COLORS.stored}/>
                                    <Bar dataKey="rest" name="Не сохранено / в очереди" stackId="k"
                                         fill={COLORS.notStored} radius={[0, 3, 3, 0]}/>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                        <div className="card table-wrap">
                            <table className="table compact">
                                <thead>
                                <tr>
                                    <th>Тип</th>
                                    <th>Всего</th>
                                    <th>Сохранено</th>
                                    <th>Объём</th>
                                    <th>В очереди</th>
                                    <th>Ошибки</th>
                                    <th>&gt; лимита</th>
                                </tr>
                                </thead>
                                <tbody>
                                {kinds.map((k) => (
                                    <tr key={k.kind}>
                                        <td>{k.name}</td>
                                        <td>{fmtNum(k.total)}</td>
                                        <td>{fmtNum(k.stored)}</td>
                                        <td>{fmtBytes(k.stored_bytes)}</td>
                                        <td>{fmtNum(k.pending)}</td>
                                        <td>{fmtNum(k.failed)}</td>
                                        <td>{fmtNum(k.too_large)}</td>
                                    </tr>
                                ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div className="grid-2 gap mt">
                        <div className="card table-wrap">
                            <div className="pad-h"><h3>Чаты с наибольшим объёмом файлов</h3></div>
                            <table className="table compact">
                                <thead>
                                <tr>
                                    <th>Чат</th>
                                    <th>Файлов</th>
                                    <th>Объём</th>
                                </tr>
                                </thead>
                                <tbody>
                                {s.chats.map((c) => (
                                    <tr key={`${c.account_id}:${c.chat_id}`}>
                                        <td className="clip-cell" title={c.chat_title || ''}>
                                            {c.chat_title || c.chat_id}
                                            {!accountId && <span
                                                className="muted small"> · {accountLabel(byId[c.account_id])}</span>}
                                        </td>
                                        <td>{fmtNum(c.count)}</td>
                                        <td>{fmtBytes(c.bytes)}</td>
                                    </tr>
                                ))}
                                </tbody>
                            </table>
                            {!s.chats.length && <Empty>Сохранённых файлов нет</Empty>}
                        </div>
                        {!accountId && (
                            <div className="card table-wrap">
                                <div className="pad-h"><h3>По аккаунтам</h3></div>
                                <table className="table compact">
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
                                        <tr key={a.account_id}>
                                            <td><Link
                                                to={`/accounts/${a.account_id}/files`}>{accountLabel(byId[a.account_id])}</Link>
                                            </td>
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
                </>
            )}
        </div>
    )
}
