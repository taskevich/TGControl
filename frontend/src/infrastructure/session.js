const KEY = 'tgc_token'

export function createSession() {
    const listeners = new Set()
    return {
        getToken() {
            try {
                return localStorage.getItem(KEY)
            } catch {
                return null
            }
        },
        setToken(v) {
            try {
                v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY)
            } catch { /* ignore */
            }
        },
        expire() {
            listeners.forEach((fn) => fn())
        },
        onExpired(fn) {
            listeners.add(fn)
            return () => listeners.delete(fn)
        },
    }
}
