import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import LoginPage from './pages/LoginPage';
import AppLayout from './pages/AppLayout';
import FeedPage from './pages/FeedPage';
import PostCreationPage from './pages/PostCreationPage';
import PostDetailPage from './pages/PostDetailPage';
import UserPostsPage from './pages/UserPostsPage';
import ProfilePage from './pages/ProfilePage';
import { isAuthenticated } from './lib/auth';

import CommunitiesPage from './pages/CommunitiesPage';
import CommunityDetailPage from './pages/CommunityDetailPage';

function ProtectedRoute({ children }: { children: ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/app"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<FeedPage />} />
          <Route path="post/new" element={<PostCreationPage />} />
          <Route path="post/:id" element={<PostDetailPage />} />
          <Route path="user/:address" element={<UserPostsPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="communities" element={<CommunitiesPage />} />
          <Route path="communities/:id" element={<CommunityDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
