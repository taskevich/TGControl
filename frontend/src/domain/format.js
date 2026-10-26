export function fmtDate(v, withTime = true) {
    if (!v) return '-'
    const d = new Date(v)
    return withTime
        ? d.toLocaleString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            year: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        })
        : d.toLocaleDateString('ru-RU')
}

export function fmtNum(v) {
    if (v === null || v === undefined) return '-'
    return new Intl.NumberFormat('ru-RU').format(v)
}

export function fmtBytes(v) {
    if (v === null || v === undefined) return '-'
    const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
    let n = v
    let i = 0
    while (n >= 1024 && i < units.length - 1) {
        n /= 1024
        i += 1
    }
    return `${new Intl.NumberFormat('ru-RU', {maximumFractionDigits: i ? 1 : 0}).format(n)} ${units[i]}`
}

export function splitLines(text) {
    return text.split('\n').map((s) => s.trim()).filter(Boolean)
}
