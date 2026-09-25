import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Menu } from 'lucide-react';
import { Sidebar } from './Navbar';

export function AppLayout() {
  const [open, setOpen] = useState(false);

  return (
    <div className="app-shell">
      {open && <div className="sidebar-backdrop" onClick={() => setOpen(false)} />}
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <button type="button" className="menu-fab" onClick={() => setOpen(true)} aria-label="Open menu">
        <Menu size={18} />
      </button>
      <div className="main-area">
        <Outlet />
      </div>
    </div>
  );
}
