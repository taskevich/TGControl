import FilesView from '../components/FilesView.jsx'
import {PageHeader} from '../components/ui.jsx'

export default function Files() {
    return (
        <div>
            <PageHeader
                title="Все файлы"
                subtitle="Медиа и файлы сохранённых сообщений всех аккаунтов, выгруженные в хранилище S3."
            />
            <FilesView/>
        </div>
    )
}
