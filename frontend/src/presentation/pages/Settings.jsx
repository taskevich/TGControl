import {useState} from 'react'
import {useServices} from '../../application/services.jsx'
import {useAuth} from '../../application/auth.jsx'
import Icon from '../components/Icon.jsx'
import {useToast} from '../components/Toast.jsx'
import {PageHeader, Spinner} from '../components/ui.jsx'
import {useQuery} from '../../application/hooks.js'
import {fmtDate} from '../../domain/format.js'

export default function Settings() {
    const toast = useToast()
    const {user} = useAuth()
    const svc = useServices()
    const [pw, setPw] = useState({old_password: '', new_password: ''})
    const [nu, setNu] = useState({username: '', password: ''})
    const [busy, setBusy] = useState('')
    const users = useQuery(() => svc.users.list(), [])

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

    const changePw = (e) => {
        e.preventDefault()
        run('pw', async () => {
            await svc.auth.changePassword(pw.old_password, pw.new_password)
            setPw({old_password: '', new_password: ''})
            toast('Пароль изменён', 'success')
        })
    }

    const addUser = (e) => {
        e.preventDefault()
        run('user', async () => {
            await svc.users.create(nu.username, nu.password)
            setNu({username: '', password: ''})
            users.reload(true)
            toast('Пользователь создан', 'success')
        })
    }

    const delUser = (u) => {
        if (!window.confirm(`Удалить пользователя ${u.username}?`)) return
        run('del', async () => {
            await svc.users.remove(u.id)
            users.reload(true)
        })
    }

    return (
        <div>
            <PageHeader title="Настройки панели"/>
            <div className="grid-2 gap">
                <form className="card pad stack" onSubmit={changePw}>
                    <h3>Сменить пароль</h3>
                    <label className="field">
                        <span>Текущий пароль</span>
                        <input type="password" value={pw.old_password}
                               onChange={(e) => setPw({...pw, old_password: e.target.value})}/>
                    </label>
                    <label className="field">
                        <span>Новый пароль (минимум 6 символов)</span>
                        <input type="password" value={pw.new_password}
                               onChange={(e) => setPw({...pw, new_password: e.target.value})}/>
                    </label>
                    <button className="btn btn-primary" disabled={busy === 'pw' || pw.new_password.length < 6}>
                        {busy === 'pw' ? <Spinner/> : 'Сменить'}
                    </button>
                </form>
                <div className="card pad stack">
                    <h3>Пользователи панели</h3>
                    <table className="table compact">
                        <tbody>
                        {(users.data || []).map((u) => (
                            <tr key={u.id}>
                                <td><strong>{u.username}</strong> {u.id === user.id &&
                                    <span className="muted small">(вы)</span>}</td>
                                <td className="small muted">{fmtDate(u.created_at)}</td>
                                <td className="actions">
                                    {u.id !== user.id && (
                                        <button className="btn-icon danger" onClick={() => delUser(u)} title="Удалить">
                                            <Icon name="trash"/></button>
                                    )}
                                </td>
                            </tr>
                        ))}
                        </tbody>
                    </table>
                    <form className="row" onSubmit={addUser}>
                        <input placeholder="логин" value={nu.username}
                               onChange={(e) => setNu({...nu, username: e.target.value})}/>
                        <input placeholder="пароль" type="password" value={nu.password}
                               onChange={(e) => setNu({...nu, password: e.target.value})}/>
                        <button className="btn btn-primary"
                                disabled={busy === 'user' || nu.username.length < 3 || nu.password.length < 6}>Добавить
                        </button>
                    </form>
                </div>
            </div>
        </div>
    )
}
