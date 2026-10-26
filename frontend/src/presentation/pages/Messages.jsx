import MessagesFeed from '../components/MessagesFeed.jsx'
import {PageHeader} from '../components/ui.jsx'

export default function Messages() {
    return (
        <div>
            <PageHeader
                title="Все сообщения"
                subtitle="Сообщения из чатов всех аккаунтов, сохранённые в базе: при прокрутке чатов и при получении новых из Telegram."
            />
            <MessagesFeed/>
        </div>
    )
}
