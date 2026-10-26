export function createGateways(http) {
    const auth = {
        login: (username, password) => http.post('/auth/login', {username, password}),
        logout: () => http.post('/auth/logout'),
        me: () => http.get('/auth/me'),
        changePassword: (oldPassword, newPassword) =>
            http.post('/auth/change-password', {old_password: oldPassword, new_password: newPassword}),
    }

    const users = {
        list: () => http.get('/users'),
        create: (username, password) => http.post('/users', {username, password}),
        remove: (id) => http.del(`/users/${id}`),
    }

    const accounts = {
        list: (status) => http.get('/accounts', {status}),
        get: (id) => http.get(`/accounts/${id}`),
        update: (id, changes) => http.patch(`/accounts/${id}`, changes),
        remove: (id, logout = false) => http.del(`/accounts/${id}`, {logout}),
        check: (id) => http.post(`/accounts/${id}/check`),
        checkAll: () => http.post('/accounts/check-all'),
        setPassword: (id, password) => http.post(`/accounts/${id}/password`, {password}),
        setPasswordAll: (password) => http.post('/accounts/password', {password}),
        loginStart: (data) => http.post('/accounts/login/start', data),
        loginCode: (flowId, code) => http.post('/accounts/login/code', {flow_id: flowId, code}),
        loginPassword: (flowId, password) => http.post('/accounts/login/password', {flow_id: flowId, password}),
        importSessions: ({files = [], strings = '', proxyId = null, proxy = null, twofa = ''}) => {
            const form = new FormData()
            files.forEach((f) => form.append('files', f))
            form.append('string_sessions', strings)
            if (proxyId) form.append('proxy_id', proxyId)
            if (proxy) form.append('proxy', proxy)
            form.append('twofa', twofa)
            return http.postForm('/accounts/import', form)
        },
    }

    const chats = {
        dialogs: (accountId, refresh = false) => http.get(`/accounts/${accountId}/dialogs`, {refresh: refresh || undefined}),
        history: (accountId, peerId, {limit, offsetId} = {}) =>
            http.get(`/accounts/${accountId}/dialogs/${peerId}/messages`, {limit, offset_id: offsetId}),
        newMessages: (accountId, peerId, afterId) =>
            http.get(`/accounts/${accountId}/dialogs/${peerId}/messages/new`, {after_id: afterId}),
        replies: (accountId, peerId, msgId) => http.get(`/accounts/${accountId}/dialogs/${peerId}/messages/${msgId}/replies`),
        send: (accountId, peerId, data) => http.post(`/accounts/${accountId}/dialogs/${peerId}/send`, data),
        sendTo: (accountId, target, text) => http.post(`/accounts/${accountId}/send-to`, {target, text}),
        comment: (accountId, data) => http.post(`/accounts/${accountId}/comment`, data),
        join: (accountId, target) => http.post(`/accounts/${accountId}/join`, {target}),
        leave: (accountId, target) => http.post(`/accounts/${accountId}/leave`, {target}),
        readAll: (accountId) => http.post(`/accounts/${accountId}/read-all`),
        comments: (accountId, params) => http.get(`/accounts/${accountId}/comments`, params),
        scanComments: (accountId, dialogLimit) =>
            http.post(`/accounts/${accountId}/comments/scan`, undefined, {dialog_limit: dialogLimit}),
    }

    const proxies = {
        list: () => http.get('/proxies'),
        create: (url, name) => http.post('/proxies', {url, name}),
        createMany: (text) => http.post('/proxies/bulk', {text}),
        update: (id, changes) => http.patch(`/proxies/${id}`, changes),
        remove: (id, force = false) => http.del(`/proxies/${id}`, {force}),
        check: (id) => http.post(`/proxies/${id}/check`),
        checkAll: () => http.post('/proxies/check-all'),
        assign: (maxPerProxy, onlyWorking) =>
            http.post('/proxies/assign', {max_per_proxy: maxPerProxy, only_working: onlyWorking}),
    }

    const tasks = {
        start: (action, data) => http.post(`/bulk/${action}`, data), // send | join | leave
        list: (params) => http.get('/tasks', params),
        get: (id) => http.get(`/tasks/${id}`),
        cancel: (id) => http.post(`/tasks/${id}/cancel`),
        remove: (id) => http.del(`/tasks/${id}`),
    }

    const stats = {
        summary: (accountId) => http.get('/stats/summary', {account_id: accountId}),
        messages: (params) => http.get('/stats/messages', params),
        message: (id) => http.get(`/stats/messages/${id}`),
        refresh: ({ids, accountId} = {}) => http.post('/stats/messages/refresh', {ids, account_id: accountId}),
        track: (accountId, link) => http.post('/stats/messages/track', {account_id: accountId, link}),
        untrack: (id) => http.del(`/stats/messages/${id}`),
        comments: (params) => http.get('/stats/comments', params),
        chatMessages: (accountId, days) => http.get('/stats/chat-messages', {account_id: accountId, days}),
    }

    const messages = {
        feed: (params) => http.get('/messages', params),
        chats: (accountId) => http.get('/messages/chats', {account_id: accountId}),
        summary: (accountId) => http.get('/messages/summary', {account_id: accountId}),
        sync: (accountId, dialogLimit) => http.post('/messages/sync', {
            account_id: accountId,
            dialog_limit: dialogLimit
        }),
        readAll: (accountId = null) => http.post('/messages/read-all', {account_id: accountId}),
        retryMedia: (id) => http.post(`/messages/${id}/media`),
    }

    const media = {
        stats: (accountId, days) => http.get('/media/stats', {account_id: accountId, days}),
    }

    return {auth, users, accounts, chats, proxies, tasks, stats, messages, media}
}
