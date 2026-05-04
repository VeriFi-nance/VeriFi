import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import LoginPage from './pages/LoginPage';
import AppLayout from './pages/AppLayout';
import FeedPage from './pages/FeedPage';
import PostCreationPage from './pages/PostCreationPage';
import ClaimReviewPage from './pages/ClaimReviewPage';
import PostDetailPage from './pages/PostDetailPage';
import UserPostsPage from './pages/UserPostsPage';
import ProfilePage from './pages/ProfilePage';
import { isAuthenticated } from './lib/auth';

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
          <Route path="post/review" element={<ClaimReviewPage />} />
          <Route path="post/:id" element={<PostDetailPage />} />
          <Route path="user/:address" element={<UserPostsPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
