import {ServiceError} from '../application/errors.js'

const KINDS = {
    400: 'invalid',
    401: 'unauthorized',
    403: 'forbidden',
    404: 'not_found',
    409: 'conflict',
    410: 'expired',
    422: 'invalid',
    429: 'rate_limited'
}

function errorMessage(data, fallback) {
    let msg = data && data.detail
    if (Array.isArray(msg)) msg = msg.map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ')
    return msg || fallback || 'Ошибка запроса'
}

function fileName(res, fallback) {
    const header = res.headers.get('Content-Disposition') || ''
    const m = header.match(/filename\*=UTF-8''([^;]+)/i)
    return m ? decodeURIComponent(m[1]) : fallback
}

export function createHttpClient({baseUrl, session}) {
    async function request(path, {method = 'GET', body, form, params, file = false} = {}) {
        let url = `${baseUrl}/api${path}`
        if (params) {
            const qs = new URLSearchParams()
            Object.entries(params).forEach(([k, v]) => {
                if (v !== undefined && v !== null && v !== '') qs.append(k, v)
            })
            const s = qs.toString()
            if (s) url += `?${s}`
        }
        const headers = {}
        const token = session.getToken()
        if (token) headers.Authorization = `Bearer ${token}`
        let payload
        if (form) payload = form
        else if (body !== undefined) {
            headers['Content-Type'] = 'application/json'
            payload = JSON.stringify(body)
        }

        let res
        try {
            res = await fetch(url, {method, headers, body: payload})
        } catch {
            throw new ServiceError('Сервер недоступен', 'unavailable')
        }
        if (res.status === 401 && !path.startsWith('/auth/login')) session.expire()
        if (file && res.ok) return {blob: await res.blob(), name: fileName(res, 'download')}

        const text = await res.text()
        let data = null
        try {
            data = text ? JSON.parse(text) : null
        } catch {
            data = text
        }
        if (!res.ok) throw new ServiceError(errorMessage(data, res.statusText), KINDS[res.status] || 'failed')
        return data
    }

    return {
        get: (path, params) => request(path, {params}),
        file: (path, params) => request(path, {params, file: true}),
        post: (path, body, params) => request(path, {method: 'POST', body, params}),
        postForm: (path, form) => request(path, {method: 'POST', form}),
        patch: (path, body) => request(path, {method: 'PATCH', body}),
        del: (path, params) => request(path, {method: 'DELETE', params}),
    }
}
