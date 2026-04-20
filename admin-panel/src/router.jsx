import { Navigate, createBrowserRouter } from 'react-router-dom';
import PageLayout from './components/layout/PageLayout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import DocumentsList from './pages/Documents/DocumentsList';
import DocumentDetail from './pages/Documents/DocumentDetail';
import UsersList from './pages/Users/UsersList';
import UserDetail from './pages/Users/UserDetail';
import Tasks from './pages/Tasks';
import SystemStatus from './pages/SystemStatus';

function ProtectedRoute({ children }) {
  return children;
}

export const appRouter = createBrowserRouter([
  {
    path: '/login',
    element: <Login />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <PageLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <Dashboard /> },
      { path: 'documents', element: <DocumentsList /> },
      { path: 'documents/:docId', element: <DocumentDetail /> },
      { path: 'users', element: <UsersList /> },
      { path: 'users/:userId', element: <UserDetail /> },
      { path: 'tasks', element: <Tasks /> },
      { path: 'system-status', element: <SystemStatus /> },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/dashboard" replace />,
  },
]);
