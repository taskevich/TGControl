import {createContext, useCallback, useContext, useEffect, useState} from 'react'
import {useServices} from './services.jsx'

const AuthContext = createContext(null)

export function AuthProvider({children}) {
    const {auth, session} = useServices()
    const [user, setUser] = useState(null)
    const [ready, setReady] = useState(false)

    const logoutLocal = useCallback(() => {
        session.setToken(null)
        setUser(null)
    }, [session])

    useEffect(() => {
        const unsubscribe = session.onExpired(logoutLocal)
        if (!session.getToken()) {
            setReady(true)
            return unsubscribe
        }
        auth.me()
            .then(setUser)
            .catch(() => session.setToken(null))
            .finally(() => setReady(true))
        return unsubscribe
    }, [auth, session, logoutLocal])

    const login = async (username, password) => {
        const res = await auth.login(username, password)
        session.setToken(res.access_token)
        setUser(await auth.me())
    }

    const logout = async () => {
        try {
            await auth.logout()
        } catch { /* ignore */
        }
        logoutLocal()
    }

    return <AuthContext.Provider value={{user, ready, login, logout}}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
