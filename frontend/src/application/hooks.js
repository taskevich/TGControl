import {useCallback, useEffect, useRef, useState} from 'react'

export function useQuery(fn, deps = []) {
    const [data, setData] = useState(null)
    const [error, setError] = useState(null)
    const [loading, setLoading] = useState(true)
    const fnRef = useRef(fn)
    fnRef.current = fn

    const reload = useCallback(async (silent = false) => {
        if (!silent) setLoading(true)
        try {
            const res = await fnRef.current()
            setData(res)
            setError(null)
            return res
        } catch (e) {
            setError(e)
        } finally {
            if (!silent) setLoading(false)
        }
    }, [])

    useEffect(() => {
        reload()
    }, deps)

    return {data, error, loading, reload, setData}
}

export function useInterval(cb, ms, enabled = true) {
    const ref = useRef(cb)
    ref.current = cb
    useEffect(() => {
        if (!enabled) return undefined
        const t = setInterval(() => ref.current(), ms)
        return () => clearInterval(t)
    }, [ms, enabled])
}

export function useDebounced(value, ms = 400) {
    const [v, setV] = useState(value)
    useEffect(() => {
        const t = setTimeout(() => setV(value), ms)
        return () => clearTimeout(t)
    }, [value, ms])
    return v
}
