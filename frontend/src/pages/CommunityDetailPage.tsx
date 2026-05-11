import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { getCommunity, joinCommunity, approveCommunityMember, banCommunityMember, getFeed, getAssets, getCommunityMembers, getPositions } from '@/lib/api';
import type { CommunityItem, PostItem, AssetItem, CommunityMembershipItem, PositionItem } from '@/lib/types';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { loadAddress } from '@/lib/auth';
import { PostCard } from '@/components/feed/PostCard';
import { NewPostButton } from '@/components/feed/NewPostModal';
import ProfitabilityBadge from '@/components/ProfitabilityBadge';
import { PositionCard } from '@/components/PositionCard';
import { NewPositionModal } from '@/components/NewPositionModal';

export default function CommunityDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const myAddress = loadAddress();
  
  const [community, setCommunity] = useState<CommunityItem | null>(null);
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [positions, setPositions] = useState<PositionItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [members, setMembers] = useState<CommunityMembershipItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchCommunityAndPosts = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const comm = await getCommunity(Number(id));
      setCommunity(comm);
      
      const canViewPosts = comm.privacy_type === 'public' || comm.my_membership_status === 'approved' || comm.creator_address === myAddress;
      
      if (canViewPosts) {
        const [p, a, m, pos] = await Promise.all([
          getFeed({ community: Number(id) }),
          getAssets(),
          getCommunityMembers(Number(id)),
          getPositions(Number(id))
        ]);
        setPosts(p);
        setAssets(a);
        setMembers(m);
        setPositions(pos);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCommunityAndPosts();
    window.addEventListener('post-created', fetchCommunityAndPosts);
    window.addEventListener('hard-claim-created', fetchCommunityAndPosts);
    return () => {
      window.removeEventListener('post-created', fetchCommunityAndPosts);
      window.removeEventListener('hard-claim-created', fetchCommunityAndPosts);
    };
  }, [id]);

  const handleJoin = async () => {
    if (!id) return;
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

  if (error) return <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>;
  if (loading && !community) return <p className="text-center py-10">Loading...</p>;
  if (!community) return <p className="text-center py-10">Community not found.</p>;

  const isCreator = myAddress && myAddress.toLowerCase() === community.creator_address.toLowerCase();
  const canViewPosts = community.privacy_type === 'public' || community.my_membership_status === 'approved' || isCreator;
  const canPost = isCreator || (community.my_membership_status === 'approved' && community.post_permission === 'all');

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/app/communities')}>
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
          </TabsList>
          
          <TabsContent value="posts" className="space-y-4 mt-4">
            {posts.length === 0 ? (
              <p className="text-muted-foreground text-sm">No posts in this community yet.</p>
            ) : (
              posts.map(post => (
                <PostCard key={post.id} post={post} hardClaims={post.hard_claims} assets={assets} />
              ))
            )}
          </TabsContent>
          
          <TabsContent value="positions" className="space-y-4 mt-4">
            {positions.length === 0 ? (
              <p className="text-muted-foreground text-sm">No positions active in this community.</p>
            ) : (
              positions.map(position => (
                <PositionCard key={position.id} position={position} assets={assets} onClosed={fetchCommunityAndPosts} />
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
        </Tabs>
      ) : (
        <Alert>
          <AlertDescription>
            This is a private community. You must be an approved member to view posts and members.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
