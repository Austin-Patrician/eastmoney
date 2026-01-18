import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { 
  Drawer, 
  List, 
  ListItem, 
  ListItemButton, 
  ListItemIcon, 
  ListItemText, 
  Typography, 
  Box,
  Divider,
  Avatar,
  Tooltip,
  IconButton,
  Menu,
  MenuItem
} from '@mui/material';
import PieChartIcon from '@mui/icons-material/PieChart';
import ArticleIcon from '@mui/icons-material/Article';
import SettingsIcon from '@mui/icons-material/Settings';
import AutoGraphIcon from '@mui/icons-material/AutoGraph';
import MonetizationOnIcon from '@mui/icons-material/MonetizationOn';
import PublicIcon from '@mui/icons-material/Public';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import ArrowDropUpIcon from '@mui/icons-material/ArrowDropUp';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import SpeedIcon from '@mui/icons-material/Speed';
import LanguageIcon from '@mui/icons-material/Language';
import LogoutIcon from '@mui/icons-material/Logout';
import PersonIcon from '@mui/icons-material/Person';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import MenuBookIcon from '@mui/icons-material/MenuBook';

import { fetchMarketIndices } from '../../api';
import type {IndexData} from '../../api';

const drawerWidth = 260;

export default function Layout() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [indices, setIndices] = useState<IndexData[]>([]);
  const [username, setUsername] = useState<string>('User');
  
  // Language Menu State
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };
  const handleClose = (lang?: string) => {
    if (lang) {
      i18n.changeLanguage(lang);
    }
    setAnchorEl(null);
  };

  // User Menu State
  const [userAnchorEl, setUserAnchorEl] = useState<null | HTMLElement>(null);
  const userOpen = Boolean(userAnchorEl);
  const handleUserClick = (event: React.MouseEvent<HTMLElement>) => {
    setUserAnchorEl(event.currentTarget);
  };
  const handleUserClose = () => {
    setUserAnchorEl(null);
  };
  const handleLogout = () => {
      localStorage.removeItem('token');
      window.location.href = '/login';
  };

  const MENU_ITEMS = useMemo(() => [
    { text: t('layout.menu.dashboard'), icon: <SpeedIcon />, path: '/dashboard', subtitle: t('layout.menu.dashboard_sub') },
    { text: t('layout.menu.universe'), icon: <PieChartIcon />, path: '/funds', subtitle: t('layout.menu.universe_sub') },
    { text: t('layout.menu.stocks'), icon: <ShowChartIcon />, path: '/stocks', subtitle: t('layout.menu.stocks_sub') },
    { text: t('layout.menu.recommendations'), icon: <AutoAwesomeIcon />, path: '/recommendations', subtitle: t('layout.menu.recommendations_sub') },
    { text: t('layout.menu.sentiment'), icon: <AutoGraphIcon />, path: '/sentiment', subtitle: t('layout.menu.sentiment_sub') },
    { text: t('layout.menu.intelligence'), icon: <ArticleIcon />, path: '/reports', subtitle: t('layout.menu.intelligence_sub') },
    { text: t('layout.menu.commodities'), icon: <MonetizationOnIcon />, path: '/commodities', subtitle: t('layout.menu.commodities_sub') },
    { text: t('layout.menu.system'), icon: <SettingsIcon />, path: '/settings', subtitle: t('layout.menu.system_sub') },
  ], [t]);

  useEffect(() => {
    // Load Indices
    const loadIndices = async () => {
      try {
        const data = await fetchMarketIndices();
        setIndices(data);
      } catch (err) {
        console.error("Failed to load market indices", err);
      }
    };
    
    // Load User Info
    const loadUser = async () => {
        try {
            // We can decode token or fetch /api/auth/me
            // Let's decode token for speed, or assume it's valid if we are here (guarded by PrivateRoute)
            const token = localStorage.getItem('token');
            if (token) {
                try {
                    // Simple parse
                    const base64Url = token.split('.')[1];
                    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                    const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function(c) {
                        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                    }).join(''));
                    const payload = JSON.parse(jsonPayload);
                    setUsername(payload.sub || 'User');
                } catch (e) {
                    console.error("Failed to parse token", e);
                }
            }
        } catch (err) {
            console.error(err);
        }
    };

    loadIndices();
    loadUser();
    const timer = setInterval(loadIndices, 60000); // Refresh every 60s
    return () => clearInterval(timer);
  }, []);

  const currentItem = MENU_ITEMS.find(item => location.pathname.startsWith(item.path)) || MENU_ITEMS[0];

  return (
    <div className="flex min-h-screen bg-white text-slate-900 font-sans">
      {/* Navigation Sidebar */}
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: { 
            width: drawerWidth, 
            boxSizing: 'border-box',
            borderRight: '1px solid #f1f5f9',
            backgroundColor: '#ffffff',
          },
        }}
      >
        <div className="h-20 flex items-center px-6 border-b border-slate-50">
          <img src="/vite.svg" alt="Logo" className="w-8 h-8 mr-3 shadow-sm rounded-xl" />
          <div className="flex flex-col">
            <Typography variant="h6" className="tracking-wide font-bold text-slate-900 leading-none" sx={{ fontFamily: 'JetBrains Mono' }}>
              V<span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-500 to-purple-600">{t('layout.title')}</span>
            </Typography>
          </div>
        </div>
        
        <div className="flex-1 py-6 px-3 overflow-y-auto">
          <List className="space-y-1">
            {MENU_ITEMS.map((item) => {
               const isActive = location.pathname.startsWith(item.path);
               return (
                <ListItem key={item.path} disablePadding>
                  <ListItemButton 
                    selected={isActive}
                    onClick={() => navigate(item.path)}
                    sx={{
                      borderRadius: '12px',
                      py: 1.5,
                      '&.Mui-selected': {
                        backgroundColor: '#f8fafc',
                        '&:hover': { backgroundColor: '#f1f5f9' },
                        '&::before': {
                            content: '""',
                            position: 'absolute',
                            left: -12,
                            width: 4,
                            height: 24,
                            borderRadius: '0 4px 4px 0',
                            bgcolor: '#6366f1'
                        }
                      },
                      '&:hover': { backgroundColor: '#f8fafc' }
                    }}
                  >
                    <ListItemIcon sx={{ 
                      minWidth: 40, 
                      color: isActive ? '#6366f1' : '#94a3b8' 
                    }}>
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText 
                      primary={item.text} 
                      primaryTypographyProps={{ 
                        fontWeight: isActive ? 800 : 600,
                        fontSize: '0.85rem',
                        color: isActive ? '#0f172a' : '#64748b'
                      }}
                    />
                  </ListItemButton>
                </ListItem>
              );
            })}
          </List>
        </div>

        <Box sx={{ p: 3, borderTop: '1px solid #f1f5f9' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 1.5, bgcolor: '#f8fafc', borderRadius: '12px' }}>
                <Avatar sx={{ width: 32, height: 32, bgcolor: '#6366f1', fontSize: '0.8rem', fontWeight: 800 }}>
                    {username.charAt(0).toUpperCase()}
                </Avatar>
                <Box>
                    <Typography sx={{ fontSize: '0.75rem', fontWeight: 800, color: '#1e293b' }}>{username}</Typography>
                    <Typography sx={{ fontSize: '0.65rem', color: '#94a3b8', fontWeight: 600 }}>Pro License</Typography>
                </Box>
            </Box>
        </Box>
      </Drawer>

      {/* Main Content Area */}
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', bgcolor: '#fcfcfc' }}>
        
        {/* Modern Header */}
        <Box component="header" sx={{ 
            height: 70, 
            flexShrink: 0, // Prevent header from shrinking
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            px: 4, 
            bgcolor: 'rgba(255, 255, 255, 0.8)',
            backdropFilter: 'blur(12px)',
            borderBottom: '1px solid #f1f5f9',
            zIndex: 10
        }}>
            {/* Left: Page Identity */}
            <Box sx={{ width: 240, flexShrink: 0 }}>
                <Typography noWrap sx={{ color: '#0f172a', fontWeight: 900, fontSize: '1.1rem', letterSpacing: '-0.02em', lineHeight: 1.5 }}>
                    {currentItem.text}
                </Typography>
                <Typography noWrap sx={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600, lineHeight: 1.5 }}>
                    {currentItem.subtitle}
                </Typography>
            </Box>

            {/* Right: Indices & System Tools */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {/* Real-time Indices with Fixed Width to prevent jitter */}
                <Box sx={{ display: 'flex', gap: 1 }}>
                    {indices.map((idx, i) => {
                        const isUp = idx.change_pct >= 0;
                        const color = isUp ? '#ef4444' : '#22c55e';
                        return (
                            <Box key={idx.code} sx={{ 
                                display: 'flex', 
                                alignItems: 'center',
                                gap: 1.5,
                                px: 2,
                                borderRight: i < indices.length - 1 ? '1px solid #f1f5f9' : 'none',
                                width: '140px' // Fixed width to prevent layout shift
                            }}>
                                <Box>
                                    <Typography sx={{ fontSize: '0.65rem', fontWeight: 800, color: '#94a3b8', whiteSpace: 'nowrap' }}>{idx.name}</Typography>
                                    <Typography sx={{ fontSize: '0.9rem', fontWeight: 900, fontFamily: 'JetBrains Mono', color: '#1e293b', lineHeight: 1.2 }}>
                                        {idx.price.toFixed(2)}
                                    </Typography>
                                </Box>
                                <Box sx={{ 
                                    display: 'flex', 
                                    flexDirection: 'column', 
                                    alignItems: 'flex-end',
                                    color: color,
                                    minWidth: '50px'
                                }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                        {isUp ? <ArrowDropUpIcon sx={{ fontSize: 18 }} /> : <ArrowDropDownIcon sx={{ fontSize: 18 }} />}
                                        <Typography sx={{ fontSize: '0.75rem', fontWeight: 900, fontFamily: 'JetBrains Mono' }}>
                                            {Math.abs(idx.change_pct).toFixed(2)}%
                                        </Typography>
                                    </Box>
                                    <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, fontFamily: 'JetBrains Mono', mt: -0.5 }}>
                                        {isUp ? '+' : ''}{idx.change_val.toFixed(2)}
                                    </Typography>
                                </Box>
                            </Box>
                        )
                    })}
                </Box>

                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Divider orientation="vertical" flexItem sx={{ height: 24, mx: 1, borderColor: '#f1f5f9' }} />
                    <Tooltip title={t('layout.tools.sync')}>
                        <IconButton size="small" sx={{ color: '#94a3b8', '&:hover': { color: '#6366f1', bgcolor: '#f8fafc' } }}>
                            <PublicIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>

                    {/* Documentation Link - Opens in new tab */}
                    <Tooltip title={t('layout.menu.documentation')}>
                        <IconButton
                            size="small"
                            onClick={() => window.open('/doc', '_blank')}
                            sx={{ color: '#94a3b8', '&:hover': { color: '#6366f1', bgcolor: '#f8fafc' } }}
                        >
                            <MenuBookIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>

                    {/* Language Switcher */}
                    <Tooltip title="Switch Language">
                        <IconButton 
                            size="small" 
                            onClick={handleClick}
                            sx={{ color: '#94a3b8', '&:hover': { color: '#6366f1', bgcolor: '#f8fafc' }, ml: 1 }}
                        >
                            <LanguageIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    {/* User Profile Menu (Replaces WifiTetheringIcon) */}
                    <Tooltip title="Account Settings">
                        <IconButton 
                            size="small" 
                            onClick={handleUserClick}
                            sx={{ 
                                color: '#94a3b8', 
                                '&:hover': { color: '#6366f1', bgcolor: '#f8fafc' },
                                border: '1px solid transparent',
                                '&.Mui-focusVisible': { borderColor: '#6366f1' }
                            }}
                        >
                            <Avatar sx={{ width: 24, height: 24, fontSize: '0.7rem', bgcolor: '#4f46e5' }}>
                                {username.charAt(0).toUpperCase()}
                            </Avatar>
                        </IconButton>
                    </Tooltip>
                    <Menu
                        anchorEl={userAnchorEl}
                        open={userOpen}
                        onClose={handleUserClose}
                        onClick={handleUserClose}
                        PaperProps={{
                            elevation: 0,
                            sx: {
                                overflow: 'visible',
                                filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.1))',
                                mt: 1.5,
                                '& .MuiAvatar-root': { width: 32, height: 32, ml: -0.5, mr: 1 },
                                '&:before': {
                                    content: '""',
                                    display: 'block',
                                    position: 'absolute',
                                    top: 0,
                                    right: 14,
                                    width: 10,
                                    height: 10,
                                    bgcolor: 'background.paper',
                                    transform: 'translateY(-50%) rotate(45deg)',
                                    zIndex: 0,
                                },
                            },
                        }}
                        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
                    >
                        <MenuItem>
                            <ListItemIcon><PersonIcon fontSize="small" /></ListItemIcon>
                            Profile
                        </MenuItem>
                        <Divider />
                        <MenuItem onClick={handleLogout} sx={{ color: '#ef4444' }}>
                            <ListItemIcon><LogoutIcon fontSize="small" sx={{ color: '#ef4444' }} /></ListItemIcon>
                            Logout
                        </MenuItem>
                    </Menu>
                    
                    
                    <Menu
                        anchorEl={anchorEl}
                        open={open}
                        onClose={() => handleClose()}
                        onClick={() => handleClose()}
                        PaperProps={{
                            elevation: 0,
                            sx: {
                                overflow: 'visible',
                                filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.1))',
                                mt: 1.5,
                                '& .MuiAvatar-root': { width: 32, height: 32, ml: -0.5, mr: 1 },
                                '&:before': {
                                    content: '""',
                                    display: 'block',
                                    position: 'absolute',
                                    top: 0,
                                    right: 14,
                                    width: 10,
                                    height: 10,
                                    bgcolor: 'background.paper',
                                    transform: 'translateY(-50%) rotate(45deg)',
                                    zIndex: 0,
                                },
                            },
                        }}
                        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
                    >
                        <MenuItem onClick={() => handleClose('en')} selected={i18n.resolvedLanguage === 'en'}>
                            English
                        </MenuItem>
                        <MenuItem onClick={() => handleClose('zh')} selected={i18n.resolvedLanguage === 'zh'}>
                            中文 (Chinese)
                        </MenuItem>
                    </Menu>

                </Box>
            </Box>
        </Box>

        {/* Content Section */}
        <Box component="main" sx={{ flexGrow: 1, overflow: 'auto', p: 4 }}>
          <Outlet />
        </Box>

        {/* Minimal Footer */}
        <Box component="footer" sx={{ 
            py: 2, 
            px: 4, 
            bgcolor: '#ffffff', 
            borderTop: '1px solid #f1f5f9',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
        }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography sx={{ color: '#94a3b8', fontSize: '0.7rem', fontWeight: 600 }}>
                    {t('layout.footer.copyright')}
                </Typography>
                <Typography sx={{ color: '#cbd5e1', fontSize: '0.7rem' }}>|</Typography>
                <Typography sx={{ color: '#94a3b8', fontSize: '0.7rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    {t('layout.footer.data_source')} <InfoOutlinedIcon sx={{ fontSize: 12 }} />
                </Typography>
            </Box>
        </Box>
      </Box>

      <style>{`
        @keyframes pulse {
          0% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.2); }
          100% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}