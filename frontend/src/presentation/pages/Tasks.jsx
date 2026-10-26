import {useState} from 'react'
import {Link} from 'react-router-dom'
import {useServices} from '../../application/services.jsx'
import {Badge, Empty, PageHeader, Pagination, Progress, Spinner} from '../components/ui.jsx'
import {useInterval, useQuery} from '../../application/hooks.js'
import {fmtDate} from '../../domain/format.js'
import {TASK_KINDS, isTaskActive} from '../../domain/tasks.js'

export default function Tasks() {
    const svc = useServices()
    const [page, setPage] = useState(1)
    const [kind, setKind] = useState('')
    const {data, loading, reload} = useQuery(() => svc.tasks.list({page, kind, page_size: 30}), [page, kind])
    const active = (data?.items || []).some(isTaskActive)
    useInterval(() => reload(true), 3000, active)

    return (
        <div>
            <PageHeader title="Задачи" subtitle="Массовые рассылки, вступления и выходы">
                <select value={kind} onChange={(e) => {
                    setPage(1);
                    setKind(e.target.value)
                }}>
                    <option value="">Все типы</option>
                    {Object.entries(TASK_KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
            </PageHeader>
            <div className="card table-wrap">
                {loading ? (
                    <div className="pad"><Spinner/></div>
                ) : !data?.items.length ? (
                    <Empty>Задач пока нет</Empty>
                ) : (
                    <table className="table">
                        <thead>
                        <tr>
                            <th>#</th>
                            <th>Тип</th>
                            <th>Статус</th>
                            <th>Прогресс</th>
                            <th>Успешно / пропущено / ошибки</th>
                            <th>Создана</th>
                            <th>Кем</th>
                        </tr>
                        </thead>
                        <tbody>
                        {data.items.map((t) => (
                            <tr key={t.id}>
                                <td><Link to={`/tasks/${t.id}`}>#{t.id}</Link></td>
                                <td><Link to={`/tasks/${t.id}`}>{TASK_KINDS[t.kind] || t.kind}</Link>
                                    <div className="muted small clip">{t.params.targets?.slice(0, 2).join(', ')}</div>
                                </td>
                                <td><Badge status={t.status}/></td>
                                <td style={{minWidth: 140}}>
                                    <Progress value={t.done} total={t.total}/>
                                    <span className="muted small">{t.done} / {t.total}</span>
                                </td>
                                <td>
                                    <span className="c-ok">{t.success}</span> / <span
                                    className="c-warn">{t.skipped}</span> / <span className="c-err">{t.failed}</span>
                                </td>
                                <td className="small">{fmtDate(t.created_at)}</td>
                                <td className="small">{t.created_by}</td>
                            </tr>
                        ))}
                        </tbody>
                    </table>
                )}
            </div>
            {data && <Pagination page={page} pageSize={30} total={data.total} onChange={setPage}/>}
        </div>
    )
}
