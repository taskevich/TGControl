import {NavLink} from 'react-router-dom'
import {useAuth} from '../../application/auth.jsx'
import Icon from './Icon.jsx'

const NAV = [
    {to: '/accounts', label: 'Аккаунты', icon: 'users'},
    {to: '/proxies', label: 'Прокси', icon: 'shield'},
    {to: '/messages', label: 'Все сообщения', icon: 'chat'},
    {to: '/files', label: 'Все файлы', icon: 'file'},
    {to: '/broadcast', label: 'Рассылка', icon: 'send'},
    {to: '/join-leave', label: 'Вступление / выход', icon: 'door'},
    {to: '/stats', label: 'Статистика', icon: 'chart'},
    {to: '/comments', label: 'Комментарии', icon: 'comment'},
    {to: '/tasks', label: 'Задачи', icon: 'list'},
    {to: '/settings', label: 'Настройки', icon: 'settings'},
]

export default function Layout({children}) {
    const {user, logout} = useAuth()
    return (
        <div className="app">
            <aside className="sidebar">
                <div className="brand">
                    <Icon name="telegram" size={22}/>
                    <span>TG Control</span>
                </div>
                <nav>
                    {NAV.map((n) => (
                        <NavLink key={n.to} to={n.to}
                                 className={({isActive}) => `nav-link${isActive ? ' active' : ''}`}>
                            <Icon name={n.icon}/>
                            <span>{n.label}</span>
                        </NavLink>
                    ))}
                </nav>
                <div className="sidebar-foot">
                    <div className="muted small">Вы вошли как</div>
                    <div className="user-row">
                        <strong>{user?.username}</strong>
                        <button className="btn-icon" title="Выйти" onClick={logout}>
                            <Icon name="logout"/>
                        </button>
                    </div>
                </div>
            </aside>
            <main className="content">{children}</main>
        </div>
    )
}
