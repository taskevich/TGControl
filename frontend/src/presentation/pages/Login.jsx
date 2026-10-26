import {useState} from 'react'
import {useAuth} from '../../application/auth.jsx'
import Icon from '../components/Icon.jsx'

export default function Login() {
    const {login} = useAuth()
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [busy, setBusy] = useState(false)

    const submit = async (e) => {
        e.preventDefault()
        setBusy(true)
        setError('')
        try {
            await login(username, password)
        } catch (err) {
            setError(err.message)
        } finally {
            setBusy(false)
        }
    }

    return (
        <div className="login-page">
            <form className="login-card" onSubmit={submit}>
                <div className="login-brand">
                    <Icon name="telegram" size={36}/>
                    <h1>TG Control</h1>
                    <div className="muted">Панель управления Telegram-аккаунтами</div>
                </div>
                <label className="field">
                    <span>Логин</span>
                    <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus
                           autoComplete="username"/>
                </label>
                <label className="field">
                    <span>Пароль</span>
                    <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                           autoComplete="current-password"/>
                </label>
                {error && <div className="alert alert-error">{error}</div>}
                <button className="btn btn-primary btn-block" disabled={busy || !username || !password}>
                    {busy ? 'Вход...' : 'Войти'}
                </button>
            </form>
        </div>
    )
}
