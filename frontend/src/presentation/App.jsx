import {Navigate, Route, Routes} from 'react-router-dom'
import {useAuth} from '../application/auth.jsx'
import Layout from './components/Layout.jsx'
import Login from './pages/Login.jsx'
import Accounts from './pages/Accounts.jsx'
import AccountView from './pages/AccountView.jsx'
import Broadcast from './pages/Broadcast.jsx'
import JoinLeave from './pages/JoinLeave.jsx'
import Tasks from './pages/Tasks.jsx'
import TaskDetail from './pages/TaskDetail.jsx'
import Stats from './pages/Stats.jsx'
import MessageDetail from './pages/MessageDetail.jsx'
import Comments from './pages/Comments.jsx'
import Messages from './pages/Messages.jsx'
import Files from './pages/Files.jsx'
import Settings from './pages/Settings.jsx'
import Proxies from './pages/Proxies.jsx'

export default function App() {
    const {user, ready} = useAuth()
    if (!ready) return <div className="splash">Загрузка...</div>
    if (!user) {
        return (
            <Routes>
                <Route path="*" element={<Login/>}/>
            </Routes>
        )
    }
    return (
        <Layout>
            <Routes>
                <Route path="/" element={<Navigate to="/accounts" replace/>}/>
                <Route path="/accounts" element={<Accounts/>}/>
                <Route path="/accounts/:id" element={<AccountView/>}/>
                <Route path="/accounts/:id/:tab" element={<AccountView/>}/>
                <Route path="/broadcast" element={<Broadcast/>}/>
                <Route path="/join-leave" element={<JoinLeave/>}/>
                <Route path="/tasks" element={<Tasks/>}/>
                <Route path="/tasks/:id" element={<TaskDetail/>}/>
                <Route path="/stats" element={<Stats/>}/>
                <Route path="/stats/:id" element={<MessageDetail/>}/>
                <Route path="/comments" element={<Comments/>}/>
                <Route path="/messages" element={<Messages/>}/>
                <Route path="/files" element={<Files/>}/>
                <Route path="/proxies" element={<Proxies/>}/>
                <Route path="/settings" element={<Settings/>}/>
                <Route path="*" element={<Navigate to="/accounts" replace/>}/>
            </Routes>
        </Layout>
    )
}
