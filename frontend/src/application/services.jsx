import {createContext, useContext} from 'react'

const ServicesContext = createContext(null)

export function ServicesProvider({services, children}) {
    return <ServicesContext.Provider value={services}>{children}</ServicesContext.Provider>
}

export function useServices() {
    const services = useContext(ServicesContext)
    if (!services) throw new Error('ServicesProvider is missing')
    return services
}
