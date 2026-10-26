export const STATUS_LABELS = {
    new: 'Новый',
    active: 'Активен',
    unauthorized: 'Не авторизован',
    banned: 'Забанен',
    error: 'Ошибка',
    pending: 'В очереди',
    running: 'Выполняется',
    done: 'Готово',
    failed: 'Сбой',
    cancelled: 'Отменена',
    ok: 'Успешно',
    skipped: 'Пропущено',
    created: 'Добавлен',
    updated: 'Обновлён',
}

export const ACCOUNT_STATUSES = ['active', 'new', 'unauthorized', 'banned', 'error']

export const USABLE_STATUSES = ['active', 'new']

export function accountLabel(a) {
    if (!a) return '-'
    const name = [a.first_name, a.last_name].filter(Boolean).join(' ')
    return name || (a.username ? `@${a.username}` : a.phone || `#${a.id}`)
}

export function accountInitial(a) {
    return accountLabel(a).replace('@', '').slice(0, 1).toUpperCase()
}

export const isUsable = (a) => a.is_enabled && USABLE_STATUSES.includes(a.status)

export const countUsable = (accounts) => (accounts || []).filter(isUsable).length

export function matchesAccount(a, needle) {
    if (!needle) return true
    return [a.phone, a.username, a.first_name, a.last_name, a.notes, String(a.tg_id)].some(
        (v) => v && v.toLowerCase().includes(needle),
    )
}

export const NEW_PASSWORD_MIN_LENGTH = 12

export function splitSecret(value) {
    const half = Math.ceil(value.length / 2)
    return [value.slice(0, half), value.slice(half)]
}
