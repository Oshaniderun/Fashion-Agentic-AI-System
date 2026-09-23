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
            <Route path="/settings" element={<Settings />} />
            <Route path="/security" element={<SecurityLab />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
