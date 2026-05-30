import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Users, Plus } from 'lucide-react';
import { EmptyState } from '@/components/EmptyState';
import { Skeleton } from '@/components/Skeleton';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { getCommunities, createCommunity } from '@/lib/api';
import { loginPathWithReturn, useAuthState } from '@/lib/auth';
import type { CommunityItem } from '@/lib/types';

export default function CommunitiesPage() {
  const navigate = useNavigate();
  const { authenticated } = useAuthState();
  const [communities, setCommunities] = useState<CommunityItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [privacy, setPrivacy] = useState<'public' | 'private'>('public');
  const [postPermission, setPostPermission] = useState<'all' | 'creator_only'>('all');
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    getCommunities()
      .then(setCommunities)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate() {
    try {
      const comm = await createCommunity(name, description, privacy, postPermission);
      setOpen(false);
      setName('');
      setDescription('');
      navigate(`/c/${comm.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create');
    }
  }

  function newCommunity() {
    if (!authenticated) {
      navigate(loginPathWithReturn('/c'));
      return;
    }
    setOpen(true);
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <div className="flex items-center justify-end">
        <Button size="sm" className="gap-1.5" onClick={newCommunity}>
          <Plus className="size-4" />
          New
        </Button>
      </div>

      <RD.Root open={open} onOpenChange={setOpen}>
        <RD.Content>
          <RD.Header>
            <RD.Title>New community</RD.Title>
            <RD.Description>Set basics. You can change them later.</RD.Description>
          </RD.Header>
          <div className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-1.5">
              <Label>Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Crypto Traders"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Description</Label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What's this community about?"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Privacy</Label>
                <Select
                  value={privacy}
                  onValueChange={(v: 'public' | 'private') => setPrivacy(v)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="public">Public</SelectItem>
                    <SelectItem value="private">Private</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Who can post?</Label>
                <Select
                  value={postPermission}
                  onValueChange={(v: 'all' | 'creator_only') => setPostPermission(v)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Members</SelectItem>
                    <SelectItem value="creator_only">Creator only</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Button className="w-full" onClick={handleCreate} disabled={!name.trim()}>
              Create
            </Button>
          </div>
        </RD.Content>
      </RD.Root>

      {loading ? (
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      ) : communities.length === 0 ? (
        <EmptyState
          icon={<Users className="size-5" />}
          title="No communities yet"
          description="Create the first one and invite people."
        />
      ) : (
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {communities.map((c) => (
            <Card
              key={c.id}
              className="cursor-pointer hover:bg-accent/40 transition-colors"
              onClick={() => navigate(`/c/${c.id}`)}
            >
              <CardHeader>
                <CardTitle className="flex items-center justify-between gap-2 text-base">
                  <span className="truncate">{c.name}</span>
                  <span className="text-[10px] font-normal px-2 py-0.5 bg-muted text-muted-foreground rounded-full uppercase tracking-wider shrink-0">
                    {c.privacy_type}
                  </span>
                </CardTitle>
                <CardDescription className="line-clamp-2 text-xs">
                  {c.description || 'No description'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-xs text-muted-foreground">
                  <strong className="text-foreground num">{c.member_count}</strong>{' '}
                  member{c.member_count !== 1 ? 's' : ''}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
