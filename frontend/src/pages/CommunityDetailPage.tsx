import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { getCommunity, joinCommunity, approveCommunityMember, banCommunityMember, getAssets, getCommunityMembers, getPositions, updateCommunity } from '@/lib/api';
import type { CommunityItem, AssetItem, CommunityMembershipItem, PositionItem } from '@/lib/types';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuthState, useOpenLogin } from '@/lib/auth';
import { FeedList } from '@/components/feed/FeedList';
import { NewPostButton } from '@/components/feed/NewPostModal';
import ProfitabilityBadge from '@/components/ProfitabilityBadge';
import { PositionCard } from '@/components/PositionCard';
import { NewPositionModal } from '@/components/NewPositionModal';
import { Settings } from 'lucide-react';
import { PageContent } from '@/components/PageContent';

export default function CommunityDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const openLogin = useOpenLogin();
  const auth = useAuthState();
  const myAddress = auth.address;
  
  const [community, setCommunity] = useState<CommunityItem | null>(null);
  const [positions, setPositions] = useState<PositionItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [members, setMembers] = useState<CommunityMembershipItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [settingsSaved, setSettingsSaved] = useState('');

  const fetchCommunityAndPosts = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const comm = await getCommunity(Number(id));
      setCommunity(comm);
      
      const canView = comm.privacy_type === 'public' || comm.my_membership_status === 'approved' || comm.creator_address === myAddress;
      
      if (canView) {
        const [a, m, pos] = await Promise.all([
          getAssets(),
          getCommunityMembers(Number(id)),
          getPositions(Number(id)),
        ]);
        setAssets(a);
        setMembers(m);
        setPositions(pos);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [id, myAddress]);

  useEffect(() => {
    fetchCommunityAndPosts();
  }, [fetchCommunityAndPosts]);

  useEffect(() => {
    const handler = () => fetchCommunityAndPosts();
    window.addEventListener('post-created', handler);
    window.addEventListener('hard-claim-created', handler);
    return () => {
      window.removeEventListener('post-created', handler);
      window.removeEventListener('hard-claim-created', handler);
    };
  }, [fetchCommunityAndPosts]);

  const handleJoin = async () => {
    if (!id) return;
    if (!auth.authenticated) {
      openLogin(`/c/${id}`);
      return;
    }
    try {
      await joinCommunity(Number(id));
      await fetchCommunityAndPosts();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleApprove = async (userAddress: string, action: 'approve' | 'reject') => {
    if (!id) return;
    try {
      await approveCommunityMember(Number(id), userAddress, action);
      await fetchCommunityAndPosts();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleBan = async (userAddress: string) => {
    if (!id || !confirm(`Are you sure you want to ban ${userAddress}?`)) return;
    try {
      await banCommunityMember(Number(id), userAddress);
      await fetchCommunityAndPosts();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handlePositionResolved = (updated: PositionItem) => {
    setPositions(prev => prev.map(p => p.id === updated.id ? updated : p));
  };

  const handlePostPermissionChange = async (value: 'all' | 'creator_only') => {
    if (!id || !community) return;
    // Optimistic update
    setCommunity(prev => prev ? { ...prev, post_permission: value } : prev);
    try {
      const updated = await updateCommunity(Number(id), { post_permission: value });
      setCommunity(updated);
      setSettingsSaved('Settings saved.');
      setTimeout(() => setSettingsSaved(''), 3000);
    } catch (e: any) {
      setSettingsSaved(`Error: ${e.message}`);
      // Revert
      await fetchCommunityAndPosts();
    }
  };

  if (error) return <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>;
  if (loading && !community) return <p className="text-center py-10">Loading...</p>;
  if (!community) return <p className="text-center py-10">Community not found.</p>;

  const isCreator = myAddress && myAddress.toLowerCase() === community.creator_address.toLowerCase();
  const canViewPosts = community.privacy_type === 'public' || community.my_membership_status === 'approved' || isCreator;
  const canPost = isCreator || (community.my_membership_status === 'approved' && community.post_permission === 'all');

  return (
    <PageContent className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/c')}>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold flex items-center gap-3">
            {community.name}
            <span className="text-xs font-normal px-2 py-1 bg-secondary rounded-full uppercase tracking-wider">{community.privacy_type}</span>
            {community.post_permission === 'creator_only' && (
              <span className="text-xs font-normal px-2 py-1 bg-primary/10 text-primary rounded-full uppercase tracking-wider">Broadcast Only</span>
            )}
          </h1>
          <p className="text-sm text-muted-foreground">{community.description}</p>
        </div>
        {!isCreator && !community.my_membership_status && (
          <Button onClick={handleJoin}>Join</Button>
        )}
        {!isCreator && community.my_membership_status === 'pending' && (
          <Button variant="secondary" disabled>Request Pending</Button>
        )}
        {canPost && (
          <div className="shrink-0 flex items-center gap-2">
            <NewPositionModal communityId={Number(id)} assets={assets} onCreated={fetchCommunityAndPosts} />
            <NewPostButton onPosted={fetchCommunityAndPosts} communityId={Number(id)} />
          </div>
        )}
      </div>

      <div className="text-sm text-muted-foreground">
        <strong>{community.member_count}</strong> member{community.member_count !== 1 ? 's' : ''} &middot; Created by {community.creator_address.slice(0,6)}...{community.creator_address.slice(-4)}
      </div>

      {isCreator && community.pending_requests && community.pending_requests.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pending Join Requests</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {community.pending_requests.map(req => (
              <div key={req.id} className="flex items-center justify-between">
                <code className="text-xs">{req.user_address}</code>
                <div className="flex gap-2">
                  <Button size="sm" variant="destructive" onClick={() => handleBan(req.user_address)}>Ban</Button>
                  <Button size="sm" variant="outline" onClick={() => handleApprove(req.user_address, 'reject')}>Reject</Button>
                  <Button size="sm" onClick={() => handleApprove(req.user_address, 'approve')}>Approve</Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {canViewPosts ? (
        <Tabs defaultValue="posts" className="mt-6">
          <TabsList>
            <TabsTrigger value="posts">Posts</TabsTrigger>
            <TabsTrigger value="positions">Positions</TabsTrigger>
            <TabsTrigger value="members">Members</TabsTrigger>
            {isCreator && <TabsTrigger value="settings" className="gap-1.5"><Settings className="size-3.5" />Settings</TabsTrigger>}
          </TabsList>
          
          <TabsContent value="posts" className="space-y-4 mt-4">
            <FeedList community={Number(id)} />
          </TabsContent>
          
          <TabsContent value="positions" className="space-y-4 mt-4">
            {positions.length === 0 ? (
              <p className="text-muted-foreground text-sm">No positions active in this community.</p>
            ) : (
              positions.map(position => (
                <PositionCard
                  key={position.id}
                  position={position}
                  assets={assets}
                  onClosed={fetchCommunityAndPosts}
                  onResolved={handlePositionResolved}
                />
              ))
            )}
          </TabsContent>
          
          <TabsContent value="members" className="space-y-4 mt-4">
            {members.length === 0 ? (
              <p className="text-muted-foreground text-sm">No approved members yet.</p>
            ) : (
              <div className="grid gap-2">
                {members.map(member => (
                  <Card key={member.id}>
                    <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div>
                        <div className="font-mono font-bold text-sm flex items-center gap-2">
                          {member.user_address}
                          <ProfitabilityBadge data={member.profitability} />
                        </div>
                        <div className="text-xs text-muted-foreground">Joined: {new Date(member.created_at).toLocaleDateString()}</div>
                      </div>
                      {isCreator && member.user_address.toLowerCase() !== community.creator_address.toLowerCase() && (
                        <Button size="sm" variant="destructive" onClick={() => handleBan(member.user_address)}>Ban</Button>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          {isCreator && (
            <TabsContent value="settings" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Settings className="size-4" />
                    Community Settings
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Who can post?</label>
                    <Select
                      value={community.post_permission}
                      onValueChange={(v: any) => handlePostPermissionChange(v)}
                    >
                      <SelectTrigger className="w-56">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">Everyone (approved members)</SelectItem>
                        <SelectItem value="creator_only">Creator Only (Broadcast)</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      When set to "Creator Only", only you can create posts and positions in this community.
                    </p>
                    {settingsSaved && (
                      <p className={`text-xs font-medium ${settingsSaved.startsWith('Error') ? 'text-destructive' : 'text-success'}`}>
                        {settingsSaved}
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          )}
        </Tabs>
      ) : (
        <Alert>
          <AlertDescription>
            This is a private community. You must be an approved member to view posts and members.
          </AlertDescription>
        </Alert>
      )}
    </PageContent>
  );
}
