import {createContext, useCallback, useContext, useState} from 'react'

const ToastContext = createContext(() => {
})

export function ToastProvider({children}) {
    const [items, setItems] = useState([])
    const push = useCallback((text, type = 'info') => {
        const id = Math.random().toString(36).slice(2)
        setItems((xs) => [...xs, {id, text, type}])
        setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), type === 'error' ? 7000 : 4000)
    }, [])
    return (
        <ToastContext.Provider value={push}>
            {children}
            <div className="toasts">
                {items.map((t) => (
                    <div key={t.id} className={`toast toast-${t.type}`}
                         onClick={() => setItems((xs) => xs.filter((x) => x.id !== t.id))}>
                        {t.text}
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    )
}

export const useToast = () => useContext(ToastContext)
