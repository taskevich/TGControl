export function linkify(text) {
    if (!text) return text
    const parts = text.split(/(https?:\/\/\S+)/g)
    return parts.map((p, i) =>
        /^https?:\/\//.test(p) ? (
            <a key={i} href={p} target="_blank" rel="noreferrer">{p}</a>
        ) : (
            p
        ),
    )
}
