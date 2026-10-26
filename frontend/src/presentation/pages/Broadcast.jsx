import {useState} from 'react'
import {useNavigate} from 'react-router-dom'
import {useServices} from '../../application/services.jsx'
import {useToast} from '../components/Toast.jsx'
import {AccountPicker, PageHeader, Spinner} from '../components/ui.jsx'
import {useQuery} from '../../application/hooks.js'
import {countUsable} from '../../domain/accounts.js'
import {splitLines} from '../../domain/format.js'

export default function Broadcast() {
    const toast = useToast()
    const navigate = useNavigate()
    const svc = useServices()
    const {data: accounts} = useQuery(() => svc.accounts.list(), [])
    const [pick, setPick] = useState({all: true, ids: []})
    const [mode, setMode] = useState('message')
    const [targets, setTargets] = useState('')
    const [text, setText] = useState('')
    const [opts, setOpts] = useState({
        join_if_needed: false,
        track: true,
        link_preview: true,
        delay_min: 3,
        delay_max: 8
    })
    const [busy, setBusy] = useState(false)
    const setOpt = (k, v) => setOpts((o) => ({...o, [k]: v}))

    const list = splitLines(targets)
    const accCount = pick.all
        ? countUsable(accounts)
        : pick.ids.length

    const submit = async (e) => {
        e.preventDefault()
        if (!window.confirm(`Запустить: ${accCount} акк. × ${list.length} целей = ${accCount * list.length} отправок?`)) return
        setBusy(true)
        try {
            const task = await svc.tasks.start('send', {
                mode,
                text,
                targets: list,
                all_accounts: pick.all,
                account_ids: pick.ids,
                ...opts,
                delay_min: Number(opts.delay_min),
                delay_max: Number(opts.delay_max),
            })
            toast(`Задача #${task.id} запущена`, 'success')
            navigate(`/tasks/${task.id}`)
        } catch (err) {
            toast(err.message, 'error')
        } finally {
            setBusy(false)
        }
    }

    return (
        <div>
            <PageHeader
                title="Рассылка"
                subtitle="Отправка от выбранных или всех аккаунтов. Аккаунты без прав на отправку в чат пропускаются автоматически."
            />
            <form className="grid-side" onSubmit={submit}>
                <div className="stack">
                    <div className="card pad stack">
                        <div className="seg">
                            <button type="button" className={mode === 'message' ? 'active' : ''}
                                    onClick={() => setMode('message')}>
                                Сообщения в чаты
                            </button>
                            <button type="button" className={mode === 'comment' ? 'active' : ''}
                                    onClick={() => setMode('comment')}>
                                Комментарии к постам
                            </button>
                        </div>
                        <label className="field">
              <span>
                {mode === 'message'
                    ? 'Чаты / пользователи - по одному на строку (@username, t.me/chat, t.me/+invite, ID). Ссылка на сообщение = ответ на него'
                    : 'Ссылки на посты каналов - по одной на строку (t.me/channel/123)'}
              </span>
                            <textarea rows={6} className="mono" value={targets}
                                      onChange={(e) => setTargets(e.target.value)}/>
                        </label>
                        <label className="field">
                            <span>Текст ({text.length}/4096)</span>
                            <textarea rows={7} value={text} maxLength={4096} onChange={(e) => setText(e.target.value)}/>
                        </label>
                    </div>
                    <div className="card pad stack">
                        <h3>Параметры</h3>
                        <label className="check-row">
                            <input type="checkbox" checked={opts.join_if_needed}
                                   onChange={(e) => setOpt('join_if_needed', e.target.checked)}/>
                            {mode === 'message' ? 'Вступать в чат, если аккаунт не участник' : 'Вступать в группу обсуждения, если нужно'}
                        </label>
                        <label className="check-row">
                            <input type="checkbox" checked={opts.track}
                                   onChange={(e) => setOpt('track', e.target.checked)}/>
                            Отслеживать статистику (просмотры, реакции, комментарии)
                        </label>
                        <label className="check-row">
                            <input type="checkbox" checked={opts.link_preview}
                                   onChange={(e) => setOpt('link_preview', e.target.checked)}/>
                            Превью ссылок
                        </label>
                        <div className="grid-2">
                            <label className="field">
                                <span>Пауза от, сек</span>
                                <input type="number" min="0" step="0.5" value={opts.delay_min}
                                       onChange={(e) => setOpt('delay_min', e.target.value)}/>
                            </label>
                            <label className="field">
                                <span>Пауза до, сек</span>
                                <input type="number" min="0" step="0.5" value={opts.delay_max}
                                       onChange={(e) => setOpt('delay_max', e.target.value)}/>
                            </label>
                        </div>
                    </div>
                </div>
                <div className="stack">
                    <div className="card pad stack">
                        <h3>От каких аккаунтов</h3>
                        <AccountPicker accounts={accounts} value={pick} onChange={setPick}/>
                    </div>
                    <div className="card pad stack">
                        <div className="summary-line">
                            <span>Аккаунтов</span><strong>{accCount}</strong>
                        </div>
                        <div className="summary-line">
                            <span>Целей</span><strong>{list.length}</strong>
                        </div>
                        <div className="summary-line">
                            <span>Всего действий</span><strong>{accCount * list.length}</strong>
                        </div>
                        <button className="btn btn-primary btn-block"
                                disabled={busy || !text.trim() || !list.length || !accCount}>
                            {busy ? <Spinner/> : 'Запустить'}
                        </button>
                    </div>
                </div>
            </form>
        </div>
    )
}
