import {useState} from 'react'
import {Link, useNavigate, useParams} from 'react-router-dom'
import {useServices} from '../../application/services.jsx'
import {useToast} from '../components/Toast.jsx'
import {Badge, Empty, PageHeader, Progress, Spinner} from '../components/ui.jsx'
import {useInterval, useQuery} from '../../application/hooks.js'
import {accountLabel} from '../../domain/accounts.js'
import {fmtDate} from '../../domain/format.js'
import {TASK_KINDS, isTaskActive} from '../../domain/tasks.js'
import {linkify} from '../components/text.jsx'

export default function TaskDetail() {
    const {id} = useParams()
    const navigate = useNavigate()
    const toast = useToast()
    const svc = useServices()
    const [filter, setFilter] = useState('')
    const {data: task, loading, reload} = useQuery(() => svc.tasks.get(id), [id])
    const {data: accounts} = useQuery(() => svc.accounts.list(), [])
    const running = task && isTaskActive(task)
    useInterval(() => reload(true), 2000, running)

    if (loading && !task) return <Spinner/>
    if (!task) return <Empty>Задача не найдена</Empty>

    const byId = Object.fromEntries((accounts || []).map((a) => [a.id, a]))
    const items = task.items.filter((i) => !filter || i.status === filter)

    const cancel = async () => {
        try {
            await svc.tasks.cancel(id)
            toast('Задача будет остановлена', 'success')
        } catch (e) {
            toast(e.message, 'error')
        }
    }
    const remove = async () => {
        if (!window.confirm('Удалить задачу из истории?')) return
        try {
            await svc.tasks.remove(id)
            navigate('/tasks')
        } catch (e) {
            toast(e.message, 'error')
        }
    }

    return (
        <div>
            <PageHeader title={`${TASK_KINDS[task.kind] || task.kind} #${task.id}`}
                        subtitle={`Создана ${fmtDate(task.created_at)} · ${task.created_by || ''}`}>
                {running ? (
                    <button className="btn btn-danger" onClick={cancel}>Остановить</button>
                ) : (
                    <button className="btn btn-ghost" onClick={remove}>Удалить</button>
                )}
            </PageHeader>

            <div className="stats-cards">
                <div className="stat-card"><span>Статус</span><Badge status={task.status}/></div>
                <div className="stat-card"><span>Выполнено</span><strong>{task.done} / {task.total}</strong></div>
                <div className="stat-card"><span>Успешно</span><strong className="c-ok">{task.success}</strong></div>
                <div className="stat-card"><span>Пропущено</span><strong className="c-warn">{task.skipped}</strong>
                </div>
                <div className="stat-card"><span>Ошибки</span><strong className="c-err">{task.failed}</strong></div>
            </div>
            <Progress value={task.done} total={task.total}/>
            {task.error && <div className="alert alert-error">{task.error}</div>}

            <div className="card pad mt">
                <div className="grid-2">
                    <div>
                        <div className="muted small">Цели</div>
                        <div className="mono small pre">{task.params.targets?.join('\n')}</div>
                    </div>
                    {task.params.text && (
                        <div>
                            <div className="muted small">Текст</div>
                            <div className="quote">{task.params.text}</div>
                        </div>
                    )}
                </div>
            </div>

            <div className="toolbar mt">
                <div className="seg">
                    {[['', 'Все'], ['ok', 'Успешно'], ['skipped', 'Пропущено'], ['error', 'Ошибки']].map(([k, l]) => (
                        <button key={k} className={filter === k ? 'active' : ''}
                                onClick={() => setFilter(k)}>{l}</button>
                    ))}
                </div>
            </div>
            <div className="card table-wrap">
                {!items.length ? (
                    <Empty>{running ? 'Выполняется...' : 'Нет записей'}</Empty>
                ) : (
                    <table className="table">
                        <thead>
                        <tr>
                            <th>Аккаунт</th>
                            <th>Цель</th>
                            <th>Результат</th>
                            <th>Детали</th>
                            <th>Время</th>
                        </tr>
                        </thead>
                        <tbody>
                        {items.map((i) => (
                            <tr key={i.id}>
                                <td>{i.account_id ? <Link
                                    to={`/accounts/${i.account_id}`}>{accountLabel(byId[i.account_id]) || `#${i.account_id}`}</Link> : '-'}</td>
                                <td className="mono small clip" title={i.target}>{i.target}</td>
                                <td><Badge status={i.status}/></td>
                                <td className="small">{linkify(i.detail)}</td>
                                <td className="small">{fmtDate(i.created_at)}</td>
                            </tr>
                        ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    )
}
