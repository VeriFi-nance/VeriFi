import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { getAssetChartData } from '@/lib/api';
import type { AssetChartData, ChartCandleInterval } from '@/lib/types';
import type { ClaimDraft } from './types';
import { InteractiveChart } from './InteractiveChart';
import { FieldError } from '@/components/ui/field-error';
import { cn } from '@/lib/utils';

interface StepTargetProps {
  value: ClaimDraft;
  onChange: (patch: Partial<ClaimDraft>) => void;
  onNext: () => void;
  onBack: () => void;
}

export function StepTarget({ value, onChange, onNext, onBack }: StepTargetProps) {
  const [chartData, setChartData] = useState<AssetChartData | null>(null);
  const [interval, setInterval] = useState<ChartCandleInterval>('4h');
  const [loading, setLoading] = useState(false);
  const [minDate, setMinDate] = useState('');

  const isPrice = value.claim_type === 'PRICE';

  useEffect(() => {
    setMinDate(new Date(Date.now() + 86400000).toISOString().split('T')[0]);
  }, []);

  useEffect(() => {
    if (!value.asset_id) return;
    let active = true;
    setLoading(true);

    getAssetChartData(Number(value.asset_id), interval)
      .then((data) => {
        if (!active) return;
        setChartData(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load asset chart data', err);
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [value.asset_id, interval]);

  // Per-field validation (shown only once the field has a value, so the user
  // isn't scolded before typing). Mirrors backend rules in validateDraft.
  const pct = parseFloat(value.percentage);
  const targetError = !value.percentage
    ? ''
    : isNaN(pct)
      ? 'Enter a number.'
      : isPrice
        ? (pct <= 0 ? 'Target price must be greater than 0.' : '')
        : (pct < 0.1 || pct > 1000 ? 'Target move must be between 0.1% and 1000%.' : '');

  const todayStr = new Date().toISOString().split('T')[0];
  const deadlineError = !value.until
    ? ''
    : value.until <= todayStr
      ? 'Deadline must be tomorrow or later.'
      : '';

  const canProceed = Boolean(value.percentage && value.until) && !targetError && !deadlineError;

  function handleSelectTarget(price: number, dateStr: string) {
    const update: Partial<ClaimDraft> = { until: dateStr };
    
    if (isPrice) {
      update.percentage = price.toFixed(2); // For PRICE claims, percentage field holds the absolute price
      // Auto-infer direction based on current price
      if (chartData && chartData.current_price !== null) {
         update.direction = price >= chartData.current_price ? 'Bullish' : 'Bearish';
      }
    } else {
      if (chartData && chartData.current_price !== null && chartData.current_price > 0) {
        const move = ((price - chartData.current_price) / chartData.current_price) * 100;
        update.percentage = Math.abs(move).toFixed(2);
        update.claim_type = move >= 0 ? 'PERCENTAGE_UP' : 'PERCENTAGE_DOWN';
        update.direction = move >= 0 ? 'Bullish' : 'Bearish';
      }
    }
    onChange(update);
  }

  // Calculate the target price for the chart line if percentage is selected
  let chartTargetPrice: number | null = null;
  if (isPrice && value.percentage) {
    chartTargetPrice = parseFloat(value.percentage);
  } else if (!isPrice && value.percentage && chartData?.current_price) {
    const pct = parseFloat(value.percentage);
    if (!isNaN(pct)) {
      const multiplier = value.claim_type === 'PERCENTAGE_DOWN' ? (1 - pct/100) : (1 + pct/100);
      chartTargetPrice = chartData.current_price * multiplier;
    }
  }

  return (
    <div className="space-y-4 animate-in slide-in-from-right-2 fade-in">
      <div className="space-y-1">
        <Label className="text-sm font-semibold">Select Target & Deadline</Label>
        <p className="text-xs text-muted-foreground">
          Use the chart to pick a target, or enter the values manually below.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 pt-2">
        <div className="space-y-1.5">
          <Label className="text-xs">
            {isPrice ? 'Target Price' : 'Target Move (%)'}
          </Label>
          <div className="flex relative items-center">
            {isPrice && <span className="absolute left-3 text-muted-foreground text-sm">$</span>}
            <Input
              type="number"
              min={isPrice ? '0' : '0.1'}
              step={isPrice ? '0.01' : '0.1'}
              value={value.percentage}
              onChange={(e) => onChange({ percentage: e.target.value })}
              className={cn('h-9 text-sm num', isPrice && 'pl-6')}
              placeholder={isPrice ? 'e.g. 103000' : 'e.g. 25'}
              aria-invalid={!!targetError}
            />
          </div>
          <FieldError>{targetError}</FieldError>
          {!isPrice && value.direction && (
            <div className={cn("text-xs font-medium", value.direction === 'Bullish' ? 'text-success' : 'text-danger')}>
              {value.direction === 'Bullish' ? '↑ Bullish (Up)' : '↓ Bearish (Down)'}
            </div>
          )}
          {isPrice && value.direction && (
            <div className={cn("text-xs font-medium", value.direction === 'Bullish' ? 'text-success' : 'text-danger')}>
              {value.direction === 'Bullish' ? '↑ Rise to target' : '↓ Fall to target'}
            </div>
          )}
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs">Deadline</Label>
          <Input
            type="date"
            min={minDate}
            value={value.until}
            onChange={(e) => onChange({ until: e.target.value })}
            className="h-9 text-sm num"
            aria-invalid={!!deadlineError}
          />
          <FieldError>{deadlineError}</FieldError>
        </div>
      </div>

      <div className="relative pt-2">
        {chartData ? (
          <InteractiveChart
            data={chartData}
            interval={interval}
            onIntervalChange={setInterval}
            priceLines={chartTargetPrice !== null ? [{ price: chartTargetPrice, color: '#f59e0b', title: 'Target' }] : []}
            dateLines={value.until ? [{ dateStr: value.until, color: 'rgba(245, 158, 11, 0.4)', title: 'Deadline' }] : []}
            onSelectTarget={handleSelectTarget}
            refetching={loading}
          />
        ) : (
          <div className="h-[320px] flex items-center justify-center border rounded-lg bg-muted/20">
            <span className="text-sm text-muted-foreground animate-pulse">Loading chart...</span>
          </div>
        )}
      </div>

      <div className="flex gap-2 pt-4">
        <Button variant="outline" className="w-1/3" onClick={onBack}>
          Back
        </Button>
        <Button 
          className="w-2/3" 
          disabled={!canProceed} 
          onClick={onNext}
        >
          Next Step
        </Button>
      </div>
    </div>
  );
}
