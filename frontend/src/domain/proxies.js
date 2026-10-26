export const PROXY_STATUS = {ok: 'Работает', error: 'Не работает', unknown: 'Не проверен'}

export const PROXY_BADGE = {ok: 'active', error: 'error', unknown: 'new'}

export const PROXY_MARK = {ok: '✓', error: '✕', unknown: '?'}

export function proxyLabel(p) {
    if (!p) return 'Без прокси'
    const base = `${p.scheme}://${p.host}:${p.port}`
    return p.name ? `${p.name} - ${base}` : base
}

export function proxyPayload(selection) {
    if (selection.proxy_id) return {proxy_id: selection.proxy_id, proxy: null}
    if (selection.newMode && selection.proxy.trim()) return {proxy_id: null, proxy: selection.proxy.trim()}
    return {proxy_id: null, proxy: null}
}

export const NO_PROXY = {proxy_id: null, proxy: '', newMode: false}
