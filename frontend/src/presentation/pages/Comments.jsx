import {useState} from 'react'
import {useServices} from '../../application/services.jsx'
import CommentsList from '../components/CommentsList.jsx'
import {PageHeader, Pagination, Spinner} from '../components/ui.jsx'
import {useQuery} from '../../application/hooks.js'
import {accountLabel} from '../../domain/accounts.js'

export default function Comments() {
    const svc = useServices()
    const [accountId, setAccountId] = useState('')
    const [kind, setKind] = useState('')
    const [q, setQ] = useState('')
    const [page, setPage] = useState(1)
    const {data: accounts} = useQuery(() => svc.accounts.list(), [])
    const {data, loading} = useQuery(
        () => svc.stats.comments({account_id: accountId, kind, q, page, page_size: 30}),
        [accountId, kind, q, page],
    )

    return (
        <div>
            <PageHeader
                title="Комментарии"
                subtitle="Ответы на сообщения и комментарии наших аккаунтов, упоминания аккаунтов. Собираются при обновлении статистики и сканировании на странице аккаунта."
            />
            <div className="toolbar">
                <input className="search" placeholder="Поиск по тексту" value={q} onChange={(e) => {
                    setPage(1);
                    setQ(e.target.value)
                }}/>
                <select value={accountId} onChange={(e) => {
                    setPage(1);
                    setAccountId(e.target.value)
                }}>
                    <option value="">Все аккаунты</option>
                    {(accounts || []).map((a) => <option key={a.id} value={a.id}>{accountLabel(a)}</option>)}
                </select>
                <select value={kind} onChange={(e) => {
                    setPage(1);
                    setKind(e.target.value)
                }}>
                    <option value="">Все типы</option>
                    <option value="reply">Ответы</option>
                    <option value="mention">Упоминания</option>
                </select>
            </div>
            {loading ? <Spinner/> : <CommentsList items={data?.items} accounts={accounts}/>}
            {data && <Pagination page={page} pageSize={30} total={data.total} onChange={setPage}/>}
        </div>
    )
}
