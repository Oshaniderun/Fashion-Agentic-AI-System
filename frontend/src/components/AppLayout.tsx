import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar, Topbar } from './Navbar';

export function AppLayout() {
  const [open, setOpen] = useState(false);

  return (
    <div className="app-shell">
      {open && <div className="sidebar-backdrop" onClick={() => setOpen(false)} />}
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="main-area">
        <Topbar onMenu={() => setOpen(true)} />
        <Outlet />
      </div>
    </div>
  );
}
