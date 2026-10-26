import {NavLink, useNavigate, useParams} from 'react-router-dom'
import {useServices} from '../../application/services.jsx'
import {Badge, SecretValue, Spinner} from '../components/ui.jsx'
import {useQuery} from '../../application/hooks.js'
import {accountInitial, accountLabel} from '../../domain/accounts.js'
import ChatsTab from './account/ChatsTab.jsx'
import MessagesFeed from '../components/MessagesFeed.jsx'
import FilesView from '../components/FilesView.jsx'
import CommentsTab from './account/CommentsTab.jsx'
import ActionsTab from './account/ActionsTab.jsx'
import SettingsTab from './account/SettingsTab.jsx'

const TABS = [
    ['chats', 'Чаты'],
    ['messages', 'Сообщения'],
    ['files', 'Файлы'],
    ['comments', 'Комментарии к аккаунту'],
    ['actions', 'Действия'],
    ['settings', 'Настройки'],
]

export default function AccountView() {
    const {id, tab = 'chats'} = useParams()
    const navigate = useNavigate()
    const accountId = Number(id)
    const svc = useServices()
    const {data: accounts} = useQuery(() => svc.accounts.list(), [])
    const {data: account, loading, setData: setAccount} = useQuery(() => svc.accounts.get(accountId), [accountId])

    if (loading && !account) return <Spinner/>
    if (!account) return <div className="empty">Аккаунт не найден</div>

    return (
        <div className="account-view">
            <div className="account-head">
                <div className="acc-cell">
                    <span className="avatar avatar-lg">{accountInitial(account)}</span>
                    <div>
                        <h1>{accountLabel(account)}</h1>
                        <div className="muted small">
                            {account.username && `@${account.username} · `}
                            {account.phone} · ID {account.tg_id || '-'} <Badge status={account.status}/>
                            {account.connected && <span className="dot-online" title="Подключён"/>}
                            {account.twofa && <> · 2FA: <SecretValue value={account.twofa}/></>}
                        </div>
                    </div>
                </div>
                <label className="field inline">
                    <span>Аккаунт:</span>
                    <select value={accountId} onChange={(e) => navigate(`/accounts/${e.target.value}/${tab}`)}>
                        {(accounts || []).map((a) => (
                            <option key={a.id} value={a.id}>
                                {accountLabel(a)} {a.phone ? `(${a.phone})` : ''}
                            </option>
                        ))}
                    </select>
                </label>
            </div>

            <div className="tabs">
                {TABS.map(([k, label]) => (
                    <NavLink key={k} to={`/accounts/${accountId}/${k}`} className={() => (tab === k ? 'active' : '')}>
                        {label}
                    </NavLink>
                ))}
            </div>

            {account.status !== 'active' && account.status !== 'new' && (
                <div className="alert alert-error">
                    Аккаунт в статусе «{account.status}». {account.status_detail}
                </div>
            )}

            {tab === 'chats' && <ChatsTab key={accountId} accountId={accountId}/>}
            {tab === 'messages' && <MessagesFeed key={accountId} accountId={accountId}/>}
            {tab === 'files' && <FilesView key={accountId} accountId={accountId}/>}
            {tab === 'comments' && <CommentsTab key={accountId} accountId={accountId}/>}
            {tab === 'actions' && <ActionsTab key={accountId} accountId={accountId}/>}
            {tab === 'settings' && <SettingsTab key={accountId} account={account} onSaved={setAccount}/>}
        </div>
    )
}
