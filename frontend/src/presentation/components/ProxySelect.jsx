import {useQuery} from '../../application/hooks.js'
import {useServices} from '../../application/services.jsx'
import {PROXY_MARK, proxyLabel} from '../../domain/proxies.js'


export default function ProxySelect({value, onChange, label = 'Прокси', hint}) {
    const svc = useServices()
    const {data: proxies} = useQuery(() => svc.proxies.list(), [])
    const mode = value.proxy_id ? String(value.proxy_id) : value.newMode ? 'new' : ''
    return (
        <div className="field">
            <span>{label} <span className="muted">- необязательно</span></span>
            <select
                value={mode}
                onChange={(e) => {
                    const v = e.target.value
                    if (v === 'new') onChange({proxy_id: null, proxy: '', newMode: true})
                    else onChange({proxy_id: v ? Number(v) : null, proxy: '', newMode: false})
                }}
            >
                <option value="">Без прокси (прямое подключение)</option>
                {(proxies || []).map((p) => (
                    <option key={p.id} value={p.id} disabled={!p.is_active}>
                        {PROXY_MARK[p.status] || ''} {proxyLabel(p)}
                        {p.accounts_count ? ` · аккаунтов: ${p.accounts_count}` : ''}
                        {p.latency_ms ? ` · ${p.latency_ms} мс` : ''}
                        {!p.is_active ? ' (отключён)' : ''}
                    </option>
                ))}
                <option value="new">+ Новый прокси...</option>
            </select>
            {mode === 'new' && (
                <input
                    value={value.proxy}
                    onChange={(e) => onChange({...value, proxy: e.target.value})}
                    placeholder="socks5://user:pass@host:port или host:port:user:pass"
                    autoFocus
                />
            )}
            {hint && <span className="muted small">{hint}</span>}
        </div>
    )
}
