'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Bell, Briefcase, FileText, Home, LogOut, Settings, UserRound, ChevronDown, Sparkles } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

// Primary navigation items
const primaryNav = [
  ['Home', '/', Home],
  ['Discover', '/jobs', Briefcase],
  ['My CV', '/cv', FileText],
  ['Applications', '/applications', Briefcase],
  ['Activity Log', '/activity', Sparkles],
];

// User menu items
const userMenuItems = [
  ['Profile', '/profile', UserRound],
  ['Settings', '/settings', Settings],
];

export default function CandidateShell({ children }) {
  const path = usePathname();
  const { user, logout } = useAuth();
  const [desktopMenuOpen, setDesktopMenuOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showNotificationDropdown, setShowNotificationDropdown] = useState(false);

  const desktopMenuRef = useRef(null);
  const notificationRef = useRef(null);

  // Close desktop menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (desktopMenuRef.current && !desktopMenuRef.current.contains(event.target)) {
        setDesktopMenuOpen(false);
      }
      if (notificationRef.current && !notificationRef.current.contains(event.target)) {
        setShowNotificationDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    setDesktopMenuOpen(false);
    setMobileMenuOpen(false);
    await logout();
  };

  // Placeholder notifications
  const notifications = [
    { id: 1, message: 'Application sent to Speechify', time: '2 hours ago', unread: true },
    { id: 2, message: 'New job match: Senior Developer at Google', time: '5 hours ago', unread: true },
    { id: 3, message: 'Your CV was viewed by Amazon', time: '1 day ago', unread: false },
  ];

  return (
    <div className="shell">
      <header className="topbar">
        {/* Logo / Brand */}
        <Link className="brand" href="/">
          <b>n</b>ext<span className="brand-accent">role</span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="desktop-nav">
          {primaryNav.map(([label, href]) => (
            <Link
              key={href}
              href={href}
              className={`nav-link ${path === href ? 'active' : ''}`}
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* Desktop User Menu Dropdown */}
        <div className="user-menu" ref={desktopMenuRef}>
          {/* Notification Icon with Dropdown */}
          <div className="notification-menu" ref={notificationRef}>
            <button
              className="notification-button"
              onClick={() => setShowNotificationDropdown(!showNotificationDropdown)}
              aria-label="Notifications"
            >
              <Bell size={18} />
              {notifications.some(n => n.unread) && (
                <span className="notification-badge" />
              )}
            </button>

            {showNotificationDropdown && (
              <div className="notification-dropdown">
                <div className="notification-header">
                  <h3>Notifications</h3>
                </div>
                <div className="notification-list">
                  {notifications.length === 0 ? (
                    <div className="notification-empty">No notifications</div>
                  ) : (
                    notifications.map((notification) => (
                      <div
                        key={notification.id}
                        className={`notification-item ${notification.unread ? 'unread' : ''}`}
                      >
                        <p className="notification-message">{notification.message}</p>
                        <p className="notification-time">{notification.time}</p>
                      </div>
                    ))
                  )}
                </div>
                <Link
                  href="/notifications"
                  className="notification-view-all"
                  onClick={() => setShowNotificationDropdown(false)}
                >
                  View all notifications
                </Link>
              </div>
            )}
          </div>

          <button
            className="user-menu-button"
            onClick={() => setDesktopMenuOpen(!desktopMenuOpen)}
            aria-label="User menu"
          >
            <UserRound size={18} />
            <ChevronDown size={16} className={desktopMenuOpen ? 'open' : ''} />
          </button>

          {desktopMenuOpen && (
            <div className="user-menu-dropdown">
              {user && (
                <div className="user-menu-header">
                  <p className="user-name">{user.email}</p>
                </div>
              )}
              <nav className="user-menu-items">
                {userMenuItems.map(([label, href, Icon]) => (
                  <Link
                    key={label}
                    href={href}
                    className="user-menu-item"
                    onClick={() => setDesktopMenuOpen(false)}
                  >
                    <Icon size={16} />
                    {label}
                  </Link>
                ))}
              </nav>
              <button className="user-menu-item logout" onClick={handleLogout}>
                <LogOut size={16} />
                Sign out
              </button>
            </div>
          )}
        </div>
      </header>

      <main>{children}</main>

      {/* Mobile Bottom Navigation Bar */}
      <nav className="mobile-nav">
        {primaryNav.slice(0, 5).map(([label, href, Icon]) => (
          <Link
            key={href}
            href={href}
            className={`mobile-nav-link ${path === href ? 'active' : ''}`}
            onClick={() => setMobileMenuOpen(false)}
          >
            <Icon size={20} />
            <span className="mobile-nav-label">{label}</span>
          </Link>
        ))}
        <button
          className={`mobile-nav-link user-menu-mobile ${mobileMenuOpen ? 'active' : ''}`}
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="User menu"
        >
          <UserRound size={20} />
          <span className="mobile-nav-label">Account</span>
        </button>
      </nav>

      {/* Mobile User Menu Sheet */}
      {mobileMenuOpen && (
        <div className="mobile-user-menu">
          {user && (
            <div className="mobile-user-header">
              <p className="mobile-user-email">{user.email}</p>
            </div>
          )}
          <nav className="mobile-user-items">
            {userMenuItems.map(([label, href, Icon]) => (
              <Link
                key={label}
                href={href}
                className="mobile-user-item"
                onClick={() => setMobileMenuOpen(false)}
              >
                <Icon size={16} />
                {label}
              </Link>
            ))}
          </nav>
          <button
            className="mobile-user-item logout"
            onClick={handleLogout}
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
