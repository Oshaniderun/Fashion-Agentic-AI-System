import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppLayout } from './components/AppLayout';
import { LoginRegister } from './pages/LoginRegister';
import { Dashboard } from './pages/Dashboard';
import { FashionRequest } from './pages/FashionRequest';
import { Wardrobe } from './pages/Wardrobe';
import { AddClothing } from './pages/AddClothing';
import { WardrobeItemDetail } from './pages/WardrobeItemDetail';
import { AnalysisResult } from './pages/AnalysisResult';
import { AgentStatusPage } from './pages/AgentStatus';
import { Agent2Dashboard } from './pages/agent2/Agent2Dashboard';
import { Agent2Search } from './pages/agent2/Agent2Search';
import { Agent2ProductDetail } from './pages/agent2/Agent2ProductDetail';
import { Agent2History } from './pages/agent2/Agent2History';
import { Agent2StatusPage } from './pages/agent2/Agent2Status';
import { Settings } from './pages/Settings';
import { SecurityLab } from './pages/SecurityLab';
import { LoadingSkeleton } from './components/LoadingSkeleton';

function ProtectedRoutes() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="page" style={{ maxWidth: 480, margin: '4rem auto' }}>
        <LoadingSkeleton rows={4} />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginRegister />} />
        <Route element={<ProtectedRoutes />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/request" element={<FashionRequest />} />
            <Route path="/wardrobe" element={<Wardrobe />} />
            <Route path="/wardrobe/add" element={<AddClothing />} />
            <Route path="/wardrobe/:id" element={<WardrobeItemDetail />} />
            <Route path="/analysis/:requestId" element={<AnalysisResult />} />
            <Route path="/agent" element={<AgentStatusPage />} />
            <Route path="/agent2" element={<Agent2Dashboard />} />
            <Route path="/agent2/search" element={<Agent2Search />} />
            <Route path="/agent2/products/:productId" element={<Agent2ProductDetail />} />
            <Route path="/agent2/history" element={<Agent2History />} />
            <Route path="/agent2/status" element={<Agent2StatusPage />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/security" element={<SecurityLab />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
