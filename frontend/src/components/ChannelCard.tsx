import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Lock, Unlock } from 'lucide-react';
import type { ChannelItem } from '@/lib/types';

interface ChannelCardProps {
  channel: ChannelItem;
  onClick: () => void;
  isOwned?: boolean;
}

export function ChannelCard({ channel, onClick, isOwned }: ChannelCardProps) {
  return (
    <Card
      className="group cursor-pointer border border-border/50 bg-card hover:bg-muted/40 hover:border-border transition-all duration-300 rounded-xl"
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between gap-2 text-sm md:text-base">
          <div className="flex items-center gap-2 truncate">
            <span className="truncate group-hover:text-primary transition-colors">{channel.name}</span>
          </div>
          <span className="text-[10px] font-normal px-2 py-0.5 bg-secondary text-secondary-foreground rounded-md uppercase tracking-wider flex items-center gap-1 shrink-0">
            {channel.privacy_type === 'private' ? <Lock className="size-2.5" /> : <Unlock className="size-2.5" />}
            {channel.privacy_type}
          </span>
        </CardTitle>
        <CardDescription className="line-clamp-2 text-xs h-8">
          {channel.description || 'No description'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-between border-t border-border/30 pt-3 text-xs text-muted-foreground">
        <div>
          <strong className="text-foreground num">{channel.member_count}</strong> subscriber{channel.member_count !== 1 ? 's' : ''}
        </div>
        {isOwned ? (
          <span className="text-[9px] font-medium uppercase tracking-wider text-primary/80">
            Owner
          </span>
        ) : channel.my_role ? (
          <span className="text-[9px] font-medium uppercase tracking-wider text-primary/80">
            {channel.my_role}
          </span>
        ) : channel.my_membership_status === 'pending' ? (
          <span className="text-[9px] font-medium uppercase tracking-wider text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded">
            Request Pending
          </span>
        ) : null}
      </CardContent>
    </Card>
  );
}
