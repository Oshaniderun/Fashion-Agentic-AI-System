import {
  LayoutDashboard,
  Shirt,
  PlusCircle,
  Sparkles,
  Search,
  Boxes,
  Wallet,
  LogOut,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const LINKS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/request', label: 'Fashion Request', icon: Sparkles },
  { to: '/wardrobe', label: 'Wardrobe', icon: Shirt, end: true },
  { to: '/wardrobe/add', label: 'Add Clothing', icon: PlusCircle },
  { to: '/agent2/search', label: 'Product Search', icon: Search },
  { to: '/agent2', label: 'Retrieval History', icon: Boxes, end: true },
  { to: '/budget', label: 'Budget', icon: Wallet },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: Props) {
  const { user, logout } = useAuth();

  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="brand">
        <p className="brand-mark">FASHORA</p>
        <p className="brand-sub">Style & Wardrobe Intelligence</p>
      </div>
      <nav>
        <ul className="nav-list">
          {LINKS.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                onClick={onClose}
              >
                <Icon />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="sidebar-foot">
        <div className="meta" style={{ marginBottom: 8 }}>
          {user?.name}
          <br />
          {user?.email}
        </div>
        <button type="button" className="btn btn-ghost" style={{ width: '100%' }} onClick={logout}>
          <LogOut size={16} /> Sign out
        </button>
      </div>
    </aside>
  );
}
