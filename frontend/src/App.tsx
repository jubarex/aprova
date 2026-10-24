import { Navigate, Route, Routes } from 'react-router-dom'
import { useSession } from '@/lib/session'
import { AppShell } from '@/layout/AppShell'
import { PortalLayout } from '@/portal/PortalLayout'
import PortalHomePage from '@/portal/PortalHome'
import PortalApprovalPage from '@/portal/PortalApproval'
import PortalItemPage from '@/portal/PortalItem'
import { PortalEnter, PortalHistory, PortalFirstAccess } from '@/portal/PortalMisc'
import InboxPage from '@/pages/Inbox'
import SchedulePage from '@/pages/Schedule'
import MetricsPage from '@/pages/Metrics'
import CatalogPage from '@/pages/Catalog'
import LoginPage from '@/pages/Login'
import TodayPage from '@/pages/Today'
import CaseDetailPage from '@/pages/CaseDetail'
import InterventionsPage from '@/pages/Interventions'
import ClientsPage from '@/pages/Clients'
import NewTicketPage from '@/pages/NewTicket'
import DemoSettingsPage from '@/pages/DemoSettings'
import { Skeleton } from '@/components/ui/skeleton'

export default function App() {
  const { me, loading } = useSession()
  if (window.location.pathname === '/portal/entrar') return <PortalEnter />
  if (loading) return <div className="p-6"><Skeleton className="h-10 w-64" /></div>
  if (!me) return <LoginPage />

  if (me.kind === 'contato') {
    return (
      <Routes>
        <Route path="/portal" element={<PortalLayout />}>
          <Route index element={<PortalHomePage />} />
          <Route path="aprovacoes/:id" element={<PortalApprovalPage />} />
          <Route path="pendencias/:id" element={<PortalItemPage />} />
          <Route path="historico" element={<PortalHistory />} />
          <Route path="primeiro-acesso" element={<PortalFirstAccess />} />
        </Route>
        <Route path="*" element={<Navigate to="/portal" replace />} />
      </Routes>
    )
  }
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<TodayPage />} />
        <Route path="processes/new" element={<NewTicketPage />} />
        <Route path="processes/:id" element={<CaseDetailPage />} />
        <Route path="inbox" element={<InboxPage />} />
        <Route path="interventions" element={<InterventionsPage />} />
        <Route path="schedule" element={<SchedulePage />} />
        <Route path="metrics" element={<MetricsPage />} />
        <Route path="templates" element={<CatalogPage />} />
        <Route path="clients" element={<ClientsPage />} />
        <Route path="settings/demo" element={<DemoSettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
