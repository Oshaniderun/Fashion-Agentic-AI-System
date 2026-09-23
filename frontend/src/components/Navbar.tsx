import {
  LayoutDashboard,
  Shirt,
  PlusCircle,
  Sparkles,
  Menu,
  LogOut,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { API_DOCS_URL } from '../config';

const LINKS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/request', label: 'Fashion Request', icon: Sparkles },
  { to: '/wardrobe', label: 'Wardrobe', icon: Shirt },
  { to: '/wardrobe/add', label: 'Add Clothing', icon: PlusCircle },
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

export function Topbar({ onMenu }: { onMenu: () => void }) {
  return (
    <header className="topbar">
      <button type="button" className="menu-btn" onClick={onMenu} aria-label="Open menu">
        <Menu size={18} />
      </button>
      <div className="meta">Agent 1 · Wardrobe Intelligence</div>
      <a className="btn btn-secondary" href={API_DOCS_URL} target="_blank" rel="noreferrer">
        API Docs
      </a>
    </header>
  );
}
