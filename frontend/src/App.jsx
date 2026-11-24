import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import AppLayout from './layouts/AppLayout'
import AttendancePage from './pages/AttendancePage'
import DashboardPage from './pages/DashboardPage'
import EmployeesPage from './pages/EmployeesPage'
import InsightsPage from './pages/InsightsPage'
import LeavesPage from './pages/LeavesPage'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'
import ReportsPage from './pages/ReportsPage'

export default function App() {
  return <Routes><Route path="/login" element={<LoginPage />} /><Route element={<ProtectedRoute />}><Route element={<AppLayout />}><Route index element={<DashboardPage />} /><Route path="attendance" element={<AttendancePage />} /><Route path="leaves" element={<LeavesPage />} /><Route path="reports" element={<ReportsPage />} /><Route path="profile" element={<ProfilePage />} /><Route path="employees" element={<EmployeesPage />} /><Route path="insights" element={<InsightsPage />} /></Route></Route><Route path="*" element={<Navigate to="/" replace />} /></Routes>
}
