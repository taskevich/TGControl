export const CHAT_TYPES = {
    user: 'Личный',
    bot: 'Бот',
    group: 'Группа',
    supergroup: 'Супергруппа',
    channel: 'Канал',
}

export const isChat = (dialog) => dialog.type !== 'user' && dialog.type !== 'bot'

export function senderTitle(m) {
    const u = m.tg_user
    if (m.out) return 'Наш аккаунт'
    if (u) return [u.first_name, u.last_name].filter(Boolean).join(' ') || (u.username ? `@${u.username}` : `id${u.id}`)
    return m.sender_name || (m.sender_id ? `id${m.sender_id}` : 'Без автора')
}

export function mergeById(first, second) {
    const known = new Set(first.map((m) => m.id))
    return [...first, ...second.filter((m) => !known.has(m.id))]
}

export const MEDIA_STATUSES = {
    pending: 'в очереди на сохранение',
    stored: 'сохранён',
    too_large: 'больше лимита, не сохранён',
    failed: 'не удалось сохранить',
}

export const MEDIA_KINDS = {
    photo: 'Фото',
    video: 'Видео',
    gif: 'GIF',
    video_note: 'Кружки',
    voice: 'Голосовые',
    audio: 'Аудио',
    sticker: 'Стикеры',
    file: 'Документы',
}

export function previewType(m) {
    const mime = m.media_mime || ''
    if (mime === 'application/x-tgsticker') return 'other' // animated Lottie stickers can't be rendered as-is
    if (mime.startsWith('image/') || (!mime && m.media === 'photo')) return 'image'
    if (mime.startsWith('video/') || ['video', 'gif', 'video_note'].includes(m.media)) return 'video'
    if (mime.startsWith('audio/') || ['voice', 'audio'].includes(m.media)) return 'audio'
    if (mime === 'application/pdf') return 'pdf'
    return 'other'
}

export const downloadUrl = (m) => (m.media_url ? `${m.media_url}&download=1` : null)

export function readAllSummary(res) {
    const parts = [`Прочитано чатов: ${res.dialogs}`]
    if (res.messages) parts.push(`сообщений: ${res.messages}`)
    if (res.topics) parts.push(`тем форумов: ${res.topics}`)
    if (res.accounts > 1) parts.push(`аккаунтов: ${res.accounts}`)
    if (res.errors) parts.push(`ошибок: ${res.errors}`)
    return parts.join(', ')
}
