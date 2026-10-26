import {useEffect, useState} from 'react'
import {STATUS_LABELS, accountLabel, countUsable, splitSecret} from '../../domain/accounts.js'
import Icon from './Icon.jsx'
import {copyText} from '../clipboard.js'
import {useToast} from './Toast.jsx'

export function Badge({status, children}) {
    return <span className={`badge badge-${status}`}>{children || STATUS_LABELS[status] || status}</span>
}

export function Modal({title, onClose, children, wide = false, footer}) {
    useEffect(() => {
        const onKey = (e) => e.key === 'Escape' && onClose()
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [onClose])
    return (
        <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
            <div className={`modal${wide ? ' modal-wide' : ''}`}>
                <div className="modal-head">
                    <h3>{title}</h3>
                    <button className="btn-icon" onClick={onClose} aria-label="Закрыть">
                        <Icon name="close"/>
                    </button>
                </div>
                <div className="modal-body">{children}</div>
                {footer && <div className="modal-foot">{footer}</div>}
            </div>
        </div>
    )
}

export function SecretValue({value, empty = '-'}) {
    const toast = useToast()
    const [copied, setCopied] = useState(false)
    if (!value) return <span className="muted">{empty}</span>
    const [visible, hidden] = splitSecret(value)
    const copy = async (e) => {
        e.preventDefault()
        e.stopPropagation()
        try {
            await copyText(value)
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
        } catch {
            toast('Не удалось скопировать', 'error')
        }
    }
    return (
        <span className="secret">
      <span className="mono">
        {visible}
          <span className="secret-blur" aria-hidden="true">{hidden}</span>
      </span>
      <button type="button" className="btn-icon btn-icon-sm" title={copied ? 'Скопировано' : 'Копировать'}
              onClick={copy}>
        <Icon name="copy" size={14}/>
      </button>
            {copied && <span className="muted small">скопировано</span>}
    </span>
    )
}

export function PageHeader({title, subtitle, children}) {
    return (
        <div className="page-header">
            <div>
                <h1>{title}</h1>
                {subtitle && <div className="muted">{subtitle}</div>}
            </div>
            <div className="page-actions">{children}</div>
        </div>
    )
}

export function Pagination({page, pageSize, total, onChange}) {
    const pages = Math.max(1, Math.ceil(total / pageSize))
    if (pages <= 1) return null
    return (
        <div className="pagination">
            <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>←</button>
            <span className="muted small">
        {page} / {pages} · всего {total}
      </span>
            <button className="btn btn-ghost btn-sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>→
            </button>
        </div>
    )
}

export function Empty({children}) {
    return <div className="empty">{children}</div>
}

export function Spinner() {
    return <span className="spinner" aria-label="Загрузка"/>
}

export function Progress({value, total}) {
    const pct = total ? Math.round((value / total) * 100) : 0
    return (
        <div className="progress" title={`${value} / ${total}`}>
            <div className="progress-bar" style={{width: `${pct}%`}}/>
        </div>
    )
}

export function AccountPicker({accounts, value, onChange}) {
    const {all, ids} = value
    const enabled = (accounts || []).filter((a) => a.is_enabled)
    const toggle = (id) => onChange({all, ids: ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]})
    return (
        <div className="picker">
            <div className="seg">
                <button type="button" className={all ? 'active' : ''} onClick={() => onChange({all: true, ids})}>
                    Все активные ({countUsable(enabled)})
                </button>
                <button type="button" className={!all ? 'active' : ''} onClick={() => onChange({all: false, ids})}>
                    Выбранные ({ids.length})
                </button>
            </div>
            {!all && (
                <div className="picker-list">
                    <div className="picker-tools">
                        <button type="button" className="link-btn" onClick={() => onChange({
                            all,
                            ids: enabled.filter((a) => a.status === 'active').map((a) => a.id)
                        })}>
                            выбрать активные
                        </button>
                        <button type="button" className="link-btn" onClick={() => onChange({all, ids: []})}>
                            снять всё
                        </button>
                    </div>
                    {enabled.map((a) => (
                        <label key={a.id} className="check-row">
                            <input type="checkbox" checked={ids.includes(a.id)} onChange={() => toggle(a.id)}/>
                            <span>{accountLabel(a)}</span>
                            <span className="muted small">{a.phone}</span>
                            <Badge status={a.status}/>
                        </label>
                    ))}
                    {!enabled.length && <div className="muted small">Нет включённых аккаунтов</div>}
                </div>
            )}
        </div>
    )
}
