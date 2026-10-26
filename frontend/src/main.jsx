import React from 'react'
import ReactDOM from 'react-dom/client'
import {BrowserRouter} from 'react-router-dom'
import {AuthProvider} from './application/auth.jsx'
import {ServicesProvider} from './application/services.jsx'
import {createGateways} from './infrastructure/gateways.js'
import {createHttpClient} from './infrastructure/http.js'
import {createSession} from './infrastructure/session.js'
import App from './presentation/App.jsx'
import {ToastProvider} from './presentation/components/Toast.jsx'
import './styles.css'

const session = createSession()
const http = createHttpClient({baseUrl: import.meta.env.VITE_API_URL || '', session})
const services = {session, ...createGateways(http)}

ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
        <BrowserRouter>
            <ServicesProvider services={services}>
                <ToastProvider>
                    <AuthProvider>
                        <App/>
                    </AuthProvider>
                </ToastProvider>
            </ServicesProvider>
        </BrowserRouter>
    </React.StrictMode>,
)
