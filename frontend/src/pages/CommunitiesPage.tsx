import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getCommunities, createCommunity } from '@/lib/api';
import type { CommunityItem } from '@/lib/types';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { loginPathWithReturn, useAuthState } from '@/lib/auth';

export default function CommunitiesPage() {
  const navigate = useNavigate();
  const auth = useAuthState();
  const [communities, setCommunities] = useState<CommunityItem[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Create state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [privacy, setPrivacy] = useState<'public' | 'private'>('public');
  const [postPermission, setPostPermission] = useState<'all' | 'creator_only'>('all');
  const [open, setOpen] = useState(false);

  const fetchCommunities = () => {
    setLoading(true);
    getCommunities().then(setCommunities).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchCommunities();
  }, []);

  const handleCreate = async () => {
    if (!auth.authenticated) {
      navigate(loginPathWithReturn('/app/communities'), { replace: true });
      return;
    }
    try {
      const comm = await createCommunity(name, description, privacy, postPermission);
      setOpen(false);
      setName('');
      setDescription('');
      navigate(`/app/communities/${comm.id}`);
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Communities</h1>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>Create Community</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create a Community</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Crypto Traders" />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What is this community about?" />
              </div>
              <div className="space-y-2">
                <Label>Privacy</Label>
                <Select value={privacy} onValueChange={(v: 'public' | 'private') => setPrivacy(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="public">Public (Anyone can join)</SelectItem>
                    <SelectItem value="private">Private (Requires approval)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Who can post?</Label>
                <Select value={postPermission} onValueChange={(v: 'all' | 'creator_only') => setPostPermission(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Members (Discussion)</SelectItem>
                    <SelectItem value="creator_only">Creator Only (Broadcast)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button className="w-full" onClick={handleCreate} disabled={!name.trim()}>Create</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {loading ? (
        <p className="text-muted-foreground text-center py-10">Loading...</p>
      ) : communities.length === 0 ? (
        <p className="text-muted-foreground text-center py-10">No communities yet.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {communities.map(c => (
            <Card key={c.id} className="cursor-pointer hover:bg-accent/50 transition-colors" onClick={() => navigate(`/app/communities/${c.id}`)}>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>{c.name}</span>
                  <span className="text-xs font-normal px-2 py-1 bg-secondary rounded-full uppercase tracking-wider">{c.privacy_type}</span>
                </CardTitle>
                <CardDescription className="line-clamp-2">{c.description || 'No description'}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-muted-foreground">
                  <strong>{c.member_count}</strong> member{c.member_count !== 1 ? 's' : ''}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
