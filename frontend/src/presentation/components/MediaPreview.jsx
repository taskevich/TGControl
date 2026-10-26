import {useEffect} from 'react'
import Icon from './Icon.jsx'
import {MEDIA_KINDS, downloadUrl, previewType} from '../../domain/chats.js'
import {fmtBytes, fmtDate} from '../../domain/format.js'

export function MediaThumb({m, onOpen}) {
    const type = previewType(m)
    return (
        <button className="media-thumb" onClick={() => onOpen(m)} title={m.media_name || ''}>
            {type === 'image' && <img src={m.media_url} alt="" loading="lazy"/>}
            {type === 'video' && (
                <>
                    <video src={m.media_url} preload="metadata" muted playsInline/>
                    <span className="media-thumb-play">▶</span>
                </>
            )}
            {(type === 'audio' || type === 'pdf' || type === 'other') && (
                <span className="media-thumb-icon">
          <span>{type === 'audio' ? '♪' : type === 'pdf' ? 'PDF' : 'FILE'}</span>
          <span className="small">{MEDIA_KINDS[m.media] || m.media}</span>
        </span>
            )}
        </button>
    )
}

export function InlineMedia({m, onOpen}) {
    const type = previewType(m)
    if (type === 'image') {
        return (
            <button className="inline-media" onClick={() => onOpen(m)}>
                <img src={m.media_url} alt="" loading="lazy"/>
            </button>
        )
    }
    if (type === 'video') return <video className="inline-media" src={m.media_url} controls preload="metadata"/>
    if (type === 'audio') return <audio className="inline-audio" src={m.media_url} controls preload="none"/>
    return null
}

export function MediaViewer({m, onClose, onPrev, onNext}) {
    useEffect(() => {
        const onKey = (e) => {
            if (e.key === 'Escape') onClose()
            if (e.key === 'ArrowLeft' && onPrev) onPrev()
            if (e.key === 'ArrowRight' && onNext) onNext()
        }
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [onClose, onPrev, onNext])

    const type = previewType(m)
    return (
        <div className="viewer-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
            <div className="viewer">
                <div className="viewer-head">
                    <div className="clip">
                        <strong>{m.media_name || MEDIA_KINDS[m.media] || m.media}</strong>
                        <div className="muted small clip">
                            {fmtBytes(m.media_size)} · {m.chat_title || m.chat_id} · {fmtDate(m.date)}
                        </div>
                    </div>
                    <span className="row">
            <a className="btn btn-sm btn-primary" href={downloadUrl(m)}>Скачать</a>
                        {m.link && <a className="btn btn-sm btn-ghost" href={m.link} target="_blank" rel="noreferrer">В
                            Telegram</a>}
                        <button className="btn-icon" onClick={onClose} aria-label="Закрыть"><Icon
                            name="close"/></button>
          </span>
                </div>
                <div className="viewer-body">
                    {onPrev &&
                        <button className="viewer-nav viewer-prev" onClick={onPrev} aria-label="Предыдущий">‹</button>}
                    {type === 'image' && <img src={m.media_url} alt=""/>}
                    {type === 'video' && <video key={m.id} src={m.media_url} controls autoPlay playsInline/>}
                    {type === 'audio' && <audio key={m.id} src={m.media_url} controls autoPlay/>}
                    {type === 'pdf' && <iframe title={m.media_name || 'pdf'} src={m.media_url}/>}
                    {type === 'other' && (
                        <div className="viewer-file">
                            <div className="media-thumb-icon big"><span>FILE</span></div>
                            <div>{m.media_name || 'Файл'}</div>
                            <div className="muted small">{m.media_mime} · {fmtBytes(m.media_size)}</div>
                            <a className="btn btn-primary mt" href={downloadUrl(m)}>Скачать</a>
                        </div>
                    )}
                    {onNext &&
                        <button className="viewer-nav viewer-next" onClick={onNext} aria-label="Следующий">›</button>}
                </div>
                {m.text && <div className="viewer-caption">{m.text}</div>}
            </div>
        </div>
    )
}
