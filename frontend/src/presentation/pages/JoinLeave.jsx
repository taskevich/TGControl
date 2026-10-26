import {useState} from 'react'
import {useNavigate} from 'react-router-dom'
import {useServices} from '../../application/services.jsx'
import {useToast} from '../components/Toast.jsx'
import {AccountPicker, PageHeader, Spinner} from '../components/ui.jsx'
import {useQuery} from '../../application/hooks.js'
import {countUsable} from '../../domain/accounts.js'
import {splitLines} from '../../domain/format.js'

export default function JoinLeave() {
    const toast = useToast()
    const navigate = useNavigate()
    const svc = useServices()
    const {data: accounts} = useQuery(() => svc.accounts.list(), [])
    const [pick, setPick] = useState({all: true, ids: []})
    const [targets, setTargets] = useState('')
    const [delay, setDelay] = useState({min: 5, max: 15})
    const [busy, setBusy] = useState('')

    const list = splitLines(targets)
    const accCount = pick.all
        ? countUsable(accounts)
        : pick.ids.length

    const start = async (action) => {
        const verb = action === 'join' ? 'Вступить в' : 'Выйти из'
        if (!window.confirm(`${verb} ${list.length} чат(ов) для ${accCount} аккаунт(ов)?`)) return
        setBusy(action)
        try {
            const task = await svc.tasks.start(action, {
                targets: list,
                all_accounts: pick.all,
                account_ids: pick.ids,
                delay_min: Number(delay.min),
                delay_max: Number(delay.max),
            })
            toast(`Задача #${task.id} запущена`, 'success')
            navigate(`/tasks/${task.id}`)
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setBusy('')
        }
    }

    return (
        <div>
            <PageHeader title="Вступление и выход из чатов"
                        subtitle="Для всех или выбранных аккаунтов. Для одного аккаунта - вкладка «Действия» на странице аккаунта."/>
            <div className="grid-side">
                <div className="card pad stack">
                    <label className="field">
                        <span>Чаты - по одному на строку: @username, https://t.me/chat, https://t.me/+invite, ID</span>
                        <textarea rows={12} className="mono" value={targets}
                                  onChange={(e) => setTargets(e.target.value)}/>
                    </label>
                    <div className="grid-2">
                        <label className="field">
                            <span>Пауза от, сек</span>
                            <input type="number" min="0" value={delay.min}
                                   onChange={(e) => setDelay({...delay, min: e.target.value})}/>
                        </label>
                        <label className="field">
                            <span>Пауза до, сек</span>
                            <input type="number" min="0" value={delay.max}
                                   onChange={(e) => setDelay({...delay, max: e.target.value})}/>
                        </label>
                    </div>
                    <div className="muted small">
                        Частое вступление в чаты может привести к FloodWait или ограничениям - используйте паузы 10+
                        секунд.
                    </div>
                </div>
                <div className="stack">
                    <div className="card pad stack">
                        <h3>Аккаунты</h3>
                        <AccountPicker accounts={accounts} value={pick} onChange={setPick}/>
                    </div>
                    <div className="card pad stack">
                        <div className="summary-line"><span>Аккаунтов</span><strong>{accCount}</strong></div>
                        <div className="summary-line"><span>Чатов</span><strong>{list.length}</strong></div>
                        <button className="btn btn-primary btn-block" disabled={!!busy || !list.length || !accCount}
                                onClick={() => start('join')}>
                            {busy === 'join' ? <Spinner/> : 'Вступить'}
                        </button>
                        <button className="btn btn-danger btn-block" disabled={!!busy || !list.length || !accCount}
                                onClick={() => start('leave')}>
                            {busy === 'leave' ? <Spinner/> : 'Выйти'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
