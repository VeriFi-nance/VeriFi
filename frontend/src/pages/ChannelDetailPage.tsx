import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { getChannel, joinChannel, approveChannelMember, banChannelMember, unbanChannelMember, getBannedChannelMembers, getChannelMembers, updateChannel, promoteModerator, demoteModerator } from '@/lib/api';
import type { ChannelItem, ChannelMembershipItem } from '@/lib/types';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuthState, useOpenLogin } from '@/lib/auth';
import { FeedList } from '@/components/feed/FeedList';
import { NewPostButton } from '@/components/feed/NewPostModal';
import { Settings, ArrowLeft, Lock, Users } from 'lucide-react';
import { PageContent } from '@/components/PageContent';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { toast, getMessage } from '@/lib/errors';
import { SmartTimestamp } from '@/components/SmartTimestamp';

export default function ChannelDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const openLogin = useOpenLogin();
  const auth = useAuthState();
  const myAddress = auth.address;
  
  const [channel, setChannel] = useState<ChannelItem | null>(null);
  const [members, setMembers] = useState<ChannelMembershipItem[]>([]);
  const [bannedMembers, setBannedMembers] = useState<ChannelMembershipItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [settingsSaved, setSettingsSaved] = useState('');
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    title: string;
    description: string;
    onConfirm: () => void | Promise<void>;
  }>({
    open: false,
    title: '',
    description: '',
    onConfirm: () => {},
  });

  const fetchChannelAndPosts = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const chan = await getChannel(Number(id));
      setChannel(chan);
      const canView = chan.my_membership_status === 'approved' || chan.creator_address === myAddress;
      
      if (canView) {
        const m = await getChannelMembers(Number(id));
        setMembers(m);
        
        if (chan.creator_address.toLowerCase() === myAddress?.toLowerCase()) {
          try {
            const banned = await getBannedChannelMembers(Number(id));
            setBannedMembers(banned);
          } catch (e) {
            console.error("Failed to load banned members", e);
          }
        }
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [id, myAddress]);

  useEffect(() => {
    fetchChannelAndPosts();
  }, [fetchChannelAndPosts]);

  useEffect(() => {
    const handler = () => fetchChannelAndPosts();
    window.addEventListener('post-created', handler);
    window.addEventListener('hard-claim-created', handler);
    return () => {
      window.removeEventListener('post-created', handler);
      window.removeEventListener('hard-claim-created', handler);
    };
  }, [fetchChannelAndPosts]);

  const handleJoin = async () => {
    if (!id) return;
    if (!auth.authenticated) {
      openLogin(`/channels/${id}`);
      return;
    }
    try {
      await joinChannel(Number(id));
      await fetchChannelAndPosts();
    } catch (e: unknown) {
      toast.error(getMessage(e));
    }
  };

  const handleApprove = async (userAddress: string, action: 'approve' | 'reject') => {
    if (!id) return;
    try {
      await approveChannelMember(Number(id), userAddress, action);
      await fetchChannelAndPosts();
    } catch (e: unknown) {
      toast.error(getMessage(e));
    }
  };

  const handleBan = (userAddress: string) => {
    if (!id) return;
    setConfirmDialog({
      open: true,
      title: 'Ban Member',
      description: `Are you sure you want to ban ${userAddress}?`,
      onConfirm: async () => {
        try {
          await banChannelMember(Number(id), userAddress);
          await fetchChannelAndPosts();
        } catch (e: unknown) {
          toast.error(getMessage(e));
        }
      }
    });
  };

  const handleUnban = (userAddress: string) => {
    if (!id) return;
    setConfirmDialog({
      open: true,
      title: 'Unban Member',
      description: `Are you sure you want to unban ${userAddress}?`,
      onConfirm: async () => {
        try {
          await unbanChannelMember(Number(id), userAddress);
          await fetchChannelAndPosts();
        } catch (e: unknown) {
          toast.error(getMessage(e));
        }
      }
    });
  };

  const handlePromote = async (userAddress: string) => {
    if (!id) return;
    try {
      await promoteModerator(Number(id), userAddress);
      await fetchChannelAndPosts();
    } catch (e: unknown) {
      toast.error(getMessage(e));
    }
  };

  const handleDemote = async (userAddress: string) => {
    if (!id) return;
    try {
      await demoteModerator(Number(id), userAddress);
      await fetchChannelAndPosts();
    } catch (e: unknown) {
      toast.error(getMessage(e));
    }
  };

  const handlePostPermissionChange = async (value: 'all' | 'creator_only') => {
    if (!id || !channel) return;
    // Optimistic update
    setChannel(prev => prev ? { ...prev, post_permission: value } : prev);
    try {
      const updated = await updateChannel(Number(id), { post_permission: value });
      setChannel(updated);
      setSettingsSaved('Settings saved.');
      setTimeout(() => setSettingsSaved(''), 3000);
    } catch (e: any) {
      setSettingsSaved(`Error: ${e.message}`);
      // Revert
      await fetchChannelAndPosts();
    }
  };

  if (error) return <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>;
  if (loading && !channel) return <p className="text-center py-10">Loading...</p>;
  if (!channel) return <p className="text-center py-10">Channel not found.</p>;

  const isCreator = myAddress && myAddress.toLowerCase() === channel.creator_address.toLowerCase();
  const isOwner = isCreator;
  const isModerator = channel.my_role === 'moderator';
  const canModerate = isOwner || isModerator;
  const canViewPosts = channel.my_membership_status === 'approved' || isCreator;
  const canPost = isCreator || (channel.my_membership_status === 'approved' && channel.post_permission === 'all');

  return (
    <PageContent className="space-y-6 max-w-5xl mx-auto pb-12">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/channels')} className="rounded-full shrink-0">
          <ArrowLeft className="size-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl md:text-2xl font-bold flex flex-wrap items-center gap-2">
            <span className="truncate">{channel.name}</span>
            <span className="text-[10px] font-normal px-2 py-0.5 bg-amber-500/10 text-amber-500 rounded-full uppercase tracking-wider shrink-0">
              Premium
            </span>
            {channel.post_permission === 'creator_only' && (
              <span className="text-[10px] font-normal px-2 py-0.5 bg-primary/10 text-primary rounded-full uppercase tracking-wider shrink-0">
                Broadcast Only
              </span>
            )}
          </h1>
          <p className="text-xs md:text-sm text-muted-foreground mt-0.5 line-clamp-2">{channel.description}</p>
        </div>
        {!isCreator && !channel.my_membership_status && (
          <Button size="sm" onClick={handleJoin} className="shrink-0">Subscribe</Button>
        )}
        {!isCreator && channel.my_membership_status === 'pending' && (
          <Button size="sm" variant="secondary" disabled className="shrink-0">Request Pending</Button>
        )}
        {canPost && (
          <div className="shrink-0">
            <NewPostButton
              onPosted={fetchChannelAndPosts}
              channelId={Number(id)}
            />
          </div>
        )}
      </div>

      <div className="text-xs text-muted-foreground flex items-center gap-2 border-b border-border/40 pb-4">
        <Users className="size-3.5" />
        <span>
          <strong className="text-foreground num">{channel.member_count}</strong> subscriber{channel.member_count !== 1 ? 's' : ''}
        </span>
        <span>&middot;</span>
        <span>
          Created by {channel.creator_username ? `@${channel.creator_username}` : `${channel.creator_address.slice(0,6)}...${channel.creator_address.slice(-4)}`}
        </span>
      </div>

      {canModerate && channel.pending_requests && channel.pending_requests.length > 0 && (
        <Card className="border-amber-500/20 bg-amber-500/5">
          <CardHeader className="py-4">
            <CardTitle className="text-sm font-semibold text-amber-600 dark:text-amber-400">Pending Subscription Requests</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pb-4">
            {channel.pending_requests.map(req => (
              <div key={req.id} className="flex items-center justify-between gap-4">
                <code className="text-xs font-mono">{req.user_username ? `@${req.user_username}` : req.user_address}</code>
                <div className="flex gap-2 shrink-0">
                  <Button size="xs" variant="destructive" onClick={() => handleBan(req.user_address)}>Ban</Button>
                  <Button size="xs" variant="outline" onClick={() => handleApprove(req.user_address, 'reject')}>Reject</Button>
                  <Button size="xs" onClick={() => handleApprove(req.user_address, 'approve')}>Approve</Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {canViewPosts ? (
        <Tabs defaultValue="posts" className="w-full">
          <TabsList className="flex w-full sm:w-auto overflow-x-auto justify-start">
            <TabsTrigger value="posts" className="text-sm">Posts</TabsTrigger>
            <TabsTrigger value="members" className="text-sm">Members</TabsTrigger>
            {isCreator && <TabsTrigger value="settings" className="text-sm gap-1.5"><Settings className="size-3.5" />Settings</TabsTrigger>}
          </TabsList>
          
          <TabsContent value="posts" className="space-y-4 mt-4">
            <FeedList channel={Number(id)} myRole={channel.my_role} creatorAddress={channel.creator_address} />
          </TabsContent>
          
          <TabsContent value="members" className="space-y-4 mt-4">
            {members.length === 0 ? (
              <p className="text-muted-foreground text-xs py-6 text-center">No subscribers yet.</p>
            ) : (
              <div className="grid gap-3">
                {members.map(member => (
                  <Card key={member.id} className="bg-card/40">
                    <CardContent className="p-4 flex items-center justify-between gap-4">
                      <div>
                        <div className="font-mono font-semibold text-xs sm:text-sm flex flex-wrap items-center gap-1.5">
                          <span>{member.user_username ? `@${member.user_username}` : member.user_address}</span>
                          {member.role === 'owner' && (
                            <span className="text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500">
                              Owner
                            </span>
                          )}
                          {member.role === 'moderator' && (
                            <span className="text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-500">
                              Mod
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-1">
                          Subscribed: <SmartTimestamp value={member.created_at} />
                        </div>
                      </div>
                      <div className="flex gap-1.5">
                        {canModerate && member.role === 'member' && member.user_address.toLowerCase() !== channel.creator_address.toLowerCase() && (
                          <Button size="xs" variant="destructive" onClick={() => handleBan(member.user_address)}>Ban</Button>
                        )}
                        {isOwner && member.role === 'member' && member.user_address.toLowerCase() !== channel.creator_address.toLowerCase() && (
                          <Button size="xs" variant="outline" onClick={() => handlePromote(member.user_address)}>Make Mod</Button>
                        )}
                        {isOwner && member.role === 'moderator' && (
                          <>
                            <Button size="xs" variant="destructive" onClick={() => handleBan(member.user_address)}>Ban</Button>
                            <Button size="xs" variant="ghost" onClick={() => handleDemote(member.user_address)}>Demote</Button>
                          </>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          {isCreator && (
            <TabsContent value="settings" className="mt-4">
              <Card className="bg-card/45">
                <CardHeader>
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <Settings className="size-4" />
                    Channel Settings
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="space-y-2">
                    <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">Who can post?</label>
                    <Select
                      value={channel.post_permission}
                      onValueChange={(v: any) => handlePostPermissionChange(v)}
                    >
                      <SelectTrigger className="w-full sm:w-64 bg-muted/30">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">Everyone (approved subscribers)</SelectItem>
                        <SelectItem value="creator_only">Creator Only (Broadcast)</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-[10px] text-muted-foreground mt-1">
                      When set to "Creator Only", only you can create posts and predictions in this channel.
                    </p>
                    {settingsSaved && (
                      <p className={`text-xs font-medium mt-1.5 ${settingsSaved.startsWith('Error') ? 'text-destructive' : 'text-emerald-500'}`}>
                        {settingsSaved}
                      </p>
                    )}
                  </div>

                  <div className="pt-4 border-t border-border/40 space-y-4">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Banned Users</h3>
                    {bannedMembers.length === 0 ? (
                      <p className="text-xs text-muted-foreground">No banned users.</p>
                    ) : (
                      <div className="space-y-2 max-w-lg">
                        {bannedMembers.map(member => (
                          <div key={member.id} className="flex items-center justify-between bg-muted/30 p-2.5 rounded-lg border border-border/30 gap-4">
                            <code className="text-xs truncate font-mono">{member.user_address}</code>
                            <Button size="xs" variant="outline" onClick={() => handleUnban(member.user_address)} className="shrink-0">Unban</Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          )}
        </Tabs>
      ) : (
        <Card className="border border-border/40 bg-muted/15 p-6 rounded-2xl text-center space-y-3">
          <div className="p-3 bg-secondary/50 rounded-full text-muted-foreground w-12 h-12 flex items-center justify-center mx-auto">
            <Lock className="size-5" />
          </div>
          <div className="space-y-1">
            <h3 className="font-semibold text-sm">Private Channel</h3>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              This is a private channel. You must be an approved subscriber to view posts and positions.
            </p>
          </div>
          <Button size="sm" onClick={handleJoin}>
            Subscribe
          </Button>
        </Card>
      )}

      <RD.Root open={confirmDialog.open} onOpenChange={(val) => setConfirmDialog(prev => ({ ...prev, open: val }))}>
        <RD.Content>
          <RD.Header>
            <RD.Title>{confirmDialog.title}</RD.Title>
            <RD.Description>{confirmDialog.description}</RD.Description>
          </RD.Header>
          <RD.Footer className="mt-4 flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setConfirmDialog(prev => ({ ...prev, open: false }))}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={async () => {
                await confirmDialog.onConfirm();
                setConfirmDialog(prev => ({ ...prev, open: false }));
              }}
            >
              Confirm
            </Button>
          </RD.Footer>
        </RD.Content>
      </RD.Root>
    </PageContent>
  );
}
