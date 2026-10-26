export const TASK_KINDS = {
    send: 'Рассылка',
    comment: 'Комментарии',
    join: 'Вступление',
    leave: 'Выход',
}

export const isTaskActive = (t) => ['pending', 'running'].includes(t.status)
