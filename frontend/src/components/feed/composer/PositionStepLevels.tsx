import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { getAssetChartData } from '@/lib/api';
import type { AssetChartData, ChartCandleInterval } from '@/lib/types';
import type { PositionDraft } from './PositionWizard';
import { InteractiveChart } from './InteractiveChart';

interface PositionStepLevelsProps {
  value: PositionDraft;
  onChange: (patch: Partial<PositionDraft>) => void;
  onNext: () => void;
  onBack: () => void;
}

export function PositionStepLevels({ value, onChange, onNext, onBack }: PositionStepLevelsProps) {
  const [chartData, setChartData] = useState<AssetChartData | null>(null);
  const [interval, setInterval] = useState<ChartCandleInterval>('4h');
  const [loading, setLoading] = useState(false);

  // 0: Entry, 1: TP, 2: SL
  const [phase, setPhase] = useState<0 | 1 | 2>(0);
  const [entry, setEntry] = useState<string>(value.entryPrice || '');
  const [tp, setTp] = useState<string>(value.takeProfit || '');
  const [sl, setSl] = useState<string>(value.stopLoss || '');

  useEffect(() => {
    if (!value.assetId) return;
    let active = true;
    setLoading(true);

    getAssetChartData(Number(value.assetId), interval)
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
  }, [value.assetId, interval]);

  function handleSelectTarget(price: number) {
    const pStr = price.toFixed(4); // Use 4 decimals for crypto accuracy
    if (phase === 0) {
      setEntry(pStr);
    } else if (phase === 1) {
      setTp(pStr);
    } else if (phase === 2) {
      setSl(pStr);
    }
  }

  function handleNext() {
    if (phase === 0) {
      setPhase(1);
    } else if (phase === 1) {
      setPhase(2);
    } else {
      // Validate direction naturally
      const en = parseFloat(entry);
      const t = parseFloat(tp);
      const direction = t >= en ? 'long' : 'short';
      
      onChange({ 
        entryPrice: entry, 
        takeProfit: tp, 
        stopLoss: sl, 
        direction 
      });
      onNext();
    }
  }

  function handleBack() {
    if (phase === 2) {
      setPhase(1);
    } else if (phase === 1) {
      setPhase(0);
    } else {
      onBack();
    }
  }

  const priceLines = [];
  if (entry && !isNaN(parseFloat(entry))) {
    priceLines.push({ price: parseFloat(entry), color: '#3b82f6', title: 'Entry' });
  }
  if (tp && !isNaN(parseFloat(tp)) && phase >= 1) {
    priceLines.push({ price: parseFloat(tp), color: '#22c55e', title: 'Take Profit' });
  }
  if (sl && !isNaN(parseFloat(sl)) && phase >= 2) {
    priceLines.push({ price: parseFloat(sl), color: '#ef4444', title: 'Stop Loss' });
  }

  let canProceed = false;
  if (phase === 0 && entry) canProceed = true;
  if (phase === 1 && tp) canProceed = true;
  if (phase === 2 && sl) canProceed = true;

  const getPhaseTitle = () => {
    if (phase === 0) return 'Pick Entry Price';
    if (phase === 1) return 'Pick Take Profit';
    return 'Pick Stop Loss';
  };

  const getPhaseDescription = () => {
    if (phase === 0) return 'Tap the chart to set your ideal entry point.';
    if (phase === 1) return 'Tap the chart to set your target take profit level.';
    return 'Tap the chart to set your stop loss level.';
  };

  return (
    <div className="space-y-4 animate-in slide-in-from-right-2 fade-in">
      <div className="space-y-1">
        <Label className="text-sm font-semibold text-indigo-400">{getPhaseTitle()}</Label>
        <p className="text-xs text-muted-foreground">{getPhaseDescription()}</p>
      </div>

      <div className="relative pt-2">
        {chartData ? (
          <InteractiveChart
            data={chartData}
            interval={interval}
            onIntervalChange={setInterval}
            priceLines={priceLines}
            dateLines={[]} // Position dates are handled in Step 3
            onSelectTarget={handleSelectTarget}
            refetching={loading}
          />
        ) : (
          <div className="h-[320px] flex items-center justify-center border rounded-lg bg-muted/20">
            <span className="text-sm text-muted-foreground animate-pulse">Loading chart...</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2">
         <div className="p-2 border rounded-md bg-background space-y-1">
           <p className="text-[10px] text-muted-foreground uppercase">Entry</p>
           <p className="text-xs font-semibold">{entry ? `$${entry}` : '-'}</p>
         </div>
         <div className={`p-2 border rounded-md space-y-1 ${phase >= 1 ? 'bg-background' : 'bg-muted/30 opacity-50'}`}>
           <p className="text-[10px] text-muted-foreground uppercase">Take Profit</p>
           <p className="text-xs font-semibold text-green-500">{tp && phase >= 1 ? `$${tp}` : '-'}</p>
         </div>
         <div className={`p-2 border rounded-md space-y-1 ${phase >= 2 ? 'bg-background' : 'bg-muted/30 opacity-50'}`}>
           <p className="text-[10px] text-muted-foreground uppercase">Stop Loss</p>
           <p className="text-xs font-semibold text-red-500">{sl && phase >= 2 ? `$${sl}` : '-'}</p>
         </div>
      </div>

      <div className="flex gap-2 pt-4">
        <Button variant="outline" className="w-1/3" onClick={handleBack}>
          Back
        </Button>
        <Button 
          className="w-2/3" 
          disabled={!canProceed} 
          onClick={handleNext}
        >
          {phase === 2 ? 'Review Position' : 'Next'}
        </Button>
      </div>
    </div>
  );
}
