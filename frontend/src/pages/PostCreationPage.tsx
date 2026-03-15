import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { createPost } from '@/lib/api';

const MAX_CHARS = 500;
const WARN_THRESHOLD = 450;

export default function PostCreationPage() {
  const navigate = useNavigate();
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit() {
    if (!content.trim()) return;
    setError('');
    setSubmitting(true);
    try {
      await createPost(content, []);
      navigate('/app', { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create post');
      setSubmitting(false);
    }
  }

  const remaining = MAX_CHARS - content.length;
  const overLimit = content.length > MAX_CHARS;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/app')}>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
        </Button>
        <h1 className="text-xl font-semibold">New Post</h1>
      </div>

      <Textarea
        placeholder="What's your financial take?"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={5}
        className="resize-none"
        maxLength={MAX_CHARS}
      />
      <p
        className={`text-xs text-right tabular-nums ${
          overLimit
            ? 'text-destructive font-medium'
            : remaining <= MAX_CHARS - WARN_THRESHOLD
            ? 'text-amber-500'
            : 'text-muted-foreground'
        }`}
      >
        {remaining} / {MAX_CHARS}
      </p>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Button
        className="w-full"
        disabled={!content.trim() || overLimit || submitting}
        onClick={handleSubmit}
      >
        {submitting ? 'Posting…' : 'Post'}
      </Button>
    </div>
  );
}
