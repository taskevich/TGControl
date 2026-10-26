import {useState} from 'react'
import {useServices} from '../../../application/services.jsx'
import CommentsList from '../../components/CommentsList.jsx'
import Icon from '../../components/Icon.jsx'
import {useToast} from '../../components/Toast.jsx'
import {Pagination, Spinner} from '../../components/ui.jsx'
import {useQuery} from '../../../application/hooks.js'

export default function CommentsTab({accountId}) {
    const toast = useToast()
    const svc = useServices()
    const [kind, setKind] = useState('')
    const [q, setQ] = useState('')
    const [page, setPage] = useState(1)
    const [scanning, setScanning] = useState(false)
    const {data, loading, reload} = useQuery(
        () => svc.chats.comments(accountId, {kind, q, page, page_size: 30}),
        [accountId, kind, q, page],
    )

    const scan = async () => {
        setScanning(true)
        try {
            const res = await svc.chats.scanComments(accountId, 80)
            toast(
                `Обновлено сообщений: ${res.tracked?.refreshed ?? 0}, просканировано чатов: ${res.mentions.chats_scanned}, найдено упоминаний/ответов: ${res.mentions.found}`,
                'success',
            )
            reload()
        } catch (e) {
            toast(e.message, 'error')
        } finally {
            setScanning(false)
        }
    }

    return (
        <div>
            <div className="toolbar">
                <input className="search" placeholder="Поиск по тексту" value={q} onChange={(e) => {
                    setPage(1);
                    setQ(e.target.value)
                }}/>
                <select value={kind} onChange={(e) => {
                    setPage(1);
                    setKind(e.target.value)
                }}>
                    <option value="">Все</option>
                    <option value="reply">Ответы на сообщения аккаунта</option>
                    <option value="mention">Упоминания</option>
                </select>
                <button className="btn btn-primary" onClick={scan} disabled={scanning}>
                    {scanning ? <Spinner/> : <Icon name="refresh"/>} Собрать комментарии
                </button>
            </div>
            <div className="muted small mb">
                Здесь собираются ответы на сообщения и комментарии, написанные этим аккаунтом, а также упоминания
                аккаунта в группах.
            </div>
            {loading ? <Spinner/> : <CommentsList items={data?.items}/>}
            {data && <Pagination page={page} pageSize={30} total={data.total} onChange={setPage}/>}
        </div>
    )
}
